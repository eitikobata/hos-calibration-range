"""
Invoked once per Map-state iteration in the Step Functions workflow -
one call per (calibration, terrain scenario) pair. Deliberately stateless:
it takes a scenario + config, returns a result, and touches no database.
Fan-out happens at the state-machine level (Map state), not in here -
this function has no idea it's running in parallel with three others.
"""
from __future__ import annotations

from app.models import CalibrationConfig, TerrainType
from app.simulation import run_simulation


def handler(event: dict, context) -> dict:
    """
    Expected event shape (one Map iteration's input):
    {
        "scenario_id": "slope-01",
        "terrain": "slope",
        "config": { "actuator_gain": 2.1, "stabilization_sensitivity": 0.6, "load_kg": 400 }
    }
    """
    config = CalibrationConfig(**event["config"])
    terrain = TerrainType(event["terrain"])

    result = run_simulation(
        scenario_id=event["scenario_id"], terrain=terrain, config=config
    )

    return result.model_dump(mode="json")
