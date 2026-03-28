from datetime import date, datetime, timezone
from decimal import Decimal
import logging
from random import choices
from string import ascii_uppercase, digits

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.db.models import Campaign, Coupon, CouponIssuanceEvent, CouponRedemptionEvent, Member
from app.schemas.auth import AuthUser
from app.schemas.campaigns import (
    CampaignCreateRequest,
    CampaignUpdateRequest,
    CouponIssueRequest,
    CouponRedeemRequest,
    CouponRedeemResponse,
)
from app.core.masking import mask_record
from app.services.audit_service import audit_event
from app.types.business import CampaignType, IssuanceMethod, RedemptionStatus, round_money


logger = logging.getLogger("meridianops.campaigns")
_SENSITIVE_LOG_KEYS = {"order_reference"}


class CampaignNotFoundError(ValueError):
    pass


class CampaignMemberNotFoundError(ValueError):
    pass


def _generate_coupon_code() -> str:
    suffix = "".join(choices(ascii_uppercase + digits, k=12))
    return f"CPN-{suffix}"


def _normalize_member_code(member_code: str | None) -> str | None:
    if member_code is None:
        return None
    value = member_code.strip().upper()
    return value or None


def _get_member_by_code(db: Session, member_code: str | None, store_id: int | None = None) -> Member | None:
    normalized = _normalize_member_code(member_code)
    if not normalized:
        return None
    stmt = select(Member).where(Member.member_code == normalized)
    if store_id is not None:
        stmt = stmt.where(Member.store_id == store_id)
    return db.execute(stmt).scalar_one_or_none()


def _validate_campaign_payload(payload: CampaignCreateRequest) -> None:
    if payload.effective_end < payload.effective_start:
        raise ValueError("effective_end must be on or after effective_start")

    if payload.campaign_type == CampaignType.PERCENT_OFF and payload.percent_off is None:
        raise ValueError("percent_off is required for percent_off campaign")

    if payload.campaign_type == CampaignType.FIXED_AMOUNT and payload.fixed_amount_off is None:
        raise ValueError("fixed_amount_off is required for fixed_amount campaign")

    if payload.campaign_type == CampaignType.FULL_REDUCTION:
        if payload.fixed_amount_off is None or payload.threshold_amount is None:
            raise ValueError("fixed_amount_off and threshold_amount are required for full_reduction campaign")


def create_campaign(db: Session, payload: CampaignCreateRequest, actor_user: AuthUser) -> Campaign:
    _validate_campaign_payload(payload)

    campaign = Campaign(
        store_id=actor_user.store_id,
        name=payload.name.strip(),
        campaign_type=payload.campaign_type.value,
        percent_off=payload.percent_off,
        fixed_amount_off=payload.fixed_amount_off,
        threshold_amount=payload.threshold_amount,
        effective_start=payload.effective_start,
        effective_end=payload.effective_end,
        daily_redemption_cap=payload.daily_redemption_cap,
        per_member_daily_limit=payload.per_member_daily_limit,
        created_by_user_id=actor_user.id,
        is_active=True,
    )
    db.add(campaign)
    db.flush()

    audit_event(
        db,
        action="campaign.created",
        resource_type="campaign",
        resource_id=str(campaign.id),
        actor_user_id=actor_user.id,
        detail={"campaign_type": campaign.campaign_type, "name": campaign.name},
    )
    return campaign


def list_campaigns(db: Session, store_id: int | None = None) -> list[Campaign]:
    stmt = select(Campaign).order_by(Campaign.id.desc())
    if store_id is not None:
        stmt = stmt.where(Campaign.store_id == store_id)
    return list(db.execute(stmt).scalars())


def get_campaign(db: Session, campaign_id: int, store_id: int | None = None) -> Campaign | None:
    stmt = select(Campaign).where(Campaign.id == campaign_id)
    if store_id is not None:
        stmt = stmt.where(Campaign.store_id == store_id)
    return db.execute(stmt).scalar_one_or_none()


