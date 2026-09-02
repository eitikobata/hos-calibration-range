"use client";

import { useEffect, useRef, useState } from "react";
import { ApiError, createCalibration, getRun, triggerRun } from "@/lib/api";
import type { CalibrationConfig, CalibrationRunSummary, Terrain } from "@/lib/types";
import styles from "./page.module.css";

type Phase = "idle" | "starting" | "running" | "done" | "error";

const DEFAULT_CONFIG: CalibrationConfig = {
  actuator_gain: 2.0,
  stabilization_sensitivity: 0.5,
  load_kg: 200,
  label: "",
};

const POLL_INTERVAL_MS = 2000;

// Display-only flavor names for the four fixed terrain scenarios the
// backend always runs (see infra/infra/hos_stack.py _TERRAIN_SCENARIOS).
// The API contract stays plain English ("flat", "slope", "rubble", "wet")
// - only this map changes, so relabeling here never touches the backend.
const TERRAIN_LABELS: Record<Terrain, string> = {
  flat: "Hangar floor",
  slope: "Access ramp",
  rubble: "Babylon site",
  wet: "Wet deck",
};

const STATUS_LABELS: Record<Phase, string> = {
  idle: "standby",
  starting: "initializing",
  running: "running diagnostic",
  done: "complete",
  error: "fault",
};

