from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.encryption import field_encryptor
from app.db.models import Member, PointsLedger, WalletAccount, WalletLedger
from app.schemas.loyalty import MemberResponse
from app.types.business import MemberTier


def get_points_balance(db: Session, member_id: int) -> int:
    points_sum = db.execute(
        select(func.coalesce(func.sum(PointsLedger.points_delta), 0)).where(PointsLedger.member_id == member_id)
    ).scalar_one()
    return int(points_sum or 0)


def get_wallet_balance(db: Session, member_id: int) -> Decimal | None:
    wallet = db.execute(select(WalletAccount).where(WalletAccount.member_id == member_id)).scalar_one_or_none()
    if not wallet:
        return None
    balance = wallet.balance
    if isinstance(balance, Decimal):
        return balance
    # Handle encrypted string balance
    if field_encryptor.enabled:
        try:
            decrypted = field_encryptor.decrypt(str(balance))
            return Decimal(decrypted) if decrypted else Decimal(str(balance))
        except (ValueError, Exception):
            pass
    return Decimal(str(balance))


def to_member_response(db: Session, member: Member) -> MemberResponse:
    full_name = member.full_name
    if field_encryptor.enabled:
        full_name = field_encryptor.decrypt(full_name) or ""
    return MemberResponse(
        id=member.id,
        store_id=member.store_id,
        member_code=member.member_code,
        full_name=full_name,
        tier=MemberTier(member.tier),
        stored_value_enabled=member.stored_value_enabled,
        points_balance=get_points_balance(db, member.id),
        wallet_balance=get_wallet_balance(db, member.id),
    )


def get_wallet_ledger(db: Session, member_id: int) -> list[WalletLedger]:
    return list(
        db.execute(
            select(WalletLedger)
            .where(WalletLedger.member_id == member_id)
            .order_by(WalletLedger.id.desc())
        ).scalars()
    )


def get_points_ledger(db: Session, member_id: int) -> list[PointsLedger]:
    return list(
        db.execute(
            select(PointsLedger)
            .where(PointsLedger.member_id == member_id)
            .order_by(PointsLedger.id.desc())
        ).scalars()
    )
