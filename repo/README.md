# MeridianOps Docker Workflow

## Start Backend + Frontend + Database

```bash
docker compose -f docker-compose.yml up --build -d
```

Or use the helper script:

```bash
./run_app.sh
```

This starts the application in detached mode and exits the terminal command while containers keep running.

Services:

- Backend API: http://localhost:8000/api/v1/health
- Frontend app: http://localhost:5173
- Postgres: localhost:5432

## Run Tests Sequentially (Backend -> Frontend)

Run this after the app stack is up:

```bash
./run_tests.sh
```

The test runner exits when done. If app services were already running before tests, they stay running.

Important: do not use `up --abort-on-container-exit` for sequential tests. That mode can stop the second test container early (exit code 137) when the first test container exits.

What this does:

- Runs backend tests first and stops on failure.
- The backend test container executes the PostgreSQL locking/concurrency suite and fails if that suite would be skipped.
- Runs frontend tests only if backend tests pass.
- Returns non-zero exit code on failure.

## Docker-Only Policy

This project must be started, tested, and validated using Docker Compose only.

Do not run backend or frontend directly on the host machine for acceptance/runtime verification.

Notes:

- Backend PostgreSQL locking tests fail (instead of skip) when `REQUIRE_POSTGRES_LOCKING_TESTS=1` or `CI=true` and `POSTGRES_TEST_DATABASE_URL` is missing.
- `run_tests.sh` sets `REQUIRE_POSTGRES_LOCKING_TESTS=1` for `backend-tests`, enforcing the locking suite in CI and local Docker runs.

## Run Individual Test Suites In Docker

Backend only:

```bash
docker compose -f docker-compose.yml --profile test run --rm backend-tests
```

Frontend only:

```bash
docker compose -f docker-compose.yml --profile test run --rm frontend-tests
```

## Stop Everything

```bash
docker compose -f docker-compose.yml down
```

To remove the database volume too:

```bash
docker compose -f docker-compose.yml down -v
```
