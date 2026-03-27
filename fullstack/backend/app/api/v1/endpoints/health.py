from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.schemas.health import AppHealthResponse
from app.services.health_service import get_app_health

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=AppHealthResponse)
def health() -> AppHealthResponse:
    return get_app_health(include_database=False)


@router.get("/database", response_model=AppHealthResponse)
def health_database() -> AppHealthResponse | JSONResponse:
    payload = get_app_health(include_database=True)
    if payload.database_status and payload.database_status.status != "ok":
        return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=payload.model_dump())
    return payload
