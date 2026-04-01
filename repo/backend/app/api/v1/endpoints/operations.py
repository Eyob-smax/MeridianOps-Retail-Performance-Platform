from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user, require_roles
from app.core.errors import bad_request, forbidden
from app.db.session import get_db
from app.schemas.auth import AuthUser
from app.schemas.kpi import (
    KPIBackfillRequest,
    KPIBackfillResponse,
    KPIDailyMetricResponse,
    KPIJobRunResponse,
    SchedulerStatusResponse,
    SeedDataResponse,
)
from app.services.kpi_service import build_scheduler_status, list_kpi_metrics, list_kpi_runs, run_kpi_materialization
from app.services.scheduler_service import NightlyScheduler, resolve_kpi_store_ids
from app.services.seed_service import seed_demo_data

router = APIRouter(prefix="/ops", tags=["operations"])

_ADMIN_MANAGER_ROLES = {"administrator", "store_manager"}
_scheduler: NightlyScheduler | None = None


def _scoped_store_ids(current_user: AuthUser, requested_store_ids: list[int] | None, db: Session) -> list[int]:
    if "administrator" in current_user.roles:
        return requested_store_ids if requested_store_ids else resolve_kpi_store_ids(db)
    if "store_manager" in current_user.roles:
        if current_user.store_id is None:
            raise forbidden("Store manager has no assigned store scope")
        if requested_store_ids:
            invalid = [store_id for store_id in requested_store_ids if store_id != current_user.store_id]
            if invalid:
                raise forbidden("Store manager cannot access other stores")
            return [current_user.store_id]
        return [current_user.store_id]
    raise forbidden()


def register_scheduler(scheduler: NightlyScheduler) -> None:
    global _scheduler
    _scheduler = scheduler


@router.get("/scheduler/status", response_model=SchedulerStatusResponse)
def scheduler_status(
    _: AuthUser = Depends(require_roles(_ADMIN_MANAGER_ROLES)),
    db: Session = Depends(get_db),
) -> SchedulerStatusResponse:
    scheduler = _scheduler
    enabled = bool(scheduler and scheduler.enabled)
    next_run_at = scheduler.next_run_at if scheduler else None
    return build_scheduler_status(db, enabled=enabled, next_run_at=next_run_at)


@router.post("/scheduler/start", response_model=SchedulerStatusResponse)
def scheduler_start(
    _: AuthUser = Depends(require_roles({"administrator"})),
    db: Session = Depends(get_db),
) -> SchedulerStatusResponse:
    scheduler = _scheduler
    if not scheduler:
        raise bad_request("Scheduler is not available")
    scheduler.start()
    return build_scheduler_status(db, enabled=scheduler.enabled, next_run_at=scheduler.next_run_at)


@router.post("/scheduler/stop", response_model=SchedulerStatusResponse)
def scheduler_stop(
    _: AuthUser = Depends(require_roles({"administrator"})),
    db: Session = Depends(get_db),
) -> SchedulerStatusResponse:
    scheduler = _scheduler
    if not scheduler:
        raise bad_request("Scheduler is not available")
    scheduler.stop()
    return build_scheduler_status(db, enabled=scheduler.enabled, next_run_at=scheduler.next_run_at)


@router.post("/kpi/backfill", response_model=KPIBackfillResponse)
def kpi_backfill(
    payload: KPIBackfillRequest,
    current_user: AuthUser = Depends(get_current_user),
    _: AuthUser = Depends(require_roles(_ADMIN_MANAGER_ROLES)),
    db: Session = Depends(get_db),
) -> KPIBackfillResponse:
    try:
        scoped_store_ids = _scoped_store_ids(current_user, payload.store_ids if payload.store_ids else None, db)
        run = run_kpi_materialization(
            db,
            start_date=payload.start_date,
            end_date=payload.end_date,
            trigger_type="manual",
            actor_user_id=current_user.id,
            store_ids=scoped_store_ids,
        )
        db.commit()
        return KPIBackfillResponse(
            run_id=run.id,
            status=run.status,
            processed_from_date=run.processed_from_date,
            processed_to_date=run.processed_to_date,
            records_written=run.records_written,
        )
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        if isinstance(exc, HTTPException):
            raise exc
        raise bad_request(str(exc))


@router.get("/kpi/runs", response_model=list[KPIJobRunResponse])
def kpi_runs(
    limit: int = Query(default=50, ge=1, le=200),
    _: AuthUser = Depends(require_roles(_ADMIN_MANAGER_ROLES)),
    db: Session = Depends(get_db),
) -> list[KPIJobRunResponse]:
    runs = list_kpi_runs(db, limit=limit)
    return [
        KPIJobRunResponse(
            id=run.id,
            job_name=run.job_name,
            trigger_type=run.trigger_type,
            status=run.status,
            scheduled_for=run.scheduled_for,
            started_at=run.started_at,
            finished_at=run.finished_at,
            attempts_made=run.attempts_made,
            max_attempts=run.max_attempts,
            processed_from_date=run.processed_from_date,
            processed_to_date=run.processed_to_date,
            records_written=run.records_written,
            error_message=run.error_message,
        )
        for run in runs
    ]


@router.get("/kpi/metrics", response_model=list[KPIDailyMetricResponse])
def kpi_metrics(
    start_date: date = Query(...),
    end_date: date = Query(...),
    store_id: int | None = Query(default=None),
    current_user: AuthUser = Depends(get_current_user),
    _: AuthUser = Depends(require_roles(_ADMIN_MANAGER_ROLES)),
    db: Session = Depends(get_db),
) -> list[KPIDailyMetricResponse]:
    if end_date < start_date:
        raise bad_request("end_date must be on or after start_date")

    scoped_store_ids = _scoped_store_ids(current_user, [store_id] if store_id is not None else None, db)
    if "administrator" in current_user.roles:
        metrics = list_kpi_metrics(db, start_date, end_date, store_id=store_id)
    else:
        metrics = []
        for scoped_store_id in scoped_store_ids:
            metrics.extend(list_kpi_metrics(db, start_date, end_date, store_id=scoped_store_id))
        metrics.sort(key=lambda item: (item.business_date, item.store_id))
    return [
        KPIDailyMetricResponse(
            id=metric.id,
            business_date=metric.business_date,
            store_id=metric.store_id,
            conversion_rate=str(metric.conversion_rate),
            average_order_value=str(metric.average_order_value),
            inventory_turnover=str(metric.inventory_turnover),
            total_attempts=metric.total_attempts,
            successful_orders=metric.successful_orders,
            revenue_total=str(metric.revenue_total),
            inventory_outbound_qty=str(metric.inventory_outbound_qty),
            average_inventory_qty=str(metric.average_inventory_qty),
        )
        for metric in metrics
    ]


@router.post("/seed/demo", response_model=SeedDataResponse)
def seed_demo(
    current_user: AuthUser = Depends(get_current_user),
    _: AuthUser = Depends(require_roles({"administrator"})),
    db: Session = Depends(get_db),
) -> SeedDataResponse:
    try:
        result = seed_demo_data(db, current_user)
        db.commit()
        return SeedDataResponse(**result)
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        raise bad_request(str(exc))
