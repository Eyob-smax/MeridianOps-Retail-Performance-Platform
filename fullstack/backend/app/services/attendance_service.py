from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import logging
from secrets import token_urlsafe

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.db.models import (
    AttendanceDailyResult,
    AttendanceMakeupRequest,
    AttendanceRuleConfig,
    AttendanceShift,
    DeviceBinding,
    RotatingQRToken,
)
from app.schemas.attendance import (
    AttendanceDailyResultResponse,
    AttendanceRuleResponse,
    AttendanceRuleUpdateRequest,
    AttendanceShiftResponse,
    CheckInRequest,
    CheckOutRequest,
    CheckOutResponse,
    MakeupRequestApprove,
    MakeupRequestCreate,
    MakeupRequestResponse,
    RotatingQRTokenResponse,
)
from app.schemas.auth import AuthUser
from app.services.audit_service import audit_event


logger = logging.getLogger("meridianops.attendance")


class AttendanceError(ValueError):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def get_or_create_rules(db: Session) -> AttendanceRuleConfig:
    row = db.execute(select(AttendanceRuleConfig).limit(1)).scalar_one_or_none()
    if row:
        return row
    row = AttendanceRuleConfig(
        tolerance_minutes=5,
        auto_break_after_hours=6,
        auto_break_minutes=30,
        late_early_penalty_hours=Decimal("0.25"),
        updated_by_user_id=None,
    )
    db.add(row)
    db.flush()
    return row


def get_rules(db: Session) -> AttendanceRuleResponse:
    rules = get_or_create_rules(db)
    return AttendanceRuleResponse(
        tolerance_minutes=rules.tolerance_minutes,
        auto_break_after_hours=rules.auto_break_after_hours,
        auto_break_minutes=rules.auto_break_minutes,
        late_early_penalty_hours=str(rules.late_early_penalty_hours),
    )


def update_rules(db: Session, payload: AttendanceRuleUpdateRequest, current_user: AuthUser) -> AttendanceRuleResponse:
    rules = get_or_create_rules(db)
    rules.tolerance_minutes = payload.tolerance_minutes
    rules.auto_break_after_hours = payload.auto_break_after_hours
    rules.auto_break_minutes = payload.auto_break_minutes
    rules.late_early_penalty_hours = payload.late_early_penalty_hours
    rules.updated_by_user_id = current_user.id

    audit_event(
        db,
        action="attendance.rules.updated",
        resource_type="attendance_rule_config",
        resource_id=str(rules.id),
        actor_user_id=current_user.id,
        detail={
            "tolerance_minutes": rules.tolerance_minutes,
            "auto_break_after_hours": rules.auto_break_after_hours,
            "auto_break_minutes": rules.auto_break_minutes,
            "late_early_penalty_hours": str(rules.late_early_penalty_hours),
        },
    )

    return get_rules(db)


def rotate_qr_token(db: Session, current_user: AuthUser) -> RotatingQRTokenResponse:
    expires_at = _utcnow() + timedelta(seconds=30)
    token = f"qr_{token_urlsafe(22)}"
    row = RotatingQRToken(token=token, created_by_user_id=current_user.id, expires_at=expires_at)
    db.add(row)
    db.flush()
    return RotatingQRTokenResponse(token=row.token, expires_at=row.expires_at)


def _validate_qr_token(db: Session, token: str) -> RotatingQRToken:
    row = db.execute(select(RotatingQRToken).where(RotatingQRToken.token == token)).scalar_one_or_none()
    if not row:
        raise AttendanceError("Invalid QR token")
    if _to_utc(row.expires_at) < _utcnow():
        raise AttendanceError("QR token expired")
    return row


def _resolve_binding(db: Session, user_id: int, device_id: str) -> DeviceBinding:
    binding = db.execute(select(DeviceBinding).where(DeviceBinding.user_id == user_id)).scalar_one_or_none()
    if not binding:
        binding = DeviceBinding(user_id=user_id, device_id=device_id, active=True)
        db.add(binding)
        db.flush()
        return binding

    if not binding.active:
        raise AttendanceError("Device binding is disabled for this user")

    if binding.device_id != device_id:
        raise AttendanceError("Device binding mismatch")

    return binding


