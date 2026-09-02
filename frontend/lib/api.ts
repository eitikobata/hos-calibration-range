import type { CalibrationConfig, CalibrationRunSummary } from "./types";

// Defaults to the local FastAPI dev server (uvicorn app.main:app --port 8000).
// Set NEXT_PUBLIC_API_URL to the real API Gateway URL once that exists -
// see .env.local.example. NEXT_PUBLIC_ prefix is required for Next.js to
// expose a variable to browser-side code, not just the server.
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });

  if (!response.ok) {
    // FastAPI's default error body is { "detail": "..." } - fall back to
    // the raw status text if the body isn't in that shape (e.g. a 502
    // from something in front of the API that isn't FastAPI at all).
    const body = await response.json().catch(() => null);
    throw new ApiError(body?.detail ?? response.statusText, response.status);
  }

  return response.json() as Promise<T>;
}

export function createCalibration(config: CalibrationConfig) {
  return request<{ id: string }>("/calibrations", {
    method: "POST",
    body: JSON.stringify(config),
  });
}

export function triggerRun(calibrationId: string, config: CalibrationConfig) {
  return request<{ run_id: string; status: string }>(
    `/calibrations/${calibrationId}/run`,
    { method: "POST", body: JSON.stringify({ config }) }
  );
}

export function getRun(runId: string) {
  return request<CalibrationRunSummary>(`/runs/${runId}`);
}

export { ApiError };
