from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.db.session import check_db_connection
from app.schemas.health import AppHealthResponse, HealthCheck

APP_VERSION = "0.1.0"


def get_api_health() -> HealthCheck:
    return HealthCheck(status="ok", detail="API is responsive")


def get_database_health() -> HealthCheck:
    try:
        check_db_connection()
    except SQLAlchemyError as exc:
        return HealthCheck(status="degraded", detail=f"Database unavailable: {exc.__class__.__name__}")
    return HealthCheck(status="ok", detail="Database connection successful")


def get_app_health(include_database: bool = False) -> AppHealthResponse:
    database_status = get_database_health() if include_database else None
    return AppHealthResponse(
        name=settings.app_name,
        environment=settings.app_env,
        version=APP_VERSION,
        api_status=get_api_health(),
        database_status=database_status,
    )