def check_in(db: Session, payload: CheckInRequest, current_user: AuthUser) -> AttendanceShiftResponse:
    token = _validate_qr_token(db, payload.qr_token)
    binding = _resolve_binding(db, current_user.id, payload.device_id)

    open_shift = db.execute(
        select(AttendanceShift)
        .where(AttendanceShift.user_id == current_user.id, AttendanceShift.status == "open")
        .limit(1)
    ).scalar_one_or_none()
    if open_shift:
        raise AttendanceError("User already has an open shift")

    check_in_at = _to_utc(payload.check_in_at) if payload.check_in_at else _utcnow()
    shift = AttendanceShift(
        user_id=current_user.id,
        device_binding_id=binding.id,
        qr_token_id=token.id,
        check_in_at=check_in_at,
        check_out_at=None,
        check_in_latitude=payload.latitude,
        check_in_longitude=payload.longitude,
        scheduled_start_at=_to_utc(payload.scheduled_start_at) if payload.scheduled_start_at else None,
        scheduled_end_at=_to_utc(payload.scheduled_end_at) if payload.scheduled_end_at else None,
        status="open",
    )
    db.add(shift)
    db.flush()

    audit_event(
        db,
        action="attendance.checkin",
        resource_type="attendance_shift",
        resource_id=str(shift.id),
        actor_user_id=current_user.id,
        detail={"device_id": payload.device_id, "qr_token": token.token},
    )

    logger.info(
        "attendance_check_in",
        extra={
            "shift_id": shift.id,
            "user_id": current_user.id,
            "device_id": payload.device_id,
        },
    )

    return AttendanceShiftResponse(
        id=shift.id,
        user_id=shift.user_id,
        check_in_at=shift.check_in_at,
        check_out_at=shift.check_out_at,
        status=shift.status,
        scheduled_start_at=shift.scheduled_start_at,
        scheduled_end_at=shift.scheduled_end_at,
    )


def _compute_daily(shift: AttendanceShift, rules: AttendanceRuleConfig, check_out_at: datetime) -> AttendanceDailyResult:
    raw_hours = Decimal(str((check_out_at - _to_utc(shift.check_in_at)).total_seconds() / 3600))
    if raw_hours < Decimal("0"):
        raise AttendanceError("Check-out time cannot be earlier than check-in time")

    auto_break_minutes = rules.auto_break_minutes if raw_hours >= Decimal(rules.auto_break_after_hours) else 0
    worked_hours = raw_hours - (Decimal(auto_break_minutes) / Decimal("60"))
    if worked_hours < Decimal("0"):
        worked_hours = Decimal("0")

    tolerance = timedelta(minutes=rules.tolerance_minutes)
    late_incidents = 0
    early_incidents = 0

    if shift.scheduled_start_at and _to_utc(shift.check_in_at) > _to_utc(shift.scheduled_start_at) + tolerance:
        late_incidents = 1

    if shift.scheduled_end_at and check_out_at + tolerance < _to_utc(shift.scheduled_end_at):
        early_incidents = 1

    penalty_hours = Decimal(late_incidents + early_incidents) * Decimal(rules.late_early_penalty_hours)

    return AttendanceDailyResult(
        user_id=shift.user_id,
        shift_id=shift.id,
        business_date=_to_utc(shift.check_in_at).date(),
        worked_hours=worked_hours.quantize(Decimal("0.01")),
        auto_break_minutes=auto_break_minutes,
        late_incidents=late_incidents,
        early_incidents=early_incidents,
        penalty_hours=penalty_hours.quantize(Decimal("0.01")),
    )


def check_out(db: Session, payload: CheckOutRequest, current_user: AuthUser) -> CheckOutResponse:
    token = _validate_qr_token(db, payload.qr_token)
    _resolve_binding(db, current_user.id, payload.device_id)

    shift = db.execute(
        select(AttendanceShift)
        .where(AttendanceShift.user_id == current_user.id, AttendanceShift.status == "open")
        .limit(1)
    ).scalar_one_or_none()
    if not shift:
        raise AttendanceError("No open shift found")

    check_out_at = _to_utc(payload.check_out_at) if payload.check_out_at else _utcnow()
    shift.check_out_at = check_out_at
    shift.check_out_latitude = payload.latitude
    shift.check_out_longitude = payload.longitude
    shift.status = "closed"

    rules = get_or_create_rules(db)

    existing_daily = db.execute(
        select(AttendanceDailyResult)
        .where(
            AttendanceDailyResult.user_id == current_user.id,
            AttendanceDailyResult.business_date == _to_utc(shift.check_in_at).date(),
        )
        .limit(1)
    ).scalar_one_or_none()
    if existing_daily:
        db.delete(existing_daily)
        db.flush()

    daily = _compute_daily(shift, rules, check_out_at)
    db.add(daily)
    db.flush()

    audit_event(
        db,
        action="attendance.checkout",
        resource_type="attendance_shift",
        resource_id=str(shift.id),
        actor_user_id=current_user.id,
        detail={"device_id": payload.device_id, "qr_token": token.token, "worked_hours": str(daily.worked_hours)},
    )

    logger.info(
        "attendance_check_out",
        extra={
            "shift_id": shift.id,
            "user_id": current_user.id,
            "device_id": payload.device_id,
            "worked_hours": str(daily.worked_hours),
        },
    )

    shift_response = AttendanceShiftResponse(
        id=shift.id,
        user_id=shift.user_id,
        check_in_at=shift.check_in_at,
        check_out_at=shift.check_out_at,
        status=shift.status,
        scheduled_start_at=shift.scheduled_start_at,
        scheduled_end_at=shift.scheduled_end_at,
    )

    daily_response = AttendanceDailyResultResponse(
        id=daily.id,
        user_id=daily.user_id,
        business_date=daily.business_date,
        worked_hours=str(daily.worked_hours),
        auto_break_minutes=daily.auto_break_minutes,
        late_incidents=daily.late_incidents,
        early_incidents=daily.early_incidents,
        penalty_hours=str(daily.penalty_hours),
    )

    return CheckOutResponse(shift=shift_response, daily_result=daily_response)


