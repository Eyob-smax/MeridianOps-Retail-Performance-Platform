import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.masking import mask_record
from app.db.models import CouponRedemptionEvent, InventoryLedger, KPIDailyMetric, KPIJobRun
from app.services.audit_service import audit_event

KPI_JOB_NAME = "nightly_kpi_materialization"
MAX_RETRIES = 3


def _date_range(start_date: date, end_date: date) -> list[date]:
    days: list[date] = []
    current = start_date
    while current <= end_date:
        days.append(current)
        current += timedelta(days=1)
    return days


def _base_attempts(day: date, store_id: int) -> int:
    return 90 + ((day.toordinal() + store_id) % 75)


def _store_from_order_reference(reference: str | None) -> int:
    if not reference:
        return 0
    upper = reference.upper()
    if "DOWNTOWN" in upper:
        return 101
    if "AIRPORT" in upper:
        return 102
    if "WEST" in upper:
        return 103
    if "NORTH" in upper:
        return 104
    if "HARBOR" in upper:
        return 105
    if "UNIVERSITY" in upper:
        return 106
    if upper.startswith("S") and len(upper) >= 4 and upper[1:4].isdigit():
        return int(upper[1:4])
    return 0


def _read_conversion_and_aov(db: Session, business_date: date, store_id: int) -> tuple[int, int, Decimal]:
    rows = db.execute(
        select(CouponRedemptionEvent).where(func.date(CouponRedemptionEvent.created_at) == str(business_date))
    ).scalars()

    successful_orders = 0
    revenue_total = Decimal("0.00")
    total_attempts = _base_attempts(business_date, store_id)

    for row in rows:
        derived_store_id = _store_from_order_reference(row.order_reference)
        if store_id != 0 and derived_store_id not in {0, store_id}:
            continue
        if row.status != "success":
            continue
        successful_orders += 1
        revenue_total += Decimal(row.pre_tax_amount) - Decimal(row.discount_amount)

    if successful_orders > total_attempts:
        total_attempts = successful_orders

    return total_attempts, successful_orders, revenue_total.quantize(Decimal("0.01"))


def _read_inventory_turnover(db: Session, business_date: date, store_id: int) -> tuple[Decimal, Decimal, Decimal]:
    rows = db.execute(
        select(InventoryLedger).where(func.date(InventoryLedger.created_at) == str(business_date))
    ).scalars()

    inbound_qty = Decimal("0.000")
    outbound_qty = Decimal("0.000")

    for row in rows:
        row_store_id = row.store_id if row.store_id is not None else row.location_id
        if store_id != 0 and row_store_id != store_id:
            continue
        qty = Decimal(row.quantity_delta)
        if qty > 0:
            inbound_qty += qty
        if qty < 0:
            outbound_qty += abs(qty)

    average_inventory_qty = ((inbound_qty + outbound_qty + Decimal("1.000")) / Decimal("2")).quantize(Decimal("0.001"))
    inventory_turnover = (outbound_qty / average_inventory_qty).quantize(Decimal("0.0001"))
    return outbound_qty.quantize(Decimal("0.001")), average_inventory_qty, inventory_turnover


def _upsert_metric(
    db: Session,
    *,
    run_id: int,
    business_date: date,
    store_id: int,
    total_attempts: int,
    successful_orders: int,
    revenue_total: Decimal,
    inventory_outbound_qty: Decimal,
    average_inventory_qty: Decimal,
    inventory_turnover: Decimal,
) -> None:
    existing = db.execute(
        select(KPIDailyMetric).where(
            KPIDailyMetric.business_date == business_date,
            KPIDailyMetric.store_id == store_id,
        )
    ).scalar_one_or_none()

    conversion_rate = Decimal("0.0000")
    if total_attempts > 0:
        conversion_rate = (Decimal(successful_orders) / Decimal(total_attempts)).quantize(Decimal("0.0001"))

    average_order_value = Decimal("0.00")
    if successful_orders > 0:
        average_order_value = (revenue_total / Decimal(successful_orders)).quantize(Decimal("0.01"))

    if existing:
        existing.conversion_rate = conversion_rate
        existing.average_order_value = average_order_value
        existing.inventory_turnover = inventory_turnover
        existing.total_attempts = total_attempts
        existing.successful_orders = successful_orders
        existing.revenue_total = revenue_total
        existing.inventory_outbound_qty = inventory_outbound_qty
        existing.average_inventory_qty = average_inventory_qty
        existing.run_id = run_id
        existing.generated_at = datetime.now(timezone.utc)
        return

    db.add(
        KPIDailyMetric(
            business_date=business_date,
            store_id=store_id,
            conversion_rate=conversion_rate,
            average_order_value=average_order_value,
            inventory_turnover=inventory_turnover,
            total_attempts=total_attempts,
            successful_orders=successful_orders,
            revenue_total=revenue_total,
            inventory_outbound_qty=inventory_outbound_qty,
            average_inventory_qty=average_inventory_qty,
            run_id=run_id,
        )
    )