export default function Page() {
  const [config, setConfig] = useState<CalibrationConfig>(DEFAULT_CONFIG);
  const [phase, setPhase] = useState<Phase>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [run, setRun] = useState<CalibrationRunSummary | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  function updateField(field: keyof CalibrationConfig, value: string) {
    setConfig((prev) => ({
      ...prev,
      [field]: field === "label" ? value : Number(value),
    }));
  }

  function describeError(err: unknown): string {
    if (err instanceof ApiError) {
      return err.status === 404
        ? "That run wasn't found. It may have expired or the ID is wrong."
        : `The API rejected the request: ${err.message}`;
    }
    return `Couldn't reach the API. Check that the backend is running and reachable at ${
      process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000"
    }.`;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErrorMessage(null);
    setRun(null);
    setPhase("starting");

    try {
      const { id } = await createCalibration(config);
      const { run_id } = await triggerRun(id, config);
      setPhase("running");

      pollRef.current = setInterval(async () => {
        try {
          const result = await getRun(run_id);
          if (result.status === "COMPLETED") {
            if (pollRef.current) clearInterval(pollRef.current);
            setRun(result);
            setPhase("done");
          }
        } catch (err) {
          if (pollRef.current) clearInterval(pollRef.current);
          setErrorMessage(describeError(err));
          setPhase("error");
        }
      }, POLL_INTERVAL_MS);
    } catch (err) {
      setErrorMessage(describeError(err));
      setPhase("error");
    }
  }

  const lampState = phase === "starting" ? "running" : phase;

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <div>
          <h1 className={styles.title}>HOS Calibration Range</h1>
          <p className={styles.subtitle}>
            Servo and gyro tuning test bench
          </p>
        </div>
        <div className={styles.statusLamp}>
          <span className={styles.lampDot} data-state={lampState} />
          {STATUS_LABELS[phase]}
        </div>
      </header>

      <div className={styles.grid}>
        <section className={styles.panel}>
          <h2 className={styles.panelTitle}>Calibration</h2>
          <form onSubmit={handleSubmit}>
            <div className={styles.field}>
              <label htmlFor="actuator_gain">Servo response</label>
              <input
                id="actuator_gain"
                type="number"
                step="0.1"
                min="0.1"
                max="5"
                value={config.actuator_gain}
                onChange={(e) => updateField("actuator_gain", e.target.value)}
                required
              />
              <span className={styles.hint}>
                Gain on the posture-correcting actuators — too low reacts
                slowly, too high overshoots. 0–5, effective up to ~3.0.
              </span>
            </div>

            <div className={styles.field}>
              <label htmlFor="stabilization_sensitivity">
                Gyro sensitivity
              </label>
              <input
                id="stabilization_sensitivity"
                type="number"
                step="0.05"
                min="0.05"
                max="1"
                value={config.stabilization_sensitivity}
                onChange={(e) =>
                  updateField("stabilization_sensitivity", e.target.value)
                }
                required
              />
              <span className={styles.hint}>
                How readily the balance system reacts to a detected lean.
                0–1, effective up to ~0.7.
              </span>
            </div>

            <div className={styles.field}>
              <label htmlFor="load_kg">Payload (kg)</label>
              <input
                id="load_kg"
                type="number"
                step="10"
                min="0"
                max="5000"
                value={config.load_kg}
                onChange={(e) => updateField("load_kg", e.target.value)}
                required
              />
              <span className={styles.hint}>
                Equipment or cargo weight carried during the test.
              </span>
            </div>

            <div className={styles.field}>
              <label htmlFor="label">Designation (optional)</label>
              <input
                id="label"
                type="text"
                value={config.label}
                onChange={(e) => updateField("label", e.target.value)}
                placeholder="e.g. wider stance, softer gain"
              />
            </div>

            <button
              type="submit"
              className={styles.runButton}
              disabled={phase === "starting" || phase === "running"}
            >
              {phase === "starting" || phase === "running"
                ? "Running…"
                : "Run diagnostic"}
            </button>
          </form>

          {phase === "error" && errorMessage && (
            <div className={styles.errorBox}>{errorMessage}</div>
          )}

          <details className={styles.glossary}>
            <summary>What do these mean?</summary>
            <dl className={styles.glossaryList}>
              <div>
                <dt>Servo response</dt>
                <dd>
                  How hard the actuators correct when the unit starts to
                  lean. Too low and correction is sluggish; too high and
                  it overcorrects, like over-steering out of a skid.
                </dd>
              </div>
              <div>
                <dt>Gyro sensitivity</dt>
                <dd>
                  How easily the balance system notices it's leaning at
                  all. Too high and it reacts to lean that doesn't matter.
                </dd>
              </div>
              <div>
                <dt>Site names</dt>
                <dd>
                  The four fixed test conditions: hangar floor (flat),
                  access ramp (slope), Babylon site (construction debris),
                  wet deck. Each run tests all four.
                </dd>
              </div>
              <div>
                <dt>Balance margin</dt>
                <dd>
                  0–100, higher is safer — how far the unit stayed from
                  losing balance during the test.
                </dd>
              </div>
              <div>
                <dt>Reference calibration</dt>
                <dd>
                  The first run for a given calibration becomes its
                  reference. Every run after that shows how much better
                  or worse the new settings did against it.
                </dd>
              </div>
            </dl>
          </details>
        </section>

        <section className={styles.panel}>
          <h2 className={styles.panelTitle}>Diagnostic Readout</h2>

          {!run && phase !== "error" && (
            <p className={styles.emptyState}>
              {phase === "idle"
                ? "Set parameters and run a diagnostic to see results here."
                : "Running the diagnostic across four site conditions…"}
            </p>
          )}

          {run && (
            <div className={styles.fadeIn}>
              <div className={styles.summaryRow}>
                <div className={styles.stat}>
                  <span className={styles.statLabel}>Avg. balance margin</span>
                  <span className={styles.statValue}>
                    {run.average_stability_margin?.toFixed(1)}
                  </span>
                </div>
                <div className={styles.stat}>
                  <span className={styles.statLabel}>Worst-case margin</span>
                  <span className={styles.statValue}>
                    {run.worst_case_stability_margin?.toFixed(1)}
                  </span>
                </div>
                <div className={styles.stat}>
                  <span className={styles.statLabel}>Vs. reference calib.</span>
                  {run.regression_vs_baseline === null ? (
                    <span className={styles.statValue}>reference set</span>
                  ) : (
                    <span
                      className={styles.statValue}
                      data-tone={
                        run.regression_vs_baseline < 0 ? "warn" : "good"
                      }
                    >
                      {run.regression_vs_baseline > 0 ? "+" : ""}
                      {run.regression_vs_baseline.toFixed(1)}
                    </span>
                  )}
                </div>
              </div>

              <table className={styles.table}>
                <thead>
                  <tr>
                    <th>Site</th>
                    <th>Balance margin</th>
                    <th>Max lean</th>
                    <th>Energy</th>
                    <th>Result</th>
                  </tr>
                </thead>
                <tbody>
                  {run.results.map((r) => (
                    <tr key={r.scenario_id}>
                      <td>{TERRAIN_LABELS[r.terrain]}</td>
                      <td>{r.stability_margin.toFixed(1)}</td>
                      <td>{r.max_lean_angle_deg.toFixed(1)}°</td>
                      <td>{r.energy_consumption_kwh.toFixed(2)} kWh</td>
                      <td className={r.passed ? styles.passYes : styles.passNo}>
                        {r.passed ? "nominal" : "fault"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