def list_shifts_for_user(db: Session, current_user: AuthUser, limit: int = 30) -> list[AttendanceShiftResponse]:
    rows = db.execute(
        select(AttendanceShift)
        .where(AttendanceShift.user_id == current_user.id)
        .order_by(AttendanceShift.check_in_at.desc())
        .limit(limit)
    ).scalars().all()
    return [
        AttendanceShiftResponse(
            id=row.id,
            user_id=row.user_id,
            check_in_at=row.check_in_at,
            check_out_at=row.check_out_at,
            status=row.status,
            scheduled_start_at=row.scheduled_start_at,
            scheduled_end_at=row.scheduled_end_at,
        )
        for row in rows
    ]


def create_makeup_request(db: Session, payload: MakeupRequestCreate, current_user: AuthUser) -> MakeupRequestResponse:
    row = AttendanceMakeupRequest(
        user_id=current_user.id,
        business_date=payload.business_date,
        reason=payload.reason.strip(),
        status="pending",
        manager_note=None,
        manager_user_id=None,
        reviewed_at=None,
    )
    db.add(row)
    db.flush()
    return MakeupRequestResponse(
        id=row.id,
        user_id=row.user_id,
        business_date=row.business_date,
        reason=row.reason,
        status=row.status,
        manager_note=row.manager_note,
        manager_user_id=row.manager_user_id,
        created_at=row.created_at,
        reviewed_at=row.reviewed_at,
    )


def list_makeup_requests(db: Session, current_user: AuthUser) -> list[MakeupRequestResponse]:
    stmt = select(AttendanceMakeupRequest)
    if "administrator" not in current_user.roles and "store_manager" not in current_user.roles:
        stmt = stmt.where(AttendanceMakeupRequest.user_id == current_user.id)

    rows = db.execute(stmt.order_by(AttendanceMakeupRequest.created_at.desc())).scalars().all()
    return [
        MakeupRequestResponse(
            id=row.id,
            user_id=row.user_id,
            business_date=row.business_date,
            reason=row.reason,
            status=row.status,
            manager_note=row.manager_note,
            manager_user_id=row.manager_user_id,
            created_at=row.created_at,
            reviewed_at=row.reviewed_at,
        )
        for row in rows
    ]


def approve_makeup_request(db: Session, request_id: int, payload: MakeupRequestApprove, current_user: AuthUser) -> MakeupRequestResponse:
    row = db.execute(select(AttendanceMakeupRequest).where(AttendanceMakeupRequest.id == request_id)).scalar_one_or_none()
    if not row:
        raise AttendanceError("Make-up request not found")
    row.status = "approved"
    row.manager_note = payload.manager_note.strip()
    row.manager_user_id = current_user.id
    row.reviewed_at = _utcnow()

    audit_event(
        db,
        action="attendance.makeup.approved",
        resource_type="attendance_makeup_request",
        resource_id=str(row.id),
        actor_user_id=current_user.id,
        detail={"user_id": row.user_id, "business_date": row.business_date.isoformat()},
    )

    logger.info(
        "attendance_makeup_approved",
        extra={
            "request_id": row.id,
            "subject_user_id": row.user_id,
            "manager_user_id": current_user.id,
            "business_date": row.business_date.isoformat(),
        },
    )

    return MakeupRequestResponse(
        id=row.id,
        user_id=row.user_id,
        business_date=row.business_date,
        reason=row.reason,
        status=row.status,
        manager_note=row.manager_note,
        manager_user_id=row.manager_user_id,
        created_at=row.created_at,
        reviewed_at=row.reviewed_at,
    )


def payroll_export_rows(db: Session, start_date: date, end_date: date) -> list[AttendanceDailyResult]:
    if end_date < start_date:
        raise AttendanceError("end_date must be on or after start_date")
    rows = db.execute(
        select(AttendanceDailyResult)
        .where(
            and_(
                AttendanceDailyResult.business_date >= start_date,
                AttendanceDailyResult.business_date <= end_date,
            )
        )
        .order_by(AttendanceDailyResult.business_date.asc(), AttendanceDailyResult.user_id.asc())
    ).scalars().all()
    return rows
