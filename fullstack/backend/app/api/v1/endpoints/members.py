from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps.auth import require_roles
from app.core.errors import bad_request, conflict, not_found
from app.db.session import get_db
from app.schemas.auth import AuthUser
from app.schemas.loyalty import (
    MemberCreateRequest,
    MemberResponse,
    MemberUpdateRequest,
    PointsAccrualRequest,
    PointsAdjustmentRequest,
    PointsLedgerEntry,
    WalletLedgerEntry,
    WalletMutationRequest,
)
from app.services.loyalty_service import (
    MemberNotFoundError,
    WalletOperationError,
    accrue_points,
    adjust_points,
    create_member,
    credit_wallet,
    debit_wallet,
    get_member_by_code_or_raise,
    list_members,
    update_member,
)
from app.services.member_view_service import get_points_ledger, get_wallet_ledger, to_member_response

router = APIRouter(prefix="/members", tags=["members"])


@router.get("", response_model=list[MemberResponse])
def member_list(
    search: str | None = Query(default=None),
    current_user: AuthUser = Depends(require_roles({"administrator", "store_manager", "cashier"})),
    db: Session = Depends(get_db),
) -> list[MemberResponse]:
    members = list_members(db, search, store_id=current_user.store_id)
    return [to_member_response(db, member) for member in members]


@router.post("", response_model=MemberResponse)
def member_create(
    payload: MemberCreateRequest,
    current_user: AuthUser = Depends(require_roles({"administrator", "store_manager"})),
    db: Session = Depends(get_db),
) -> MemberResponse:
    try:
        response = create_member(db, payload, current_user.id, current_user.store_id)
        db.commit()
        return response
    except IntegrityError:
        db.rollback()
        raise conflict("Member code already exists")
    except ValueError as exc:
        db.rollback()
        raise bad_request(str(exc))


@router.get("/{member_code}", response_model=MemberResponse)
def member_lookup(
    member_code: str,
    current_user: AuthUser = Depends(require_roles({"administrator", "store_manager", "cashier"})),
    db: Session = Depends(get_db),
) -> MemberResponse:
    try:
        member = get_member_by_code_or_raise(db, member_code, store_id=current_user.store_id)
    except MemberNotFoundError as exc:
        raise not_found(str(exc))
    return to_member_response(db, member)


@router.patch("/{member_code}", response_model=MemberResponse)
def member_update(
    member_code: str,
    payload: MemberUpdateRequest,
    current_user: AuthUser = Depends(require_roles({"administrator", "store_manager"})),
    db: Session = Depends(get_db),
) -> MemberResponse:
    try:
        response = update_member(db, member_code, payload, current_user.id, current_user.store_id)
        db.commit()
        return response
    except MemberNotFoundError as exc:
        db.rollback()
        raise not_found(str(exc))
    except ValueError as exc:
        db.rollback()
        raise bad_request(str(exc))


@router.post("/{member_code}/points/accrue", response_model=MemberResponse)
def member_points_accrue(
    member_code: str,
    payload: PointsAccrualRequest,
    current_user: AuthUser = Depends(require_roles({"administrator", "store_manager", "cashier"})),
    db: Session = Depends(get_db),
) -> MemberResponse:
    try:
        response, _entry = accrue_points(db, member_code, payload, current_user.id, current_user.store_id)
        db.commit()
        return response
    except MemberNotFoundError as exc:
        db.rollback()
        raise not_found(str(exc))


@router.post("/{member_code}/points/adjust", response_model=MemberResponse)
def member_points_adjust(
    member_code: str,
    payload: PointsAdjustmentRequest,
    current_user: AuthUser = Depends(require_roles({"administrator", "store_manager"})),
    db: Session = Depends(get_db),
) -> MemberResponse:
    try:
        response, _entry = adjust_points(db, member_code, payload, current_user.id, current_user.store_id)
        db.commit()
        return response
    except MemberNotFoundError as exc:
        db.rollback()
        raise not_found(str(exc))


@router.post("/{member_code}/wallet/credit", response_model=MemberResponse)
def member_wallet_credit(
    member_code: str,
    payload: WalletMutationRequest,
    current_user: AuthUser = Depends(require_roles({"administrator", "store_manager", "cashier"})),
    db: Session = Depends(get_db),
) -> MemberResponse:
    try:
        response, _entry = credit_wallet(db, member_code, payload, current_user.id, current_user.store_id)
        db.commit()
        return response
    except MemberNotFoundError as exc:
        db.rollback()
        raise not_found(str(exc))
    except WalletOperationError as exc:
        db.rollback()
        raise conflict(str(exc))


@router.post("/{member_code}/wallet/debit", response_model=MemberResponse)
def member_wallet_debit(
    member_code: str,
    payload: WalletMutationRequest,
    current_user: AuthUser = Depends(require_roles({"administrator", "store_manager", "cashier"})),
    db: Session = Depends(get_db),
) -> MemberResponse:
    try:
        response, _entry = debit_wallet(db, member_code, payload, current_user.id, current_user.store_id)
        db.commit()
        return response
    except MemberNotFoundError as exc:
        db.rollback()
        raise not_found(str(exc))
    except WalletOperationError as exc:
        db.rollback()
        raise conflict(str(exc))


@router.get("/{member_code}/points-ledger", response_model=list[PointsLedgerEntry])
def member_points_ledger(
    member_code: str,
    current_user: AuthUser = Depends(require_roles({"administrator", "store_manager", "cashier"})),
    db: Session = Depends(get_db),
) -> list[PointsLedgerEntry]:
    try:
        member = get_member_by_code_or_raise(db, member_code, store_id=current_user.store_id)
    except MemberNotFoundError as exc:
        raise not_found(str(exc))
    entries = get_points_ledger(db, member.id)
    return [
        PointsLedgerEntry(
            id=entry.id,
            member_id=entry.member_id,
            points_delta=entry.points_delta,
            reason=entry.reason,
            pre_tax_amount=Decimal(entry.pre_tax_amount) if entry.pre_tax_amount is not None else None,
        )
        for entry in entries
    ]


@router.get("/{member_code}/wallet-ledger", response_model=list[WalletLedgerEntry])
def member_wallet_ledger(
    member_code: str,
    current_user: AuthUser = Depends(require_roles({"administrator", "store_manager", "cashier"})),
    db: Session = Depends(get_db),
) -> list[WalletLedgerEntry]:
    try:
        member = get_member_by_code_or_raise(db, member_code, store_id=current_user.store_id)
    except MemberNotFoundError as exc:
        raise not_found(str(exc))
    entries = get_wallet_ledger(db, member.id)
    return [
        WalletLedgerEntry(
            id=entry.id,
            member_id=entry.member_id,
            entry_type=entry.entry_type,
            amount=Decimal(entry.amount),
            balance_after=Decimal(entry.balance_after),
            reason=entry.reason,
        )
        for entry in entries
    ]
