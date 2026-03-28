#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

echo "Running backend suite (SQLite fast path)..."
docker compose -f docker-compose.yml --profile test run --rm backend-tests

echo "Running frontend suite..."
docker compose -f docker-compose.yml --profile test run --rm frontend-tests

echo "All dockerized tests passed."
