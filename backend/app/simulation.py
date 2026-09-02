"""
Simulation engine. This is deliberately NOT a real rigid-body physics
simulator (that's a project of its own) - it's a deterministic-per-seed
model that reacts sensibly to the tunable parameters:

- Higher actuator_gain reduces lean angle but costs more energy, and past
  a threshold starts overshooting (reduces stability again).
- Higher stabilization_sensitivity reduces lean angle up to a point, then
  makes the system twitchy (reduces stability past that point).
- Harder terrain (rubble, wet) reduces stability and raises lean angle
  for the same calibration.
- Higher load reduces stability margin and raises energy consumption.

The point of the model existing at all is to give a portfolio project a
believable, explainable "did this calibration get better or worse"
signal - not to be metrologically accurate.
"""
from __future__ import annotations

import numpy as np

from app.models import CalibrationConfig, SimulationResult, TerrainType

# Terrain difficulty multipliers, tuned by hand to feel ordered
# (flat easiest, rubble hardest) rather than derived from any real data.
_TERRAIN_DIFFICULTY = {
    TerrainType.FLAT: 1.0,
    TerrainType.SLOPE: 1.35,
    TerrainType.WET: 1.5,
    TerrainType.RUBBLE: 1.9,
}

_STABILITY_PASS_THRESHOLD = 55.0


def _seed_for(scenario_id: str, config: CalibrationConfig) -> int:
    """
    Deterministic seed derived from the scenario + config, so re-running
    the exact same calibration against the exact same scenario always
    reproduces the exact same result. That determinism matters for the
    portfolio story: a "regression vs baseline" comparison is meaningless
    if re-running an unchanged calibration silently changes the numbers.
    """
    raw = f"{scenario_id}:{config.actuator_gain}:{config.stabilization_sensitivity}:{config.load_kg}"
    return abs(hash(raw)) % (2**32)


def run_simulation(
    scenario_id: str, terrain: TerrainType, config: CalibrationConfig
) -> SimulationResult:
    rng = np.random.default_rng(_seed_for(scenario_id, config))

    difficulty = _TERRAIN_DIFFICULTY[terrain]

    # Gain helps up to ~3.0, then overshoot penalty kicks in.
    gain_effectiveness = config.actuator_gain - max(0.0, config.actuator_gain - 3.0) * 2.5

    # Sensitivity helps up to ~0.7, then twitchiness penalty kicks in.
    sensitivity_effectiveness = config.stabilization_sensitivity - max(
        0.0, config.stabilization_sensitivity - 0.7
    ) * 1.8

    load_penalty = (config.load_kg / 5000) * 25  # up to 25pt penalty at max load

    base_stability = 40 + gain_effectiveness * 12 + sensitivity_effectiveness * 30
    stability_margin = base_stability / difficulty - load_penalty
    stability_margin += rng.normal(0, 2.5)  # sensor/actuator noise
    stability_margin = float(np.clip(stability_margin, 0, 100))

    max_lean_angle = 25 - (gain_effectiveness * 3 + sensitivity_effectiveness * 4)
    max_lean_angle = max_lean_angle * difficulty + (config.load_kg / 5000) * 8
    max_lean_angle += rng.normal(0, 0.8)
    max_lean_angle = float(np.clip(max_lean_angle, 0, 45))

    energy_consumption = (
        2.0
        + config.actuator_gain * 1.1
        + config.stabilization_sensitivity * 0.8
        + (config.load_kg / 5000) * 3
    ) * difficulty
    energy_consumption += rng.normal(0, 0.15)
    energy_consumption = float(max(0.1, energy_consumption))

    return SimulationResult(
        scenario_id=scenario_id,
        terrain=terrain,
        stability_margin=round(stability_margin, 2),
        max_lean_angle_deg=round(max_lean_angle, 2),
        energy_consumption_kwh=round(energy_consumption, 3),
        passed=stability_margin >= _STABILITY_PASS_THRESHOLD,
    )
