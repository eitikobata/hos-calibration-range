"""
Runs once, after every simulate_worker Map iteration has finished. Takes
the full list of SimulationResults, computes the run's summary stats,
compares against the calibration's baseline (if one exists), and writes
the final report to the Runs table - this is what GET /runs/{id} reads.

Baseline rule, kept deliberately simple for v1: the FIRST completed run
for a given calibration becomes its baseline automatically. Every run
after that is compared against it, but never overwrites it. Promoting a
later run to be the new baseline is a follow-up feature, not v1 - added
here because "how do baselines get set" is exactly the kind of decision
that's easy to leave implicit and then be unable to explain later.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

import boto3

from app.dynamo_utils import to_dynamo_safe

_CALIBRATIONS_TABLE = os.environ.get("CALIBRATIONS_TABLE", "")
_RUNS_TABLE = os.environ.get("RUNS_TABLE", "")

_dynamodb = boto3.resource("dynamodb")


def handler(event: dict, context) -> dict:
    """
    Expected event shape:
    {
        "run_id": "...",
        "calibration_id": "...",
        "results": [ <SimulationResult dict>, ... ]   # Map state output
    }
    """
    run_id = event["run_id"]
    calibration_id = event["calibration_id"]
    results = event["results"]

    margins = [r["stability_margin"] for r in results]
    average_margin = sum(margins) / len(margins)
    worst_case_margin = min(margins)

    calibrations_table = _dynamodb.Table(_CALIBRATIONS_TABLE)
    calibration_item = calibrations_table.get_item(
        Key={"id": calibration_id}
    ).get("Item", {})

    baseline_margin = calibration_item.get("baseline_average_stability_margin")
    regression_vs_baseline = None

    if baseline_margin is None:
        # First run for this calibration - it becomes the baseline.
        calibrations_table.update_item(
            Key={"id": calibration_id},
            UpdateExpression="SET baseline_average_stability_margin = :m, baseline_run_id = :r",
            ExpressionAttributeValues=to_dynamo_safe({":m": average_margin, ":r": run_id}),
        )
    else:
        regression_vs_baseline = round(average_margin - float(baseline_margin), 2)

    runs_table = _dynamodb.Table(_RUNS_TABLE)
    runs_table.update_item(
        Key={"id": run_id},
        UpdateExpression=(
            "SET #status = :status, average_stability_margin = :avg, "
            "worst_case_stability_margin = :worst, results = :results, "
            "completed_at = :completed_at"
            + (", regression_vs_baseline = :reg" if regression_vs_baseline is not None else "")
        ),
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues=to_dynamo_safe(
            {
                ":status": "COMPLETED",
                ":avg": round(average_margin, 2),
                ":worst": worst_case_margin,
                ":results": results,
                ":completed_at": datetime.now(timezone.utc).isoformat(),
                **(
                    {":reg": regression_vs_baseline}
                    if regression_vs_baseline is not None
                    else {}
                ),
            }
        ),
    )

    return {
        "run_id": run_id,
        "average_stability_margin": round(average_margin, 2),
        "regression_vs_baseline": regression_vs_baseline,
    }
