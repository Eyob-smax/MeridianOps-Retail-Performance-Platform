# MeridianOps Docker Workflow

## Local (Non-Docker) Quick Start

Backend (Python 3.12+):

```bash
cd fullstack/backend
python -m venv .venv
source .venv/Scripts/activate
python -m pip install -U pip
python -m pip install -e .[dev]
```

Run backend tests locally:

```bash
cd fullstack/backend
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q
```

Frontend:

```bash
cd fullstack/frontend
npm install
npm test -- --pool=forks
```

Notes:

- `--pool=forks` avoids worker-thread startup issues seen on some local environments.
- Non-Docker local tests do not require changing application source code.

## Start Backend + Frontend + Database

```bash
docker compose -f fullstack/docker-compose.yml up --build -d
```

Services:

- Backend API: http://localhost:8000/api/v1/health
- Frontend app: http://localhost:5173
- Postgres: localhost:5432

## Run Tests Sequentially (Backend -> Frontend)

Run this after the app stack is up:

```bash
docker compose -f fullstack/docker-compose.yml --profile test run --rm backend-tests && docker compose -f fullstack/docker-compose.yml --profile test run --rm frontend-tests
```

Important: do not use `up --abort-on-container-exit` for sequential tests. That mode can stop the second test container early (exit code 137) when the first test container exits.

What this does:

- Runs backend tests first and stops on failure.
- Runs frontend tests only if backend tests pass.
- Returns non-zero exit code on failure.

## Run Individual Test Suites In Docker

Backend only:

```bash
docker compose -f fullstack/docker-compose.yml --profile test run --rm backend-tests
```

Frontend only:

```bash
docker compose -f fullstack/docker-compose.yml --profile test run --rm frontend-tests
```

## One-Command Test Runners

From project root:

```bash
bash fullstack/run-tests.sh
```

PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File fullstack/run-tests.ps1
```

## Full Production Validation Flow

```bash
docker compose -f fullstack/docker-compose.yml up --build -d
docker compose -f fullstack/docker-compose.yml --profile test run --rm backend-tests && docker compose -f fullstack/docker-compose.yml --profile test run --rm frontend-tests
docker compose -f fullstack/docker-compose.yml down
```

## Stop Everything

```bash
docker compose -f fullstack/docker-compose.yml down
```

To remove the database volume too:

```bash
docker compose -f fullstack/docker-compose.yml down -v
```
