import os

import boto3
import pytest
from moto import mock_aws

# Table/state-machine names must be set before app.main is imported,
# since it reads them from the environment at module load time.
os.environ.setdefault("CALIBRATIONS_TABLE", "test-calibrations")
os.environ.setdefault("RUNS_TABLE", "test-runs")
os.environ.setdefault("STATE_MACHINE_ARN", "arn:aws:states:us-east-1:123456789012:stateMachine:test")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")


@pytest.fixture
def aws(monkeypatch):
    """
    Spins up moto's in-memory AWS, creates the two DynamoDB tables the app
    expects, and registers a fake state machine so start_execution has
    something to call. Yields nothing - tests just import app.main and it
    picks up the mocked AWS through boto3 as normal.
    """
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        dynamodb.create_table(
            TableName="test-calibrations",
            KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        dynamodb.create_table(
            TableName="test-runs",
            KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        sfn = boto3.client("stepfunctions", region_name="us-east-1")
        role = "arn:aws:iam::123456789012:role/fake-role"
        definition = '{"StartAt": "Noop", "States": {"Noop": {"Type": "Pass", "End": true}}}'
        created = sfn.create_state_machine(
            name="test",
            definition=definition,
            roleArn=role,
        )

        # moto assigns its own ARN on creation, which won't match whatever
        # STATE_MACHINE_ARN happened to be set to at import time. Patch the
        # module-level value directly so start_execution targets the real
        # mocked state machine instead of a made-up ARN.
        import app.main as main_module

        monkeypatch.setattr(main_module, "_STATE_MACHINE_ARN", created["stateMachineArn"])

        yield
