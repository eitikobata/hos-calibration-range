HOS Calibration Range

A batch calibration test bench for actuator and gyro tuning, built around a real fan-out/aggregate pipeline on serverless AWS — not a toy Lambda, a working Step Functions state machine coordinating parallel simulation workers, comparing every run against a saved baseline.

Live demo: hos.eitikobata.com

On-screen the system is presented through HOS — the Hyper Operating System, the actual designation used for a Labor's onboard control software — running calibration diagnostics against four fixed test conditions: hangar floor, access ramp, a construction site referencing the Babylon Project (the land-reclamation effort at the center of the wider setting), and a wet deck. Every field name in the UI maps to something real underneath (servo response is actuator gain, gyro sensitivity is the balance loop's reaction threshold) — a "What do these mean?" panel on the form spells out the plain-language meaning of each one, so the flavor never comes at the cost of the page actually being usable.

What it does
A calibration is a set of three tunable parameters: actuator gain, gyro (stabilization) sensitivity, and payload weight.
Running a diagnostic fans that calibration out across four terrain scenarios in parallel via a Step Functions Map state — not a loop inside one Lambda, four independent Lambda invocations coordinated by the state machine itself.
Each terrain run produces a deterministic result (seeded by scenario + config, so re-running an unchanged calibration always reproduces the same numbers): a balance margin, a max lean angle, energy consumption, and a pass/fail against a safety threshold.
An aggregation step averages the four results and compares them against the calibration's baseline — the first completed run for any given calibration automatically becomes its reference point; every run after that reports how much better or worse the new settings did.
The frontend polls for the run's status until it completes and renders the full breakdown — this is a batch workflow, not a live stream, so polling is the correct tool here, not a WebSocket standing in for one.
Architecture
┌─────────────────────────┐
│      Next.js Frontend    │
│  (form, poll, readout)    │
└────────────┬────────────┘
             │ HTTPS
             ▼
┌─────────────────────────┐
│       API Gateway          │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐        ┌────────────────┐
│  ApiFunction (Lambda)      │ ───▶  │   DynamoDB       │
│  FastAPI via Mangum          │       │  Calibrations,   │
└────────────┬────────────┘        │  Runs tables     │
             │ starts execution      └────────▲───────┘
             ▼                                 │
┌─────────────────────────┐                   │
│      Step Functions         │                   │
│   GenerateScenarios          │                   │
│         │                    │                   │
│         ▼ (Map, parallel)     │                   │
│   SimulateFunction × 4          │                   │
│         │                    │                   │
│         ▼                    │                   │
│   AggregateFunction ──────────┼───────────────────┘
└─────────────────────────┘

Every piece of compute above exists only while it's handling a request — nothing sits idle between calibrations. The frontend is deployed separately (see Deployment notes) and talks to the API over plain HTTPS; there's no shared session state between the two beyond that.

Key features
Real parallel fan-out, not a disguised loop. The Map state dispatches all four terrain simulations as independent Lambda invocations and waits on all of them before aggregating — Step Functions owns the coordination, not application code polling a list of promises.
Deterministic simulation, on purpose. The physics-flavored model is seeded from the scenario ID and the exact calibration values, so identical inputs always produce identical outputs. A regression comparison against a baseline is only meaningful if "nothing changed" actually means nothing changed in the numbers too.
Baseline-on-first-run, no separate setup step. A calibration's first completed run becomes its reference automatically — there's no "mark as baseline" action to forget to click.
Infrastructure as code, no manual console setup. Every resource — both DynamoDB tables, all three Lambda functions, the full state machine definition, the API Gateway proxy — is declared in CDK (Python) and stood up with a single cdk deploy.
In-universe naming that doesn't cost clarity. Every field on the form uses HOS's in-fiction terminology, but a plain-language glossary sits right below the form, closed by default, open on demand.
Technical decisions & trade-offs

Python + fully serverless AWS, deliberately different from the rest of this portfolio — every other project here runs NestJS on a persistent Docker/VPS service. This one runs Python on Lambda behind Step Functions, with nothing resembling a long-lived process anywhere in the backend. The goal was range: proving out an event-driven, non-persistent compute model and a second language, not repeating the same architecture with new theming.

DynamoDB in PROVISIONED mode, not on-demand, and deliberately low (5 read / 5 write capacity units per table). AWS's DynamoDB Always Free allowance — 25 RCU + 25 WCU, shared across every table in the account, with no 12-month expiry — only applies to provisioned mode. On-demand bills per request from the very first call. At this project's traffic, provisioned at low capacity costs nothing, indefinitely.

A global exception handler, added after catching a real Starlette gotcha. A handler registered for the bare Exception class runs inside Starlette's ServerErrorMiddleware, which sits outside CORSMiddleware in the framework's fixed layering — confirmed empirically, not assumed from docs: an unhandled exception's response came back over the wire with no Access-Control-Allow-Origin header at all, which browsers report as a CORS failure, hiding the real 500 and its actual message from anyone debugging the frontend. The fix sets the CORS header by hand inside the handler rather than relying on the middleware to do it, since in this one code path it structurally can't.

Decimal conversion for every DynamoDB write. boto3's DynamoDB resource layer rejects native Python floats outright (TypeError, not silent truncation) — every float coming out of a Pydantic model has to pass through an explicit float → Decimal conversion first. Caught by the test suite on the very first run against a real (mocked) table, not assumed going in.

