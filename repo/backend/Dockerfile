FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --upgrade pip \
    && pip install ".[dev]"

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
COPY tests ./tests

RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app
USER appuser

FROM base AS runtime
ENV APP_ENV=docker \
    DATABASE_URL=postgresql+psycopg://postgres:postgres@db:5432/meridianops \
    BACKEND_CORS_ORIGINS=http://localhost:5173 \
    SCHEDULER_ENABLED=false \
    SCHEDULER_START_ON_BOOT=false
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]

FROM base AS test
ENV APP_ENV=test \
    DATABASE_URL=sqlite+pysqlite:///:memory: \
    POSTGRES_TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@db:5432/meridianops \
    SCHEDULER_ENABLED=false \
    SCHEDULER_START_ON_BOOT=false
CMD ["python", "-m", "pytest"]
