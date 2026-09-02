# HOS Calibration Range

Batch calibration testing for a Labor's actuator/stabilization tuning.
Configure a calibration, run it against a fixed set of terrain scenarios
in parallel, and see whether it improved or regressed against the
calibration's baseline.

## Architecture

Client -> API Gateway -> Lambda (FastAPI via Mangum) -> Step Functions
(fan-out across terrain scenarios via Map state) -> Lambda workers ->
aggregation Lambda -> DynamoDB.

Every piece of compute exists only while it's processing a request - no
server runs idle. See `infra/infra/hos_stack.py` for the full resource
list and the reasoning behind each choice (inline comments cover the
DynamoDB provisioned-vs-on-demand decision specifically, since that one
is what keeps this on AWS's Always Free tier).

## Local development

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest -v          # run tests
.venv/bin/ruff check app lambda_handlers tests   # lint
```

Run the API locally without touching AWS by setting
`CALIBRATIONS_TABLE` / `RUNS_TABLE` / `STATE_MACHINE_ARN` to point at
`localstack` or by mocking with `moto` (see `tests/conftest.py` for the
pattern the test suite already uses).

## Deploying

1. `aws configure` with an IAM user that has permission to deploy this
   stack (or use the GitHub Actions workflow, which expects
   `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` repo secrets).
2. **Set a billing alarm before your first deploy** - AWS Budgets, alert
   at $1. This is the actual safety net, not a suggestion to skip.
3. `cd backend && ./build.sh` (produces the Lambda deployment package)
4. `cd infra && cdk bootstrap` (first time only, per account/region)
5. `cd infra && cdk deploy`

CI (`.github/workflows/ci.yml`) runs tests, lint, and `cdk synth` on
every push/PR - never touches real AWS. Deploy
(`.github/workflows/deploy.yml`) only runs on merge to `main`.

## Cost

Designed to stay inside AWS's Always Free tier indefinitely:
Lambda, DynamoDB (provisioned, low capacity - see stack comments), and
Step Functions all have always-free allowances that don't expire after
12 months. API Gateway's REST API free tier is the one 12-month-limited
piece in this stack; at portfolio-demo traffic levels the actual cost
after that window is expected to be cents, not dollars, but it's the one
component worth watching on the AWS Billing dashboard.
