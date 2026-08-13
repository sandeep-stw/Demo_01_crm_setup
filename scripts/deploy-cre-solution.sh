#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

export DOTNET_ROOT="${DOTNET_ROOT:-$HOME/.dotnet}"
export PATH="${DOTNET_ROOT}:${DOTNET_ROOT}/tools:${PATH}"

if [ -f ./scripts/cloud-agent-start.sh ]; then
  timeout 120 ./scripts/cloud-agent-start.sh || echo "Warning: start script timed out or failed; continuing with deploy."
fi

if command -v dotnet >/dev/null 2>&1; then
  dotnet build ./solutions/CreRelationshipManagement/CreRelationshipManagement.cdsproj
fi

python3 ./scripts/deploy-cre-model.py
python3 ./scripts/add-cre-to-solution.py
python3 ./scripts/deploy-cre-app.py
python3 ./scripts/deploy-cre-lead-flow.py

if command -v pac >/dev/null 2>&1 && pac auth list 2>/dev/null | grep -q cloud-agent; then
  echo "Syncing solution project from environment..."
  pac solution sync --solution-folder ./solutions/CreRelationshipManagement/src
fi
