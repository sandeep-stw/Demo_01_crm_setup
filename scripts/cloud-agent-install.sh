#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

export DOTNET_ROOT="${DOTNET_ROOT:-$HOME/.dotnet}"
export DOTNET_CLI_TELEMETRY_OPTOUT=1
export PATH="${DOTNET_ROOT}:${DOTNET_ROOT}/tools:${PATH}"

install_dotnet_sdk() {
  local install_script
  install_script="$(mktemp)"
  curl -fsSL https://dot.net/v1/dotnet-install.sh -o "${install_script}"
  bash "${install_script}" --channel 9.0
  rm -f "${install_script}"
  export PATH="${DOTNET_ROOT}:${DOTNET_ROOT}/tools:${PATH}"
}

if [ ! -x "${DOTNET_ROOT}/dotnet" ]; then
  install_dotnet_sdk
fi

export PATH="${DOTNET_ROOT}:${DOTNET_ROOT}/tools:${PATH}"

if ! command -v pac >/dev/null 2>&1; then
  dotnet tool install --global Microsoft.PowerApps.CLI.Tool --version 1.38.3
fi

export PATH="${DOTNET_ROOT}/tools:${PATH}"

pac help >/dev/null
node --version
dotnet --version
