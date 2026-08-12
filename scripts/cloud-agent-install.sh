#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

npm ci
npx prisma db push --skip-generate
