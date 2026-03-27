import csv
import io
from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user, require_roles
from app.core.errors import bad_request
from app.db.session import get_db
from app.schemas.attendance import (
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
from app.services.attendance_service import (
    AttendanceError,
    approve_makeup_request,
    check_in,
    check_out,
    create_makeup_request,
    get_rules,
    list_makeup_requests,
    list_shifts_for_user,
    payroll_export_rows,
    rotate_qr_token,
    update_rules,
)

router = APIRouter(prefix="/attendance", tags=["attendance"])

_MANAGER_ROLES = {"administrator", "store_manager"}
_ATTENDANCE_ROLES = _MANAGER_ROLES | {"employee"}


@router.get("/rules", response_model=AttendanceRuleResponse)
def attendance_rules(
    _: AuthUser = Depends(require_roles(_ATTENDANCE_ROLES)),
    db: Session = Depends(get_db),
) -> AttendanceRuleResponse:
    return get_rules(db)


@router.patch("/rules", response_model=AttendanceRuleResponse)
def attendance_rules_patch(
    payload: AttendanceRuleUpdateRequest,
    current_user: AuthUser = Depends(get_current_user),
    _: AuthUser = Depends(require_roles(_MANAGER_ROLES)),
    db: Session = Depends(get_db),
) -> AttendanceRuleResponse:
    try:
        response = update_rules(db, payload, current_user)
        db.commit()
        return response
    except AttendanceError as exc:
        db.rollback()
        raise bad_request(str(exc))


@router.post("/qr/rotate", response_model=RotatingQRTokenResponse)
def attendance_rotate_qr(
    current_user: AuthUser = Depends(get_current_user),
    _: AuthUser = Depends(require_roles(_MANAGER_ROLES)),
    db: Session = Depends(get_db),
) -> RotatingQRTokenResponse:
    response = rotate_qr_token(db, current_user)
    db.commit()
    return response


@router.post("/check-in", response_model=AttendanceShiftResponse)
def attendance_check_in(
    payload: CheckInRequest,
    current_user: AuthUser = Depends(get_current_user),
    _: AuthUser = Depends(require_roles(_ATTENDANCE_ROLES)),
    db: Session = Depends(get_db),
) -> AttendanceShiftResponse:
    try:
        response = check_in(db, payload, current_user)
        db.commit()
        return response
    except AttendanceError as exc:
        db.rollback()
        raise bad_request(str(exc))


@router.post("/check-out", response_model=CheckOutResponse)
def attendance_check_out(
    payload: CheckOutRequest,
    current_user: AuthUser = Depends(get_current_user),
    _: AuthUser = Depends(require_roles(_ATTENDANCE_ROLES)),
    db: Session = Depends(get_db),
) -> CheckOutResponse:
    try:
        response = check_out(db, payload, current_user)
        db.commit()
        return response
    except AttendanceError as exc:
        db.rollback()
        raise bad_request(str(exc))


@router.get("/me/shifts", response_model=list[AttendanceShiftResponse])
def attendance_me_shifts(
    limit: int = Query(default=30, ge=1, le=180),
    current_user: AuthUser = Depends(get_current_user),
    _: AuthUser = Depends(require_roles(_ATTENDANCE_ROLES)),
    db: Session = Depends(get_db),
) -> list[AttendanceShiftResponse]:
    return list_shifts_for_user(db, current_user, limit=limit)


@router.post("/makeup-requests", response_model=MakeupRequestResponse)
def attendance_makeup_create(
    payload: MakeupRequestCreate,
    current_user: AuthUser = Depends(get_current_user),
    _: AuthUser = Depends(require_roles(_ATTENDANCE_ROLES)),
    db: Session = Depends(get_db),
) -> MakeupRequestResponse:
    response = create_makeup_request(db, payload, current_user)
    db.commit()
    return response


@router.get("/makeup-requests", response_model=list[MakeupRequestResponse])
def attendance_makeup_list(
    current_user: AuthUser = Depends(get_current_user),
    _: AuthUser = Depends(require_roles(_ATTENDANCE_ROLES)),
    db: Session = Depends(get_db),
) -> list[MakeupRequestResponse]:
    return list_makeup_requests(db, current_user)


@router.post("/makeup-requests/{request_id}/approve", response_model=MakeupRequestResponse)
def attendance_makeup_approve(
    request_id: int,
    payload: MakeupRequestApprove,
    current_user: AuthUser = Depends(get_current_user),
    _: AuthUser = Depends(require_roles(_MANAGER_ROLES)),
    db: Session = Depends(get_db),
) -> MakeupRequestResponse:
    try:
        response = approve_makeup_request(db, request_id, payload, current_user)
        db.commit()
        return response
    except AttendanceError as exc:
        db.rollback()
        raise bad_request(str(exc))


@router.get("/payroll-export")
def attendance_payroll_export(
    start_date: date = Query(...),
    end_date: date = Query(...),
    _: AuthUser = Depends(require_roles(_MANAGER_ROLES)),
    db: Session = Depends(get_db),
) -> Response:
    try:
        rows = payroll_export_rows(db, start_date, end_date)
    except AttendanceError as exc:
        raise bad_request(str(exc))

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "user_id",
            "business_date",
            "worked_hours",
            "auto_break_minutes",
            "late_incidents",
            "early_incidents",
            "penalty_hours",
        ]
    )
    for row in rows:
        writer.writerow(
            [
                row.user_id,
                row.business_date.isoformat(),
                str(row.worked_hours),
                row.auto_break_minutes,
                row.late_incidents,
                row.early_incidents,
                str(row.penalty_hours),
            ]
        )

    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="attendance_payroll.csv"'},
    )
