from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.encryption import field_encryptor
from app.db.models import Member, PointsLedger, WalletAccount, WalletLedger
from app.schemas.loyalty import (
    MemberCreateRequest,
    MemberUpdateRequest,
    PointsAccrualRequest,
    PointsAdjustmentRequest,
    WalletMutationRequest,
)
from app.services.audit_service import audit_event
from app.services.member_view_service import to_member_response
from app.services.points_service import calculate_points
from app.types.business import WalletEntryType, round_money


class MemberNotFoundError(ValueError):
    pass


class WalletOperationError(ValueError):
    pass


def _encrypt_name(value: str) -> str:
    if not field_encryptor.enabled:
        return value
    return field_encryptor.encrypt(value) or ""


def _decrypt_name(value: str) -> str:
    if not field_encryptor.enabled:
        return value
    return field_encryptor.decrypt(value) or ""


def _encrypt_amount(value: Decimal) -> str:
    """Encrypt a monetary value for at-rest storage. Returns string representation when encryption is disabled."""
    str_value = str(value)
    if not field_encryptor.enabled:
        return str_value
    return field_encryptor.encrypt(str_value) or str_value


def _decrypt_amount(value: str | Decimal) -> Decimal:
    """Decrypt a monetary value from storage. Handles both encrypted strings and plain Decimal."""
    if isinstance(value, Decimal):
        return value
    if not field_encryptor.enabled:
        return Decimal(str(value))
    try:
        decrypted = field_encryptor.decrypt(str(value))
        return Decimal(decrypted) if decrypted else Decimal(str(value))
    except (ValueError, Exception):
        return Decimal(str(value))


def _get_member_by_code(db: Session, member_code: str, store_id: int | None = None) -> Member | None:
    normalized = member_code.strip().upper()
    stmt = select(Member).where(Member.member_code == normalized)
    if store_id is not None:
        stmt = stmt.where(Member.store_id == store_id)
    return db.execute(stmt).scalar_one_or_none()


def get_member_by_code_or_raise(db: Session, member_code: str, store_id: int | None = None) -> Member:
    member = _get_member_by_code(db, member_code, store_id=store_id)
    if not member:
        raise MemberNotFoundError("Member not found")
    return member


def create_member(
    db: Session,
    payload: MemberCreateRequest,
    actor_user_id: int | None,
    store_id: int | None,
):
    member = Member(
        store_id=store_id,
        member_code=payload.member_code.strip().upper(),
        full_name=_encrypt_name(payload.full_name.strip()),
        tier=payload.tier.value,
        stored_value_enabled=payload.stored_value_enabled,
    )
    db.add(member)
    db.flush()

    if payload.stored_value_enabled:
        db.add(WalletAccount(member_id=member.id, balance=Decimal("0.00"), currency="USD", is_active=True))

    audit_event(
        db,
        action="member.created",
        resource_type="member",
        resource_id=str(member.id),
        actor_user_id=actor_user_id,
        detail={"member_code": member.member_code, "tier": member.tier},
    )
    db.flush()
    return to_member_response(db, member)


def update_member(
    db: Session,
    member_code: str,
    payload: MemberUpdateRequest,
    actor_user_id: int | None,
    store_id: int | None,
):
    member = get_member_by_code_or_raise(db, member_code, store_id=store_id)

    if payload.full_name is not None:
        member.full_name = _encrypt_name(payload.full_name.strip())
    if payload.tier is not None:
        member.tier = payload.tier.value
    if payload.stored_value_enabled is not None:
        member.stored_value_enabled = payload.stored_value_enabled
        wallet = db.execute(select(WalletAccount).where(WalletAccount.member_id == member.id)).scalar_one_or_none()
        if payload.stored_value_enabled and not wallet:
            db.add(WalletAccount(member_id=member.id, balance=Decimal("0.00"), currency="USD", is_active=True))

    audit_event(
        db,
        action="member.updated",
        resource_type="member",
        resource_id=str(member.id),
        actor_user_id=actor_user_id,
        detail={"member_code": member.member_code, "tier": member.tier},
    )
    db.flush()
    return to_member_response(db, member)


def accrue_points(
    db: Session,
    member_code: str,
    payload: PointsAccrualRequest,
    actor_user_id: int | None,
    store_id: int | None,
):
    member = get_member_by_code_or_raise(db, member_code, store_id=store_id)
    points = calculate_points(payload.pre_tax_amount)

    entry = PointsLedger(
        member_id=member.id,
        points_delta=points,
        reason=payload.reason,
        pre_tax_amount=round_money(payload.pre_tax_amount),
        operator_user_id=actor_user_id,
    )
    db.add(entry)

    audit_event(
        db,
        action="points.accrued",
        resource_type="member",
        resource_id=str(member.id),
        actor_user_id=actor_user_id,
        detail={"member_code": member.member_code, "points_delta": points, "reason": payload.reason},
    )
    db.flush()
    return to_member_response(db, member), entry


