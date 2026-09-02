"""
FastAPI app. This file is intentionally infrastructure-agnostic - it
doesn't know it's going to run inside a Lambda. That's on purpose: the
same `app` object here can run locally with `uvicorn app.main:app --reload`
for fast iteration, and gets wrapped by Mangum in
lambda_handlers/api_handler.py for the deployed version. Keeping AWS-specific
code out of this file is what makes that possible.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import boto3
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.dynamo_utils import to_dynamo_safe
from app.models import (
    CalibrationConfig,
    CalibrationRunRequest,
    CalibrationRunSummary,
)

app = FastAPI(title="HOS Calibration Range", version="0.1.0")

# CORS: wide open to localhost for local dev only. Browsers block
# cross-origin fetches by default (the frontend runs on :3000, the API on
# :8000 - different origin even though both are "localhost"), so without
# this the frontend's requests fail silently in the browser console, not
# with a Python error here. Tighten allow_origins to the real deployed
# frontend domain before this ever goes to production - "*" or a
# wildcard localhost list is a local-only convenience, not a prod setting.
_ALLOWED_ORIGINS = ["https://hos.eitikobata.com"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """
    Without this, an unhandled exception (like the NoRegionError this
    caught on first real test) produces Starlette's default plaintext 500
    response. Worse: a handler registered for the bare `Exception` class
    specifically runs inside Starlette's ServerErrorMiddleware, which
    sits OUTSIDE CORSMiddleware in the stack (this is Starlette's fixed
    architecture, not something add_middleware ordering controls) - so
    CORSMiddleware never gets a chance to decorate this response with
    Access-Control-Allow-Origin. Browsers then report the failure as a
    CORS error, not as a 500, hiding the real cause from whoever's
    debugging the frontend (confirmed here: the header was genuinely
    absent from a real response, not just untested theory). The fix is
    to set the header by hand for exactly this one response path.

    Returning str(exc) to the client is fine for this project (a local
    portfolio demo debugged by its own author) but would leak internals
    in a real production API - swap for a generic message + server-side
    logging before this ever fronts real user traffic.
    """
    response = JSONResponse(status_code=500, content={"detail": str(exc)})
    origin = request.headers.get("origin")
    if origin in _ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
    return response

_CALIBRATIONS_TABLE = os.environ.get("CALIBRATIONS_TABLE", "")
_RUNS_TABLE = os.environ.get("RUNS_TABLE", "")
_STATE_MACHINE_ARN = os.environ.get("STATE_MACHINE_ARN", "")
# AWS_REGION is set automatically inside every real Lambda invocation, so
# this default only matters for local dev (running via uvicorn without
# `aws configure` yet). us-east-1 matches what the CDK stack deploys to.
_AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

# boto3 clients are created lazily and cached, not at import time. Import
# time is when pytest collects this module for local unit tests, which
# don't have AWS credentials configured - eagerly touching boto3 there
# would break tests that never actually call an AWS API.
_dynamodb = None
_sfn = None


def _get_dynamodb():
    global _dynamodb
    if _dynamodb is None:
        _dynamodb = boto3.resource("dynamodb", region_name=_AWS_REGION)
    return _dynamodb


def _get_sfn():
    global _sfn
    if _sfn is None:
        _sfn = boto3.client("stepfunctions", region_name=_AWS_REGION)
    return _sfn


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/calibrations", status_code=201)
def create_calibration(config: CalibrationConfig) -> dict:
    calibration_id = str(uuid.uuid4())
    table = _get_dynamodb().Table(_CALIBRATIONS_TABLE)
    table.put_item(
        Item={
            "id": calibration_id,
            "config": to_dynamo_safe(config.model_dump()),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    return {"id": calibration_id}


@app.post("/calibrations/{calibration_id}/run", status_code=202)
def trigger_run(calibration_id: str, body: CalibrationRunRequest) -> dict:
    run_id = str(uuid.uuid4())
    execution_input = {
        "run_id": run_id,
        "calibration_id": calibration_id,
        "config": body.config.model_dump(),
    }

    runs_table = _get_dynamodb().Table(_RUNS_TABLE)
    runs_table.put_item(
        Item={
            "id": run_id,
            "calibration_id": calibration_id,
            "status": "RUNNING",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )

    _get_sfn().start_execution(
        stateMachineArn=_STATE_MACHINE_ARN,
        name=run_id,
        input=__import__("json").dumps(execution_input),
    )

    return {"run_id": run_id, "status": "RUNNING"}


@app.get("/runs/{run_id}", response_model=CalibrationRunSummary)
def get_run(run_id: str) -> CalibrationRunSummary:
    runs_table = _get_dynamodb().Table(_RUNS_TABLE)
    item = runs_table.get_item(Key={"id": run_id}).get("Item")
    if item is None:
        raise HTTPException(status_code=404, detail="Run not found")

    return CalibrationRunSummary(
        run_id=item["id"],
        calibration_id=item["calibration_id"],
        status=item["status"],
        average_stability_margin=item.get("average_stability_margin"),
        worst_case_stability_margin=item.get("worst_case_stability_margin"),
        regression_vs_baseline=item.get("regression_vs_baseline"),
        results=item.get("results", []),
    )
    