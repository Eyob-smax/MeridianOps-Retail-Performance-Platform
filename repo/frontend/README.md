# MeridianOps Frontend (Vue 3 + TypeScript + Vite)

Single-page UI for campaign operations, loyalty/member workflows, training, inventory, attendance, and analytics dashboards.

## Runtime Policy

Frontend runtime and tests are Docker-only for this project.

Do not run `npm install`, `npm run dev`, `npm run test`, or `npm run build` directly on the host for project acceptance.

## Start Full Stack (Docker)

```bash
docker compose -f docker-compose.yml up --build -d
```

## Run Frontend Tests (Docker)

```bash
docker compose -f docker-compose.yml --profile test run --rm frontend-tests
```

## Run Full Test Sequence (Docker)

```bash
docker compose -f docker-compose.yml --profile test run --rm backend-tests && docker compose -f docker-compose.yml --profile test run --rm frontend-tests
```

## Stop Stack

```bash
docker compose -f docker-compose.yml down
```

For complete project workflow details, use the main guide in `repo/README.md`.
