from app.models import CalibrationConfig, TerrainType
from app.simulation import run_simulation


def _config(**overrides) -> CalibrationConfig:
    defaults = dict(actuator_gain=2.0, stabilization_sensitivity=0.5, load_kg=200)
    defaults.update(overrides)
    return CalibrationConfig(**defaults)


def test_same_inputs_produce_identical_results():
    """
    Determinism is the whole point of seeding on (scenario_id, config) -
    a regression comparison is meaningless if re-running an unchanged
    calibration silently produces different numbers.
    """
    config = _config()
    first = run_simulation("scenario-a", TerrainType.FLAT, config)
    second = run_simulation("scenario-a", TerrainType.FLAT, config)
    assert first == second


def test_different_scenario_id_changes_result():
    config = _config()
    a = run_simulation("scenario-a", TerrainType.FLAT, config)
    b = run_simulation("scenario-b", TerrainType.FLAT, config)
    assert a != b


def test_rubble_is_harder_than_flat_for_same_config():
    config = _config()
    flat = run_simulation("s", TerrainType.FLAT, config)
    rubble = run_simulation("s", TerrainType.RUBBLE, config)
    assert rubble.stability_margin < flat.stability_margin
    assert rubble.max_lean_angle_deg > flat.max_lean_angle_deg


def test_higher_load_reduces_stability():
    light = run_simulation("s", TerrainType.FLAT, _config(load_kg=50))
    heavy = run_simulation("s", TerrainType.FLAT, _config(load_kg=4500))
    assert heavy.stability_margin < light.stability_margin


def test_excessive_gain_overshoots_and_hurts_stability():
    """
    The model rewards gain up to 3.0 and penalizes it after - this checks
    the penalty branch actually engages, not just the reward branch.
    """
    moderate = run_simulation("s", TerrainType.FLAT, _config(actuator_gain=3.0))
    excessive = run_simulation("s", TerrainType.FLAT, _config(actuator_gain=5.0))
    assert excessive.stability_margin < moderate.stability_margin


def test_stability_margin_and_lean_angle_stay_in_bounds():
    for gain in (0.1, 2.5, 5.0):
        for sensitivity in (0.1, 0.5, 1.0):
            for load in (0, 2500, 5000):
                result = run_simulation(
                    "bounds-check",
                    TerrainType.RUBBLE,
                    _config(
                        actuator_gain=gain,
                        stabilization_sensitivity=sensitivity,
                        load_kg=load,
                    ),
                )
                assert 0 <= result.stability_margin <= 100
                assert 0 <= result.max_lean_angle_deg <= 45
                assert result.energy_consumption_kwh > 0