def update_campaign(
    db: Session,
    campaign: Campaign,
    payload: CampaignUpdateRequest,
    actor_user_id: int | None,
) -> Campaign:
    if payload.name is not None:
        campaign.name = payload.name.strip()
    if payload.effective_start is not None:
        campaign.effective_start = payload.effective_start
    if payload.effective_end is not None:
        campaign.effective_end = payload.effective_end
    if payload.daily_redemption_cap is not None:
        campaign.daily_redemption_cap = payload.daily_redemption_cap
    if payload.per_member_daily_limit is not None:
        campaign.per_member_daily_limit = payload.per_member_daily_limit
    if payload.percent_off is not None:
        campaign.percent_off = payload.percent_off
    if payload.fixed_amount_off is not None:
        campaign.fixed_amount_off = payload.fixed_amount_off
    if payload.threshold_amount is not None:
        campaign.threshold_amount = payload.threshold_amount
    if payload.is_active is not None:
        campaign.is_active = payload.is_active

    if campaign.effective_end < campaign.effective_start:
        raise ValueError("effective_end must be on or after effective_start")

    audit_event(
        db,
        action="campaign.updated",
        resource_type="campaign",
        resource_id=str(campaign.id),
        actor_user_id=actor_user_id,
        detail={"campaign_type": campaign.campaign_type, "name": campaign.name},
    )
    db.flush()
    return campaign


def _validate_issue_member(db: Session, request: CouponIssueRequest, store_id: int | None) -> Member | None:
    member = _get_member_by_code(db, request.member_code, store_id=store_id)

    if request.issuance_method == IssuanceMethod.ACCOUNT_ASSIGNMENT:
        if not member:
            raise ValueError("member_code is required and must exist for account assignment")
        return member

    if request.member_code and not member:
        raise CampaignMemberNotFoundError("Member not found")

    return member


def issue_coupon(db: Session, request: CouponIssueRequest, actor_user: AuthUser) -> tuple[Coupon, str | None]:
    campaign = get_campaign(db, request.campaign_id, store_id=actor_user.store_id)
    if not campaign:
        raise CampaignNotFoundError("Campaign not found")
    if not campaign.is_active:
        raise ValueError("Campaign is inactive")

    member = _validate_issue_member(db, request, store_id=actor_user.store_id)

    code = _generate_coupon_code()
    coupon = Coupon(
        store_id=campaign.store_id,
        campaign_id=campaign.id,
        coupon_code=code,
        issuance_method=request.issuance_method.value,
        member_id=member.id if member else None,
        issued_by_user_id=actor_user.id,
    )
    db.add(coupon)
    db.flush()

    qr_payload = f"coupon:{coupon.coupon_code}" if request.issuance_method == IssuanceMethod.PRINTABLE_QR else None

    db.add(
        CouponIssuanceEvent(
            store_id=campaign.store_id,
            coupon_id=coupon.id,
            campaign_id=campaign.id,
            member_id=member.id if member else None,
            operator_user_id=actor_user.id,
            channel=request.issuance_method.value,
            qr_payload=qr_payload,
        )
    )

    audit_event(
        db,
        action="coupon.issued",
        resource_type="coupon",
        resource_id=str(coupon.id),
        actor_user_id=actor_user.id,
        detail={"coupon_code": coupon.coupon_code, "campaign_id": campaign.id},
    )

    return coupon, qr_payload


def _count_redemptions_today(db: Session, campaign_id: int, store_id: int | None = None) -> int:
    today = date.today()
    stmt = select(func.count(CouponRedemptionEvent.id)).where(
        CouponRedemptionEvent.campaign_id == campaign_id,
        CouponRedemptionEvent.status == RedemptionStatus.SUCCESS.value,
        func.date(CouponRedemptionEvent.created_at) == str(today),
    )
    if store_id is not None:
        stmt = stmt.where(CouponRedemptionEvent.store_id == store_id)
    return int(db.execute(stmt).scalar_one() or 0)


def _count_member_redemptions_today(
    db: Session,
    campaign_id: int,
    member_id: int,
    store_id: int | None = None,
) -> int:
    today = date.today()
    stmt = select(func.count(CouponRedemptionEvent.id)).where(
        CouponRedemptionEvent.campaign_id == campaign_id,
        CouponRedemptionEvent.member_id == member_id,
        CouponRedemptionEvent.status == RedemptionStatus.SUCCESS.value,
        func.date(CouponRedemptionEvent.created_at) == str(today),
    )
    if store_id is not None:
        stmt = stmt.where(CouponRedemptionEvent.store_id == store_id)
    return int(db.execute(stmt).scalar_one() or 0)


