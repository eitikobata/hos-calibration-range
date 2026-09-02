"""
Data models shared across the API, the Step Functions workers, and the
aggregation step. Kept in one file on purpose: a calibration project has
few enough models that splitting them into multiple files would just add
import indirection for no benefit at this size.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class TerrainType(str, Enum):
    """
    Terrain scenarios the calibration gets tested against. Kept as a fixed
    enum (not a free string) so a typo like "flatt" fails validation at the
    API boundary instead of silently producing a Step Functions execution
    that never matches any known scenario.
    """

    FLAT = "flat"
    SLOPE = "slope"
    RUBBLE = "rubble"
    WET = "wet"


class CalibrationConfig(BaseModel):
    """
    The tunable parameters for a single calibration attempt. These map to
    the kind of knobs a real actuator-control tuning pass would expose:
    how aggressively the actuators respond (gain) and how sensitive the
    stabilization loop is to detected lean.
    """

    actuator_gain: float = Field(
        ..., gt=0, le=5.0, description="Actuator response gain, 0-5"
    )
    stabilization_sensitivity: float = Field(
        ..., gt=0, le=1.0, description="Stabilization loop sensitivity, 0-1"
    )
    load_kg: float = Field(..., ge=0, le=5000, description="Carried load in kg")
    label: Optional[str] = Field(
        None, description="Human-readable name for this calibration attempt"
    )


class SimulationScenario(BaseModel):
    """One (terrain) condition a calibration gets run against."""

    terrain: TerrainType
    scenario_id: str


class SimulationResult(BaseModel):
    """
    Output of a single simulation run (one calibration x one terrain
    scenario). This is what SimulateFunction returns and what
    AggregateFunction consumes in bulk.
    """

    scenario_id: str
    terrain: TerrainType
    stability_margin: float = Field(..., description="0-100, higher is safer")
    max_lean_angle_deg: float
    energy_consumption_kwh: float
    passed: bool


class CalibrationRunRequest(BaseModel):
    """Body for POST /calibrations/{id}/run."""

    config: CalibrationConfig


class CalibrationRunSummary(BaseModel):
    """
    What gets stored in the Runs table and returned from GET /runs/{id}.
    Aggregates every SimulationResult in a run plus the delta against the
    calibration's baseline, if one exists.
    """

    run_id: str
    calibration_id: str
    status: str
    average_stability_margin: Optional[float] = None
    worst_case_stability_margin: Optional[float] = None
    regression_vs_baseline: Optional[float] = None
    results: list[SimulationResult] = Field(default_factory=list)
