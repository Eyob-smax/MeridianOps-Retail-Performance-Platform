from contextlib import asynccontextmanager
import logging
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.router import api_router
from app.api.v1.endpoints.operations import register_scheduler
from app.core.config import settings
from app.core.security import assert_password_hashing_backend_ready
from app.services.scheduler_service import NightlyScheduler


scheduler = NightlyScheduler(run_hour_utc=settings.scheduler_kpi_hour_utc)
logger = logging.getLogger(__name__)


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "") or request.headers.get("X-Request-ID") or uuid4().hex


def _http_error_code(status_code: int) -> str:
    mapping = {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        422: "validation_error",
        500: "internal_server_error",
    }
    return mapping.get(status_code, "http_error")


def _build_error_payload(
    *,
    request: Request,
    status_code: int,
    detail: str,
    validation_errors: list[dict] | None = None,
) -> dict:
    payload = {
        "detail": detail,
        "error_code": _http_error_code(status_code),
        "status_code": status_code,
        "path": request.url.path,
        "request_id": _request_id(request),
    }
    if validation_errors is not None:
        payload["errors"] = validation_errors
    return payload


@asynccontextmanager
async def lifespan(_: FastAPI):
    assert_password_hashing_backend_ready()
    if settings.scheduler_enabled and settings.scheduler_start_on_boot:
        scheduler.start()
    try:
        yield
    finally:
        scheduler.stop()


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

    @app.middleware("http")
    async def attach_request_id(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid4().hex
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException):
        detail = exc.detail if isinstance(exc.detail, str) else "Request failed"
        payload = _build_error_payload(request=request, status_code=exc.status_code, detail=detail)
        return JSONResponse(
            status_code=exc.status_code,
            content=payload,
            headers={"X-Request-ID": payload["request_id"]},
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_exception(request: Request, exc: RequestValidationError):
        payload = _build_error_payload(
            request=request,
            status_code=422,
            detail="Validation failed",
            validation_errors=exc.errors(),
        )
        return JSONResponse(
            status_code=422,
            content=payload,
            headers={"X-Request-ID": payload["request_id"]},
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_exception(request: Request, exc: Exception):
        logger.exception("Unhandled API exception", exc_info=exc)
        payload = _build_error_payload(
            request=request,
            status_code=500,
            detail="Internal server error",
        )
        return JSONResponse(
            status_code=500,
            content=payload,
            headers={"X-Request-ID": payload["request_id"]},
        )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.backend_cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router)

    register_scheduler(scheduler)

    return app


app = create_app()
