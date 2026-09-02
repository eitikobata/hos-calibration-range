# PowerShell version of build.sh - same job, Windows-native.
# Installs backend dependencies into backend/build/ as Lambda-compatible
# manylinux wheels (numpy needs this - it ships compiled code, and a
# wheel built for Windows won't run inside AWS Lambda's Linux runtime).
# Run this from inside the backend/ folder: .\build.ps1

Set-Location $PSScriptRoot

Remove-Item -Recurse -Force build -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path build | Out-Null

.venv\Scripts\pip install `
  --quiet `
  --platform manylinux2014_x86_64 `
  --target build `
  --implementation cp `
  --python-version 3.12 `
  --only-binary=:all: `
  -r requirements.txt

# boto3/botocore ship pre-installed in every Python Lambda runtime -
# bundling our own copy just bloats the zip for no benefit.
Get-ChildItem build -Filter "boto3*" | Remove-Item -Recurse -Force
Get-ChildItem build -Filter "botocore*" | Remove-Item -Recurse -Force
Get-ChildItem build -Filter "s3transfer*" | Remove-Item -Recurse -Force

Copy-Item -Recurse app build\
Copy-Item -Recurse lambda_handlers build\

$size = (Get-ChildItem build -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB
Write-Host "Build output: backend\build\ ($([math]::Round($size, 1)) MB)"