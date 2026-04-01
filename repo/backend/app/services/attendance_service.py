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
    NfcBadge,
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
from app.core.masking import mask_record
from app.services.audit_service import audit_event


logger = logging.getLogger("meridianops.attendance")
_SENSITIVE_LOG_KEYS = {"device_id", "qr_token", "nfc_tag"}


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
        cross_day_shift_cutoff_hour=6,
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
        cross_day_shift_cutoff_hour=rules.cross_day_shift_cutoff_hour,
        late_early_penalty_hours=str(rules.late_early_penalty_hours),
    )


def update_rules(db: Session, payload: AttendanceRuleUpdateRequest, current_user: AuthUser) -> AttendanceRuleResponse:
    rules = get_or_create_rules(db)
    rules.tolerance_minutes = payload.tolerance_minutes
    rules.auto_break_after_hours = payload.auto_break_after_hours
    rules.auto_break_minutes = payload.auto_break_minutes
    rules.cross_day_shift_cutoff_hour = payload.cross_day_shift_cutoff_hour
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
            "cross_day_shift_cutoff_hour": rules.cross_day_shift_cutoff_hour,
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
    row = db.execute(
        select(RotatingQRToken).where(RotatingQRToken.token == token).with_for_update()
    ).scalar_one_or_none()
    if not row:
        raise AttendanceError("Invalid QR token")
    if _to_utc(row.expires_at) < _utcnow():
        raise AttendanceError("QR token expired")
    if row.used_at is not None:
        raise AttendanceError("QR token already used")
    return row


def _consume_qr_token(row: RotatingQRToken | None) -> None:
    if row is not None:
        row.used_at = _utcnow()


def _resolve_nfc_binding(db: Session, user_id: int, tag_id: str) -> NfcBadge:
    binding = db.execute(select(NfcBadge).where(NfcBadge.user_id == user_id)).scalar_one_or_none()
    if not binding:
        binding = NfcBadge(user_id=user_id, tag_id=tag_id, active=True)
        db.add(binding)
        db.flush()
        return binding

    if not binding.active:
        raise AttendanceError("NFC badge is disabled for this user")

    if binding.tag_id != tag_id:
        raise AttendanceError("NFC badge mismatch")

    return binding


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
    token = _validate_qr_token(db, payload.qr_token) if payload.qr_token else None
    nfc_binding = _resolve_nfc_binding(db, current_user.id, payload.nfc_tag) if payload.nfc_tag else None
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
        store_id=current_user.store_id,
        user_id=current_user.id,
        device_binding_id=binding.id,
        qr_token_id=token.id if token else None,
        nfc_badge_id=nfc_binding.id if nfc_binding else None,
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
    _consume_qr_token(token)

    audit_event(
        db,
        action="attendance.checkin",
        resource_type="attendance_shift",
        resource_id=str(shift.id),
        actor_user_id=current_user.id,
        detail={
            "device_id": payload.device_id,
            "qr_token": token.token if token else None,
            "nfc_tag": payload.nfc_tag,
        },
    )

    logger.info(
        "attendance_check_in",
        extra=mask_record(
            {
                "shift_id": shift.id,
                "user_id": current_user.id,
                "device_id": payload.device_id,
            },
            _SENSITIVE_LOG_KEYS,
        ),
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


def _resolve_business_date(shift: AttendanceShift, rules: AttendanceRuleConfig, check_out_at: datetime) -> date:
    check_in_utc = _to_utc(shift.check_in_at)
    if shift.scheduled_start_at is not None:
        return _to_utc(shift.scheduled_start_at).date()
    if check_out_at.date() > check_in_utc.date() and check_out_at.hour < rules.cross_day_shift_cutoff_hour:
        return check_in_utc.date()
    return check_out_at.date()


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
    business_date = _resolve_business_date(shift, rules, check_out_at)

    return AttendanceDailyResult(
        user_id=shift.user_id,
        shift_id=shift.id,
        business_date=business_date,
        worked_hours=worked_hours.quantize(Decimal("0.01")),
        auto_break_minutes=auto_break_minutes,
        late_incidents=late_incidents,
        early_incidents=early_incidents,
        penalty_hours=penalty_hours.quantize(Decimal("0.01")),
    )


def check_out(db: Session, payload: CheckOutRequest, current_user: AuthUser) -> CheckOutResponse:
    token = _validate_qr_token(db, payload.qr_token) if payload.qr_token else None
    nfc_binding = _resolve_nfc_binding(db, current_user.id, payload.nfc_tag) if payload.nfc_tag else None
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
    _consume_qr_token(token)

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
    daily.store_id = current_user.store_id
    db.add(daily)
    db.flush()

    audit_event(
        db,
        action="attendance.checkout",
        resource_type="attendance_shift",
        resource_id=str(shift.id),
        actor_user_id=current_user.id,
        detail={
            "device_id": payload.device_id,
            "qr_token": token.token if token else None,
            "nfc_tag": payload.nfc_tag,
            "worked_hours": str(daily.worked_hours),
        },
    )

    logger.info(
        "attendance_check_out",
        extra=mask_record(
            {
                "shift_id": shift.id,
                "user_id": current_user.id,
                "device_id": payload.device_id,
                "worked_hours": str(daily.worked_hours),
            },
            _SENSITIVE_LOG_KEYS,
        ),
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
        .where(
            AttendanceShift.store_id == current_user.store_id
            if current_user.store_id is not None
            else True
        )
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
        store_id=current_user.store_id,
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
    if current_user.store_id is not None:
        stmt = stmt.where(AttendanceMakeupRequest.store_id == current_user.store_id)

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
    if current_user.store_id is not None and row.store_id != current_user.store_id:
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


def payroll_export_rows(db: Session, start_date: date, end_date: date, store_id: int | None = None) -> list[AttendanceDailyResult]:
    if end_date < start_date:
        raise AttendanceError("end_date must be on or after start_date")
    stmt = select(AttendanceDailyResult).where(
        and_(
            AttendanceDailyResult.business_date >= start_date,
            AttendanceDailyResult.business_date <= end_date,
        )
    )
    if store_id is not None:
        stmt = stmt.where(AttendanceDailyResult.store_id == store_id)
    rows = db.execute(stmt.order_by(AttendanceDailyResult.business_date.asc(), AttendanceDailyResult.user_id.asc())).scalars().all()
    return list(rows)
