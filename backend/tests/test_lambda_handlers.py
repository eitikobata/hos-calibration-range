from decimal import Decimal

import boto3

from lambda_handlers.simulate_worker import handler as simulate_handler


def test_simulate_worker_returns_result_dict():
    event = {
        "scenario_id": "slope-01",
        "terrain": "slope",
        "config": {"actuator_gain": 2.1, "stabilization_sensitivity": 0.6, "load_kg": 300},
    }
    result = simulate_handler(event, context=None)
    assert result["scenario_id"] == "slope-01"
    assert result["terrain"] == "slope"
    assert 0 <= result["stability_margin"] <= 100


def test_aggregate_first_run_becomes_baseline(aws, monkeypatch):
    import lambda_handlers.aggregate_results as aggregate_module

    monkeypatch.setattr(aggregate_module, "_CALIBRATIONS_TABLE", "test-calibrations")
    monkeypatch.setattr(aggregate_module, "_RUNS_TABLE", "test-runs")

    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    calibrations = dynamodb.Table("test-calibrations")
    runs = dynamodb.Table("test-runs")
    calibrations.put_item(Item={"id": "cal-1"})
    runs.put_item(Item={"id": "run-1", "calibration_id": "cal-1", "status": "RUNNING"})

    event = {
        "run_id": "run-1",
        "calibration_id": "cal-1",
        "results": [
            {"scenario_id": "a", "terrain": "flat", "stability_margin": 80.0,
             "max_lean_angle_deg": 5.0, "energy_consumption_kwh": 3.0, "passed": True},
            {"scenario_id": "b", "terrain": "rubble", "stability_margin": 60.0,
             "max_lean_angle_deg": 12.0, "energy_consumption_kwh": 5.0, "passed": True},
        ],
    }

    output = aggregate_module.handler(event, context=None)

    assert output["average_stability_margin"] == 70.0
    assert output["regression_vs_baseline"] is None  # first run, no baseline yet

    stored_run = runs.get_item(Key={"id": "run-1"})["Item"]
    assert stored_run["status"] == "COMPLETED"
    assert float(stored_run["average_stability_margin"]) == 70.0

    stored_calibration = calibrations.get_item(Key={"id": "cal-1"})["Item"]
    assert float(stored_calibration["baseline_average_stability_margin"]) == 70.0


def test_aggregate_second_run_compares_against_baseline(aws, monkeypatch):
    import lambda_handlers.aggregate_results as aggregate_module

    monkeypatch.setattr(aggregate_module, "_CALIBRATIONS_TABLE", "test-calibrations")
    monkeypatch.setattr(aggregate_module, "_RUNS_TABLE", "test-runs")

    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    calibrations = dynamodb.Table("test-calibrations")
    runs = dynamodb.Table("test-runs")
    calibrations.put_item(
        Item={"id": "cal-1", "baseline_average_stability_margin": Decimal("70.0"), "baseline_run_id": "run-1"}
    )
    runs.put_item(Item={"id": "run-2", "calibration_id": "cal-1", "status": "RUNNING"})

    event = {
        "run_id": "run-2",
        "calibration_id": "cal-1",
        "results": [
            {"scenario_id": "a", "terrain": "flat", "stability_margin": 65.0,
             "max_lean_angle_deg": 6.0, "energy_consumption_kwh": 3.2, "passed": True},
        ],
    }

    output = aggregate_module.handler(event, context=None)

    assert output["average_stability_margin"] == 65.0
    assert output["regression_vs_baseline"] == -5.0  # worse than the 70.0 baseline
