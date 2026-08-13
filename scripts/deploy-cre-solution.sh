#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

export DOTNET_ROOT="${DOTNET_ROOT:-$HOME/.dotnet}"
export PATH="${DOTNET_ROOT}:${DOTNET_ROOT}/tools:${PATH}"

if [ -f ./scripts/cloud-agent-start.sh ]; then
  ./scripts/cloud-agent-start.sh
fi

python3 ./scripts/deploy-cre-model.py

if command -v pac >/dev/null 2>&1; then
  echo "Packing solution project..."
  dotnet build ./solutions/CreRelationshipManagement/CreRelationshipManagement.cdsproj
  pac solution import --path ./solutions/CreRelationshipManagement/bin/Debug
fi