def adjust_points(
    db: Session,
    member_code: str,
    payload: PointsAdjustmentRequest,
    actor_user_id: int | None,
    store_id: int | None,
):
    member = get_member_by_code_or_raise(db, member_code, store_id=store_id)

    entry = PointsLedger(
        member_id=member.id,
        points_delta=payload.points_delta,
        reason=payload.reason,
        operator_user_id=actor_user_id,
    )
    db.add(entry)

    audit_event(
        db,
        action="points.adjusted",
        resource_type="member",
        resource_id=str(member.id),
        actor_user_id=actor_user_id,
        detail={"member_code": member.member_code, "points_delta": payload.points_delta, "reason": payload.reason},
    )
    db.flush()
    return to_member_response(db, member), entry


def _get_wallet_for_update(db: Session, member_id: int) -> WalletAccount:
    stmt = select(WalletAccount).where(WalletAccount.member_id == member_id).with_for_update()
    wallet = db.execute(stmt).scalar_one_or_none()
    if not wallet:
        raise WalletOperationError("Wallet account not found")
    if not wallet.is_active:
        raise WalletOperationError("Wallet account is inactive")
    return wallet


def _write_wallet_ledger(
    db: Session,
    *,
    wallet: WalletAccount,
    member: Member,
    entry_type: WalletEntryType,
    amount: Decimal,
    reason: str,
    actor_user_id: int | None,
) -> WalletLedger:
    entry = WalletLedger(
        wallet_account_id=wallet.id,
        member_id=member.id,
        entry_type=entry_type.value,
        amount=round_money(amount),
        balance_after=round_money(_decrypt_amount(wallet.balance)),
        reason=reason,
        operator_user_id=actor_user_id,
    )
    db.add(entry)
    return entry


def credit_wallet(
    db: Session,
    member_code: str,
    payload: WalletMutationRequest,
    actor_user_id: int | None,
    store_id: int | None,
):
    member = get_member_by_code_or_raise(db, member_code, store_id=store_id)
    wallet = _get_wallet_for_update(db, member.id)

    current_balance = _decrypt_amount(wallet.balance)
    new_balance = round_money(current_balance + payload.amount)
    wallet.balance = new_balance
    entry = _write_wallet_ledger(
        db,
        wallet=wallet,
        member=member,
        entry_type=WalletEntryType.CREDIT,
        amount=payload.amount,
        reason=payload.reason,
        actor_user_id=actor_user_id,
    )

    audit_event(
        db,
        action="wallet.credited",
        resource_type="member",
        resource_id=str(member.id),
        actor_user_id=actor_user_id,
        detail={"member_code": member.member_code, "amount": str(round_money(payload.amount)), "reason": payload.reason},
    )
    db.flush()
    return to_member_response(db, member), entry


def debit_wallet(
    db: Session,
    member_code: str,
    payload: WalletMutationRequest,
    actor_user_id: int | None,
    store_id: int | None,
):
    member = get_member_by_code_or_raise(db, member_code, store_id=store_id)
    wallet = _get_wallet_for_update(db, member.id)

    current_balance = _decrypt_amount(wallet.balance)
    new_balance = round_money(current_balance - payload.amount)
    if new_balance < Decimal("0.00"):
        raise WalletOperationError("Insufficient wallet balance")

    wallet.balance = new_balance
    entry = _write_wallet_ledger(
        db,
        wallet=wallet,
        member=member,
        entry_type=WalletEntryType.DEBIT,
        amount=payload.amount,
        reason=payload.reason,
        actor_user_id=actor_user_id,
    )

    audit_event(
        db,
        action="wallet.debited",
        resource_type="member",
        resource_id=str(member.id),
        actor_user_id=actor_user_id,
        detail={"member_code": member.member_code, "amount": str(round_money(payload.amount)), "reason": payload.reason},
    )
    db.flush()
    return to_member_response(db, member), entry


def list_members(db: Session, search: str | None = None, store_id: int | None = None) -> list[Member]:
    stmt = select(Member).order_by(Member.id.desc())
    if store_id is not None:
        stmt = stmt.where(Member.store_id == store_id)
    if search:
        raw_search = search.strip()
        code_term = f"%{raw_search.upper()}%"
        if field_encryptor.enabled:
            stmt = stmt.where(Member.member_code.ilike(code_term))
        else:
            name_term = f"%{raw_search}%"
            stmt = stmt.where(Member.member_code.ilike(code_term) | Member.full_name.ilike(name_term))
    return list(db.execute(stmt).scalars())
