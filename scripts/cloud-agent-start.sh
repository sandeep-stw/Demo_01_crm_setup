#!/usr/bin/env bash
set -euo pipefail

export DOTNET_ROOT="${DOTNET_ROOT:-$HOME/.dotnet}"
export PATH="${DOTNET_ROOT}:${DOTNET_ROOT}/tools:${PATH}"

if ! command -v pac >/dev/null 2>&1; then
  echo "Power Platform CLI (pac) is not installed." >&2
  exit 1
fi

if [ -n "${AZURE_CLIENT_ID:-}" ] && [ -n "${AZURE_CLIENT_SECRET:-}" ] && [ -n "${AZURE_TENANT_ID:-}" ]; then
  auth_args=(
    --name "cloud-agent"
    --applicationId "${AZURE_CLIENT_ID}"
    --clientSecret "${AZURE_CLIENT_SECRET}"
    --tenant "${AZURE_TENANT_ID}"
  )

  if [ -n "${DATAVERSE_ENVIRONMENT_URL:-}" ]; then
    auth_args+=(--environment "${DATAVERSE_ENVIRONMENT_URL}")
  fi

  if ! pac auth list 2>/dev/null | grep -q "cloud-agent"; then
    pac auth create "${auth_args[@]}"
  else
    pac auth select --name "cloud-agent"
  fi
fi

if pac auth who >/dev/null 2>&1; then
  echo "Connected to Dynamics 365 / Dataverse:"
  pac auth who
  pac env who
else
  echo "Dynamics 365 tooling is installed. Configure Azure app registration secrets to connect."
  echo "Required secrets: AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, DATAVERSE_ENVIRONMENT_URL"
fi
