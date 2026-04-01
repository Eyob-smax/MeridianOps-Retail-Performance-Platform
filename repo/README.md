# MeridianOps Docker Workflow

## Start Backend + Frontend + Database

```bash
docker compose -f docker-compose.yml up --build -d
```

Services:

- Backend API: http://localhost:8000/api/v1/health
- Frontend app: http://localhost:5173
- Postgres: localhost:5432

## Run Tests Sequentially (Backend -> Frontend)

Run this after the app stack is up:

```bash
docker compose -f docker-compose.yml --profile test run --rm backend-tests && docker compose -f docker-compose.yml --profile test run --rm frontend-tests
```

Important: do not use `up --abort-on-container-exit` for sequential tests. That mode can stop the second test container early (exit code 137) when the first test container exits.

What this does:

- Runs backend tests first and stops on failure.
- The backend test container also executes the PostgreSQL locking/concurrency suite by default through `POSTGRES_TEST_DATABASE_URL`.
- Runs frontend tests only if backend tests pass.
- Returns non-zero exit code on failure.

## Docker-Only Policy

This project must be started, tested, and validated using Docker Compose only.

Do not run backend or frontend directly on the host machine for acceptance/runtime verification.

Notes:

- Backend PostgreSQL locking tests are skipped only when `POSTGRES_TEST_DATABASE_URL` is not configured.
- In the Docker test profile, `POSTGRES_TEST_DATABASE_URL` is preconfigured in Compose to execute PostgreSQL locking tests in `backend-tests`.

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
