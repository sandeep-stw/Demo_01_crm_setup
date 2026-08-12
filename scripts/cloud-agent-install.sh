#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

export DOTNET_CLI_TELEMETRY_OPTOUT=1
export PATH="${HOME}/.dotnet/tools:${PATH}"

if ! command -v dotnet >/dev/null 2>&1; then
  echo "dotnet SDK is required but was not found in PATH." >&2
  exit 1
fi

if ! command -v pac >/dev/null 2>&1; then
  dotnet tool install --global Microsoft.PowerApps.CLI.Tool --version 1.38.3
fi

export PATH="${HOME}/.dotnet/tools:${PATH}"

pac help >/dev/null
node --version
dotnet --version
