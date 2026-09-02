"""
Single stack for the whole project. Splitting into multiple stacks
(DataStack, ComputeStack, ApiStack) is a pattern that earns its
complexity once resources need independent deploy lifecycles - at this
project's size it would just be extra indirection with no real benefit,
so everything lives together here on purpose.
"""
from __future__ import annotations

from aws_cdk import Duration, RemovalPolicy, Stack
from aws_cdk import aws_apigateway as apigw
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_stepfunctions as sfn
from aws_cdk import aws_stepfunctions_tasks as sfn_tasks
from constructs import Construct

# Fixed, hardcoded at deploy time - matches the "known limitation" pattern
# from the Nexus project (fixed skill set at bootstrap). Adding a terrain
# type here means a redeploy, not a runtime config change. Fine for a
# portfolio project; a production version would make this data-driven.
_TERRAIN_SCENARIOS = [
    {"scenario_id": "flat-01", "terrain": "flat"},
    {"scenario_id": "slope-01", "terrain": "slope"},
    {"scenario_id": "wet-01", "terrain": "wet"},
    {"scenario_id": "rubble-01", "terrain": "rubble"},
]

# Provisioned, not on-demand, and deliberately low. DynamoDB's
# Always Free allowance (25 RCU + 25 WCU total, shared across every
# table in the account) only applies to PROVISIONED billing mode - the
# on-demand mode that's easiest to reach for bills per-request with no
# free allowance at all. Two tables at 5/5 leaves headroom under the
# account-wide 25/25 ceiling even if another project shares the account.
_READ_CAPACITY = 5
_WRITE_CAPACITY = 5


class HosCalibrationStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        calibrations_table = dynamodb.Table(
            self,
            "CalibrationsTable",
            partition_key=dynamodb.Attribute(
                name="id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PROVISIONED,
            read_capacity=_READ_CAPACITY,
            write_capacity=_WRITE_CAPACITY,
            # DESTROY, not RETAIN: this is a portfolio demo, not a system
            # holding data anyone depends on. A stray forgotten table is a
            # bigger real-world risk than losing demo data on teardown.
            removal_policy=RemovalPolicy.DESTROY,
        )

        runs_table = dynamodb.Table(
            self,
            "RunsTable",
            partition_key=dynamodb.Attribute(
                name="id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PROVISIONED,
            read_capacity=_READ_CAPACITY,
            write_capacity=_WRITE_CAPACITY,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Code comes from backend/build/, produced by backend/build.sh -
        # NOT from backend/ directly. See that script for why (Docker-free
        # dependency bundling, boto3 excluded since the runtime provides it).
        lambda_code = lambda_.Code.from_asset("../backend/build")
        common_lambda_kwargs = dict(
            runtime=lambda_.Runtime.PYTHON_3_12,
            code=lambda_code,
            timeout=Duration.seconds(30),
            memory_size=512,
        )

        simulate_fn = lambda_.Function(
            self,
            "SimulateFunction",
            handler="lambda_handlers.simulate_worker.handler",
            **common_lambda_kwargs,
        )

        aggregate_fn = lambda_.Function(
            self,
            "AggregateFunction",
            handler="lambda_handlers.aggregate_results.handler",
            environment={
                "CALIBRATIONS_TABLE": calibrations_table.table_name,
                "RUNS_TABLE": runs_table.table_name,
            },
            **common_lambda_kwargs,
        )
        calibrations_table.grant_read_write_data(aggregate_fn)
        runs_table.grant_read_write_data(aggregate_fn)

        # --- Step Functions: generate scenarios -> fan out -> aggregate ---

        generate_scenarios = sfn.Pass(
            self,
            "GenerateScenarios",
            parameters={
                "run_id.$": "$.run_id",
                "calibration_id.$": "$.calibration_id",
                "config.$": "$.config",
                "scenarios": _TERRAIN_SCENARIOS,
            },
        )

        simulate_task = sfn_tasks.LambdaInvoke(
            self,
            "RunOneSimulation",
            lambda_function=simulate_fn,
            payload_response_only=True,
        )

        # Map fans the 4 hardcoded scenarios out to 4 parallel Lambda
        # invocations. max_concurrency=0 means "no explicit cap" - fine
        # at 4 items; would need a real limit if the scenario list grew
        # into the hundreds and risked hitting Lambda's account-level
        # concurrent-execution limit.
        run_simulations = sfn.Map(
            self,
            "RunSimulations",
            items_path="$.scenarios",
            item_selector={
                "scenario_id.$": "$$.Map.Item.Value.scenario_id",
                "terrain.$": "$$.Map.Item.Value.terrain",
                "config.$": "$.config",
            },
            result_path="$.results",
            max_concurrency=0,
        )
        run_simulations.item_processor(simulate_task)

        aggregate_task = sfn_tasks.LambdaInvoke(
            self,
            "AggregateResults",
            lambda_function=aggregate_fn,
            payload=sfn.TaskInput.from_object(
                {
                    "run_id.$": "$.run_id",
                    "calibration_id.$": "$.calibration_id",
                    "results.$": "$.results",
                }
            ),
            payload_response_only=True,
        )

        definition = generate_scenarios.next(run_simulations).next(aggregate_task)

        state_machine = sfn.StateMachine(
            self,
            "CalibrationStateMachine",
            definition_body=sfn.DefinitionBody.from_chainable(definition),
            timeout=Duration.minutes(5),
        )

        # --- API: FastAPI-via-Mangum behind a single Lambda proxy ---

        api_fn = lambda_.Function(
            self,
            "ApiFunction",
            handler="lambda_handlers.api_handler.handler",
            environment={
                "CALIBRATIONS_TABLE": calibrations_table.table_name,
                "RUNS_TABLE": runs_table.table_name,
                "STATE_MACHINE_ARN": state_machine.state_machine_arn,
            },
            **common_lambda_kwargs,
        )
        calibrations_table.grant_read_write_data(api_fn)
        runs_table.grant_read_write_data(api_fn)
        state_machine.grant_start_execution(api_fn)

        apigw.LambdaRestApi(
            self,
            "Api",
            handler=api_fn,
            proxy=True,
            deploy_options=apigw.StageOptions(stage_name="prod"),
        )
