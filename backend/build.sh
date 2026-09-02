#!/usr/bin/env bash
# Builds the Lambda deployment package: backend/build/ ends up containing
# app/, lambda_handlers/, and every third-party dependency flattened into
# the same directory (Lambda's expected layout - imports resolve exactly
# like they do locally, no separate "layer" indirection to reason about).
#
# Runs pip with --platform/--only-binary so the packages installed here
# are Lambda-compatible manylinux wheels, even when this script runs on a
# different OS (e.g. macOS) - most relevant for numpy, which ships
# compiled C extensions that are NOT portable across platforms.
#
# CDK's own Docker-based asset bundling was deliberately avoided (it
# requires a running Docker daemon on every machine that deploys, local
# or CI). This script needs only Python + pip, which both this
# environment and GitHub Actions already have.
set -euo pipefail

cd "$(dirname "$0")"
rm -rf build
mkdir -p build

pip install \
  --quiet \
  --platform manylinux2014_x86_64 \
  --target build \
  --implementation cp \
  --python-version 3.12 \
  --only-binary=:all: \
  -r requirements.txt

# boto3/botocore ship pre-installed in every Python Lambda runtime.
# Bundling our own copy just bloats the zip for no benefit - about 30MB
# saved here, and it avoids a version mismatch between what we bundled
# and what AWS actually runs (the runtime's boto3 always wins anyway).
rm -rf build/boto3 build/botocore build/boto3-* build/botocore-* build/s3transfer build/s3transfer-*

cp -r app build/
cp -r lambda_handlers build/

echo "Build output: backend/build/ ($(du -sh build | cut -f1))"