def _compute_discount(campaign: Campaign, pre_tax_amount: Decimal) -> Decimal:
    pre_tax = round_money(pre_tax_amount)

    if campaign.campaign_type == CampaignType.PERCENT_OFF.value:
        percent = Decimal(campaign.percent_off or 0)
        discount = pre_tax * percent
    elif campaign.campaign_type == CampaignType.FIXED_AMOUNT.value:
        discount = Decimal(campaign.fixed_amount_off or 0)
    else:
        threshold = Decimal(campaign.threshold_amount or 0)
        if pre_tax < threshold:
            return Decimal("0.00")
        discount = Decimal(campaign.fixed_amount_off or 0)

    if discount > pre_tax:
        discount = pre_tax
    return round_money(discount)


def _reject_redemption(
    db: Session,
    *,
    coupon: Coupon | None,
    campaign: Campaign | None,
    member_id: int | None,
    operator_user_id: int | None,
    order_reference: str,
    pre_tax_amount: Decimal,
    reason_code: str,
    message: str,
) -> CouponRedeemResponse:
    logger.warning(
        "coupon_redeem_rejected",
        extra=mask_record(
            {
                "reason_code": reason_code,
                "campaign_id": campaign.id if campaign else None,
                "coupon_id": coupon.id if coupon else None,
                "operator_user_id": operator_user_id,
                "order_reference": order_reference,
            },
            _SENSITIVE_LOG_KEYS,
        ),
    )
    db.add(
        CouponRedemptionEvent(
            coupon_id=coupon.id if coupon else None,
            campaign_id=campaign.id if campaign else None,
            member_id=member_id,
            operator_user_id=operator_user_id,
            store_id=campaign.store_id if campaign else None,
            order_reference=order_reference,
            pre_tax_amount=round_money(pre_tax_amount),
            discount_amount=Decimal("0.00"),
            status=RedemptionStatus.FAILED.value,
            reason_code=reason_code,
            message=message,
        )
    )
    return CouponRedeemResponse(
        success=False,
        reason_code=reason_code,
        message=message,
        discount_amount=Decimal("0.00"),
        final_amount=round_money(pre_tax_amount),
        campaign_id=campaign.id if campaign else None,
    )


