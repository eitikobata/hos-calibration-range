// Mirrors backend/app/models.py. Kept as plain types, not generated
// automatically from the Pydantic schema - the project is small enough
// that a codegen step would be more setup than it saves right now. If
// the API grows past a handful of endpoints, generating this from
// FastAPI's OpenAPI schema (openapi-typescript) is the natural upgrade.

export type Terrain = "flat" | "slope" | "rubble" | "wet";

export interface CalibrationConfig {
  actuator_gain: number;
  stabilization_sensitivity: number;
  load_kg: number;
  label?: string;
}

export interface SimulationResult {
  scenario_id: string;
  terrain: Terrain;
  stability_margin: number;
  max_lean_angle_deg: number;
  energy_consumption_kwh: number;
  passed: boolean;
}

export type RunStatus = "RUNNING" | "COMPLETED";

export interface CalibrationRunSummary {
  run_id: string;
  calibration_id: string;
  status: RunStatus;
  average_stability_margin: number | null;
  worst_case_stability_margin: number | null;
  regression_vs_baseline: number | null;
  results: SimulationResult[];
}