Lambda code built from a committed build/ directory, not live source, and without a Docker dependency. CDK's usual asset-bundling story leans on Docker being available on every machine that deploys. A small build script instead runs pip install --platform manylinux2014_x86_64 ... --target build/ directly — producing Lambda-compatible wheels (this matters specifically for numpy, which ships compiled code) without needing a Docker daemon locally or in CI. The prebuilt boto3/botocore are deliberately stripped back out afterward, since every Python Lambda runtime already ships its own copy.

HOSTNAME=0.0.0.0 in the frontend's production Docker image. The Next.js standalone server binds to localhost only unless told otherwise — invisible to a reverse proxy running outside the container's own network namespace, even though the container's own logs show it starting up cleanly. This is Next.js's own documented requirement for standalone-mode Docker deployments, and it's the kind of failure that looks like a healthy container from the inside while being completely unreachable from the outside.

Build-arg over the placeholder/sed pattern for NEXT_PUBLIC_API_URL. NEXT_PUBLIC_* variables get inlined into the client bundle at next build time, which is normally a problem on a platform that only injects environment variables at container runtime (that exact workaround is documented in the Nexus project). Here, the deploy platform actually forwards configured variables as a Docker build ARG — confirmed directly from the build invocation — so the API URL is consumed the standard way (ARG → ENV, baked in at build time) instead of needing a runtime string-substitution step.

Known limitations (intentional, not overlooked)
No authentication on the API. Every endpoint is open — acceptable for a single-operator diagnostic tool with no real user data behind it, not a pattern that belongs anywhere real accounts or private data are involved.
The simulation is a seeded heuristic model, not real rigid-body physics. It reacts sensibly and consistently to every input (harder terrain, higher load, and excessive gain all degrade the result in the expected direction), but it's not a physics engine — that's a different project.
The four terrain scenarios are fixed at deploy time. They're declared directly in the CDK stack, not stored as data — adding a fifth today means a code change and a redeploy, not a UI action.
Single-key DynamoDB tables, no secondary index. Both tables are keyed only on id. Fetching a specific run by its ID works directly; listing every run for a given calibration would need a GSI that doesn't exist yet, since nothing in the current UI needs that query.
No integration tests against real AWS. The 14-test suite runs entirely against mocked AWS (moto) plus a cdk synth check in CI — real end-to-end behavior (the CORS-header bug, the Decimal conversion, the Docker HOSTNAME issue) was found by deploying and testing manually against the genuine services, not by an automated suite that exercises them.
Stack
Layer	Tech
Backend	Python, FastAPI, Mangum
Compute	AWS Lambda, Step Functions (Map state fan-out)
Database	DynamoDB (provisioned capacity)
API	API Gateway (Lambda proxy integration)
Infra as code	AWS CDK (Python)
Frontend	Next.js (App Router), TypeScript
Testing	pytest, moto (mocked AWS)
Infra (frontend)	Docker (multi-stage build), EasyPanel
Deployment notes

Backend and frontend deploy independently, to different platforms entirely — the backend to AWS via CDK, the frontend as a Docker container on the same shared VPS as the rest of this portfolio. That split means the two need each other's final URL to talk correctly (the frontend needs the API's real Gateway URL; the backend's CORS policy needs the frontend's real domain), which in practice means a first backend deploy, a frontend deploy pointed at its output, and a second backend deploy once the frontend's real domain is known.

DynamoDB is provisioned, not on-demand — see Technical decisions above for why that specific choice keeps this on AWS's Always Free tier indefinitely rather than for 12 months.
Lambda assets are built by a small script (backend/build.sh / build.ps1), not by CDK's Docker-based bundling — see Technical decisions above.
The frontend's Dockerfile sets HOSTNAME=0.0.0.0 explicitly and consumes NEXT_PUBLIC_API_URL as a build ARG — both were real deploy-time bugs before they were deliberate lines in the Dockerfile.
Running locally
bash
# Backend
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest -v                # 14 tests, fully mocked AWS
.venv/bin/uvicorn app.main:app --port 8000

# Infra (validates the CDK stack without touching real AWS)
cd infra
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cdk synth

# Frontend
cd frontend
npm install
npm run dev                        # http://localhost:3000, expects the API at :8000

Backend: http://localhost:8000 (interactive API docs at /docs) Frontend: http://localhost:3000

Project structure
hos-calibration-range/
├── backend/
│   ├── app/                 # FastAPI app, Pydantic models, simulation engine
│   ├── lambda_handlers/     # api_handler (Mangum), simulate_worker, aggregate_results
│   ├── tests/                # pytest + moto
│   └── build.sh / build.ps1  # Docker-free Lambda packaging
├── infra/
│   └── infra/hos_stack.py   # the entire AWS resource graph, in CDK (Python)
├── frontend/
│   ├── app/                  # Next.js App Router pages + styles
│   ├── lib/                   # API client, shared types
│   └── Dockerfile
└── .github/workflows/        # CI: tests + lint + cdk synth on every push; deploy on merge to main
Author

Built by Eiti Kobata as a portfolio project. HOS references the actual "Hyper Operating System" designation from the wider setting this project draws its theming from; every other in-UI term (servo response, gyro sensitivity, the four site names) is this project's own naming layered on top of it — no licensed characters, assets, or trademarked material reproduced.