def redeem_coupon(
    db: Session,
    request: CouponRedeemRequest,
    operator_user_id: int | None,
    operator_store_id: int | None = None,
) -> CouponRedeemResponse:
    stmt = select(Coupon).where(Coupon.coupon_code == request.coupon_code)
    if operator_store_id is not None:
        stmt = stmt.where(Coupon.store_id == operator_store_id)
    coupon = db.execute(stmt.with_for_update()).scalar_one_or_none()

    if not coupon:
        return _reject_redemption(
            db,
            coupon=None,
            campaign=None,
            member_id=None,
            operator_user_id=operator_user_id,
            order_reference=request.order_reference,
            pre_tax_amount=request.pre_tax_amount,
            reason_code="COUPON_NOT_FOUND",
            message="Coupon not found.",
        )

    campaign = get_campaign(db, coupon.campaign_id, store_id=operator_store_id)
    if not campaign:
        return _reject_redemption(
            db,
            coupon=coupon,
            campaign=None,
            member_id=None,
            operator_user_id=operator_user_id,
            order_reference=request.order_reference,
            pre_tax_amount=request.pre_tax_amount,
            reason_code="CAMPAIGN_NOT_FOUND",
            message="Campaign not found.",
        )

    member = _get_member_by_code(db, request.member_code, store_id=operator_store_id)

    existing_success = db.execute(
        select(CouponRedemptionEvent).where(
            CouponRedemptionEvent.coupon_id == coupon.id,
            CouponRedemptionEvent.order_reference == request.order_reference,
            CouponRedemptionEvent.status == RedemptionStatus.SUCCESS.value,
        )
    ).scalar_one_or_none()

    if existing_success:
        final_amount = round_money(Decimal(existing_success.pre_tax_amount) - Decimal(existing_success.discount_amount))
        return CouponRedeemResponse(
            success=True,
            reason_code="IDEMPOTENT_REPLAY",
            message="Coupon already redeemed for this order.",
            discount_amount=Decimal(existing_success.discount_amount),
            final_amount=final_amount,
            campaign_id=campaign.id,
        )

    if coupon.redeemed_at is not None:
        return _reject_redemption(
            db,
            coupon=coupon,
            campaign=campaign,
            member_id=member.id if member else None,
            operator_user_id=operator_user_id,
            order_reference=request.order_reference,
            pre_tax_amount=request.pre_tax_amount,
            reason_code="ALREADY_REDEEMED",
            message="Coupon already redeemed.",
        )

    today = date.today()
    if not campaign.is_active or not (campaign.effective_start <= today <= campaign.effective_end):
        return _reject_redemption(
            db,
            coupon=coupon,
            campaign=campaign,
            member_id=member.id if member else None,
            operator_user_id=operator_user_id,
            order_reference=request.order_reference,
            pre_tax_amount=request.pre_tax_amount,
            reason_code="CAMPAIGN_INACTIVE",
            message="Campaign is not active for today.",
        )

    if _count_redemptions_today(db, campaign.id, store_id=operator_store_id) >= campaign.daily_redemption_cap:
        return _reject_redemption(
            db,
            coupon=coupon,
            campaign=campaign,
            member_id=member.id if member else None,
            operator_user_id=operator_user_id,
            order_reference=request.order_reference,
            pre_tax_amount=request.pre_tax_amount,
            reason_code="DAILY_CAP_REACHED",
            message="Campaign daily redemption cap reached.",
        )

    if coupon.member_id and member and coupon.member_id != member.id:
        return _reject_redemption(
            db,
            coupon=coupon,
            campaign=campaign,
            member_id=member.id,
            operator_user_id=operator_user_id,
            order_reference=request.order_reference,
            pre_tax_amount=request.pre_tax_amount,
            reason_code="MEMBER_MISMATCH",
            message="Coupon assigned to another member.",
        )

    if coupon.member_id and not member:
        return _reject_redemption(
            db,
            coupon=coupon,
            campaign=campaign,
            member_id=None,
            operator_user_id=operator_user_id,
            order_reference=request.order_reference,
            pre_tax_amount=request.pre_tax_amount,
            reason_code="MEMBER_REQUIRED",
            message="Member code is required for this coupon.",
        )

    if (
        member
        and _count_member_redemptions_today(
            db,
            campaign.id,
            member.id,
            store_id=operator_store_id,
        )
        >= campaign.per_member_daily_limit
    ):
        return _reject_redemption(
            db,
            coupon=coupon,
            campaign=campaign,
            member_id=member.id,
            operator_user_id=operator_user_id,
            order_reference=request.order_reference,
            pre_tax_amount=request.pre_tax_amount,
            reason_code="MEMBER_DAILY_LIMIT_REACHED",
            message="Member daily redemption limit reached for this campaign.",
        )

    discount_amount = _compute_discount(campaign, request.pre_tax_amount)
    if campaign.campaign_type == CampaignType.FULL_REDUCTION.value and discount_amount <= Decimal("0.00"):
        return _reject_redemption(
            db,
            coupon=coupon,
            campaign=campaign,
            member_id=member.id if member else None,
            operator_user_id=operator_user_id,
            order_reference=request.order_reference,
            pre_tax_amount=request.pre_tax_amount,
            reason_code="THRESHOLD_NOT_MET",
            message="Order amount does not meet campaign threshold.",
        )

    coupon.redeemed_at = datetime.now(timezone.utc)
    coupon.redeemed_by_user_id = operator_user_id
    coupon.order_reference = request.order_reference
    coupon.redemption_member_id = member.id if member else None

    final_amount = round_money(request.pre_tax_amount - discount_amount)

    db.add(
        CouponRedemptionEvent(
            store_id=campaign.store_id,
            coupon_id=coupon.id,
            campaign_id=campaign.id,
            member_id=member.id if member else None,
            operator_user_id=operator_user_id,
            order_reference=request.order_reference,
            pre_tax_amount=round_money(request.pre_tax_amount),
            discount_amount=discount_amount,
            status=RedemptionStatus.SUCCESS.value,
            reason_code="SUCCESS",
            message="Coupon redeemed successfully.",
        )
    )

    audit_event(
        db,
        action="coupon.redeemed",
        resource_type="coupon",
        resource_id=str(coupon.id),
        actor_user_id=operator_user_id,
        detail={
            "coupon_code": coupon.coupon_code,
            "campaign_id": campaign.id,
            "discount_amount": discount_amount,
            "order_reference": request.order_reference,
        },
    )

    logger.info(
        "coupon_redeemed",
        extra=mask_record(
            {
                "campaign_id": campaign.id,
                "coupon_id": coupon.id,
                "operator_user_id": operator_user_id,
                "discount_amount": str(discount_amount),
                "order_reference": request.order_reference,
            },
            _SENSITIVE_LOG_KEYS,
        ),
    )

    return CouponRedeemResponse(
        success=True,
        reason_code="SUCCESS",
        message="Coupon redeemed successfully.",
        discount_amount=discount_amount,
        final_amount=final_amount,
        campaign_id=campaign.id,
    )
