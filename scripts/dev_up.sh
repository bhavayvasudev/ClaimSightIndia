#!/usr/bin/env bash
# Local dev bootstrap: starts Postgres+pgvector, backend, frontend via
# infra/docker-compose.yml. Copy .env.example to .env first.
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo "No .env found — copying .env.example. Fill in ANTHROPIC_API_KEY before continuing." >&2
  cp .env.example .env
fi

docker compose -f infra/docker-compose.yml up --build
