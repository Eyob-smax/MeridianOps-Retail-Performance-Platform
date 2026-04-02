#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

COMPOSE_CMD=(docker compose -f docker-compose.yml --profile test)
APP_SERVICES_REGEX='^(db|backend|frontend)$'
APP_WAS_RUNNING=0

detect_running_app_stack() {
	local running_services
	running_services="$("${COMPOSE_CMD[@]}" ps --services --status running 2>/dev/null || true)"

	while IFS= read -r service; do
		[[ -z "$service" ]] && continue
		if [[ "$service" =~ $APP_SERVICES_REGEX ]]; then
			APP_WAS_RUNNING=1
			break
		fi
	done <<< "$running_services"
}

cleanup() {
	local exit_code=$?
	if [[ "$APP_WAS_RUNNING" -eq 1 ]]; then
		echo "Leaving existing docker services running."
	else
		echo "Stopping docker services..."
		"${COMPOSE_CMD[@]}" down --remove-orphans >/dev/null 2>&1 || true
	fi

	trap - EXIT
	exit "$exit_code"
}

trap cleanup EXIT

detect_running_app_stack

# Remove stale stopped test containers without touching app services.
"${COMPOSE_CMD[@]}" rm -f -s backend-tests frontend-tests >/dev/null 2>&1 || true

echo "Running backend suite (SQLite fast path + mandatory PostgreSQL locking)..."
"${COMPOSE_CMD[@]}" run --build --rm -e REQUIRE_POSTGRES_LOCKING_TESTS=1 backend-tests

echo "Running frontend suite..."
"${COMPOSE_CMD[@]}" run --build --rm frontend-tests

echo "All dockerized tests passed."