def _write_metrics_for_range(db: Session, run_id: int, start_date: date, end_date: date, store_ids: list[int]) -> int:
    records_written = 0
    for day in _date_range(start_date, end_date):
        for store_id in store_ids:
            total_attempts, successful_orders, revenue_total = _read_conversion_and_aov(db, day, store_id)
            inventory_outbound_qty, average_inventory_qty, inventory_turnover = _read_inventory_turnover(
                db,
                day,
                store_id,
            )
            _upsert_metric(
                db,
                run_id=run_id,
                business_date=day,
                store_id=store_id,
                total_attempts=total_attempts,
                successful_orders=successful_orders,
                revenue_total=revenue_total,
                inventory_outbound_qty=inventory_outbound_qty,
                average_inventory_qty=average_inventory_qty,
                inventory_turnover=inventory_turnover,
            )
            records_written += 1
    return records_written


def _mark_failure(run: KPIJobRun, error_message: str, actor_user_id: int | None, db: Session) -> None:
    run.status = "failed"
    run.error_message = error_message
    run.finished_at = datetime.now(timezone.utc)

    audit_event(
        db,
        action="kpi.materialization.failed",
        resource_type="kpi_job_run",
        resource_id=str(run.id),
        actor_user_id=actor_user_id,
        detail={
            "job_name": KPI_JOB_NAME,
            "error": error_message,
            "attempts": run.attempts_made,
            "from": run.processed_from_date.isoformat(),
            "to": run.processed_to_date.isoformat(),
        },
    )


def run_kpi_materialization(
    db: Session,
    *,
    start_date: date,
    end_date: date,
    trigger_type: str,
    actor_user_id: int | None,
    store_ids: list[int] | None = None,
    scheduled_for: datetime | None = None,
) -> KPIJobRun:
    if end_date < start_date:
        raise ValueError("end_date must be on or after start_date")

    scoped_store_ids = sorted(set(store_ids or [0]))

    run = KPIJobRun(
        job_name=KPI_JOB_NAME,
        trigger_type=trigger_type,
        status="running",
        scheduled_for=scheduled_for,
        started_at=datetime.now(timezone.utc),
        finished_at=None,
        attempts_made=0,
        max_attempts=MAX_RETRIES,
        processed_from_date=start_date,
        processed_to_date=end_date,
        records_written=0,
        error_message=None,
        created_by_user_id=actor_user_id,
    )
    db.add(run)
    db.flush()

    for attempt in range(1, MAX_RETRIES + 1):
        run.attempts_made = attempt
        try:
            with db.begin_nested():
                records_written = _write_metrics_for_range(db, run.id, start_date, end_date, scoped_store_ids)
            run.status = "success"
            run.records_written = records_written
            run.error_message = None
            run.finished_at = datetime.now(timezone.utc)

            audit_event(
                db,
                action="kpi.materialized",
                resource_type="kpi_job_run",
                resource_id=str(run.id),
                actor_user_id=actor_user_id,
                detail={
                    "job_name": KPI_JOB_NAME,
                    "trigger_type": trigger_type,
                    "from": start_date.isoformat(),
                    "to": end_date.isoformat(),
                    "records_written": records_written,
                    "store_ids": scoped_store_ids,
                },
            )
            db.flush()
            return run
        except Exception as exc:  # noqa: BLE001
            run.error_message = str(exc)
            run.status = "retrying" if attempt < MAX_RETRIES else "failed"
            if attempt >= MAX_RETRIES:
                _mark_failure(run, str(exc), actor_user_id, db)
                db.flush()
                return run
            db.flush()

    return run


def list_kpi_runs(db: Session, limit: int = 50) -> list[KPIJobRun]:
    rows = db.execute(select(KPIJobRun).order_by(KPIJobRun.id.desc()).limit(limit)).scalars()
    return list(rows)


def list_kpi_metrics(db: Session, start_date: date, end_date: date, store_id: int | None = None) -> list[KPIDailyMetric]:
    stmt = select(KPIDailyMetric).where(
        KPIDailyMetric.business_date >= start_date,
        KPIDailyMetric.business_date <= end_date,
    )
    if store_id is not None:
        stmt = stmt.where(KPIDailyMetric.store_id == store_id)

    rows = db.execute(stmt.order_by(KPIDailyMetric.business_date.asc(), KPIDailyMetric.store_id.asc())).scalars()
    return list(rows)


def purge_metrics_range(db: Session, start_date: date, end_date: date, store_ids: list[int] | None = None) -> int:
    stmt = delete(KPIDailyMetric).where(
        KPIDailyMetric.business_date >= start_date,
        KPIDailyMetric.business_date <= end_date,
    )
    if store_ids:
        stmt = stmt.where(KPIDailyMetric.store_id.in_(store_ids))

    result = db.execute(stmt)
    return int(result.rowcount or 0)


def build_scheduler_status(db: Session, enabled: bool, next_run_at: datetime | None):
    latest = db.execute(select(KPIJobRun).where(KPIJobRun.job_name == KPI_JOB_NAME).order_by(KPIJobRun.id.desc())).scalar_one_or_none()

    from app.schemas.kpi import SchedulerStatusResponse

    return SchedulerStatusResponse(
        job_name=KPI_JOB_NAME,
        enabled=enabled,
        next_run_at=next_run_at,
        last_run_status=latest.status if latest else None,
        last_run_at=latest.finished_at if latest else None,
    )


def log_masking_preview() -> str:
    preview = {
        "member_code": "MEM-SECRET-001",
        "coupon_code": "CPN-SECRET-XYZ",
        "wallet_reference": "WALLET-999-ABC",
        "note": "kpi job run",
    }
    masked = mask_record(preview, {"member_code", "coupon_code", "wallet_reference"})
    return json.dumps(masked, sort_keys=True)
