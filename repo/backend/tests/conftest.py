import os
from inspect import signature

import httpx

# Starlette TestClient in this repository passes `app=...` to httpx.Client,
# but newer httpx versions removed that keyword. This shim keeps tests portable.
if "app" not in signature(httpx.Client.__init__).parameters:
    _orig_client_init = httpx.Client.__init__

    def _patched_client_init(self, *args, app=None, **kwargs):  # type: ignore[no-redef]
        return _orig_client_init(self, *args, **kwargs)

    httpx.Client.__init__ = _patched_client_init  # type: ignore[assignment]


os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.services.auth_service import ensure_seed_users

# Ensure SQLAlchemy metadata has all mapped classes before create_all.
from app.db import models as _models  # noqa: F401


@pytest.fixture
def db_engine():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session_factory(db_engine):
    return sessionmaker(bind=db_engine, autoflush=False, autocommit=False, class_=Session)


@pytest.fixture
def client(db_session_factory) -> TestClient:
    seed_db = db_session_factory()
    ensure_seed_users(seed_db, password="ChangeMeNow123")
    seed_db.commit()
    seed_db.close()

    def override_get_db():
        db = db_session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def db_session(db_session_factory) -> Session:
    db = db_session_factory()
    try:
        yield db
    finally:
        db.close()
