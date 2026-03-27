from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps.auth import require_roles
from app.core.errors import bad_request
from app.db.session import get_db
from app.schemas.auth import AuthUser
from app.schemas.campaigns import (
    CampaignCreateRequest,
    CampaignResponse,
    CampaignUpdateRequest,
    CouponIssueRequest,
    CouponIssueResponse,
    CouponRedeemRequest,
    CouponRedeemResponse,
)
from app.services.campaign_service import (
    create_campaign,
    get_campaign,
    issue_coupon,
    list_campaigns,
    redeem_coupon,
    update_campaign,
)

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


def _to_campaign_response(campaign) -> CampaignResponse:
    return CampaignResponse(
        id=campaign.id,
        name=campaign.name,
        campaign_type=campaign.campaign_type,
        effective_start=campaign.effective_start,
        effective_end=campaign.effective_end,
        daily_redemption_cap=campaign.daily_redemption_cap,
        per_member_daily_limit=campaign.per_member_daily_limit,
        is_active=campaign.is_active,
        percent_off=campaign.percent_off,
        fixed_amount_off=campaign.fixed_amount_off,
        threshold_amount=campaign.threshold_amount,
    )


@router.get("", response_model=list[CampaignResponse])
def campaign_list(
    _: AuthUser = Depends(require_roles({"administrator", "store_manager"})),
    db: Session = Depends(get_db),
) -> list[CampaignResponse]:
    campaigns = list_campaigns(db)
    return [_to_campaign_response(campaign) for campaign in campaigns]


@router.post("", response_model=CampaignResponse)
def campaign_create(
    payload: CampaignCreateRequest,
    current_user: AuthUser = Depends(require_roles({"administrator", "store_manager"})),
    db: Session = Depends(get_db),
) -> CampaignResponse:
    try:
        campaign = create_campaign(db, payload, current_user.id)
        db.commit()
        return _to_campaign_response(campaign)
    except ValueError as exc:
        db.rollback()
        raise bad_request(str(exc))


@router.get("/{campaign_id}", response_model=CampaignResponse)
def campaign_detail(
    campaign_id: int,
    _: AuthUser = Depends(require_roles({"administrator", "store_manager", "cashier"})),
    db: Session = Depends(get_db),
) -> CampaignResponse:
    campaign = get_campaign(db, campaign_id)
    if not campaign:
        raise bad_request("Campaign not found")
    return _to_campaign_response(campaign)


@router.patch("/{campaign_id}", response_model=CampaignResponse)
def campaign_patch(
    campaign_id: int,
    payload: CampaignUpdateRequest,
    current_user: AuthUser = Depends(require_roles({"administrator", "store_manager"})),
    db: Session = Depends(get_db),
) -> CampaignResponse:
    campaign = get_campaign(db, campaign_id)
    if not campaign:
        raise bad_request("Campaign not found")
    try:
        updated = update_campaign(db, campaign, payload, current_user.id)
        db.commit()
        return _to_campaign_response(updated)
    except ValueError as exc:
        db.rollback()
        raise bad_request(str(exc))


@router.post("/issue", response_model=CouponIssueResponse)
def campaign_issue_coupon(
    payload: CouponIssueRequest,
    current_user: AuthUser = Depends(require_roles({"administrator", "store_manager"})),
    db: Session = Depends(get_db),
) -> CouponIssueResponse:
    try:
        coupon, qr_payload = issue_coupon(db, payload, current_user.id)
        db.commit()
        return CouponIssueResponse(
            coupon_code=coupon.coupon_code,
            campaign_id=coupon.campaign_id,
            issuance_method=coupon.issuance_method,
            qr_payload=qr_payload,
        )
    except ValueError as exc:
        db.rollback()
        raise bad_request(str(exc))


@router.post("/redeem", response_model=CouponRedeemResponse)
def campaign_redeem_coupon(
    payload: CouponRedeemRequest,
    current_user: AuthUser = Depends(require_roles({"administrator", "store_manager", "cashier"})),
    db: Session = Depends(get_db),
) -> CouponRedeemResponse:
    response = redeem_coupon(db, payload, current_user.id)
    db.commit()
    return response
