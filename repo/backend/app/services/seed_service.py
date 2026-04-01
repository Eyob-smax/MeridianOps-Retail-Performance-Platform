from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.masking import mask_record
from app.db.models import (
    Campaign,
    Coupon,
    CouponIssuanceEvent,
    CouponRedemptionEvent,
    DashboardLayout,
    InventoryDocument,
    InventoryDocumentLine,
    InventoryItem,
    InventoryLedger,
    InventoryLocation,
    Member,
    PointsLedger,
    QuizAssignment,
    QuizAttempt,
    QuizQuestion,
    QuizTopic,
    ReviewQueueSnapshot,
    SpacedRepetitionState,
    User,
    WalletAccount,
    WalletLedger,
)
from app.schemas.auth import AuthUser
from app.services.audit_service import audit_event
from app.types.business import WalletEntryType

DEMO_STORES: list[tuple[int, str, str]] = [
    (101, "DOWNTOWN", "Downtown"),
    (102, "AIRPORT", "Airport"),
    (103, "WEST", "West End"),
]


def _ensure_member(db: Session, member_code: str, full_name: str, tier: str, stored_value_enabled: bool) -> Member:
    member = db.execute(select(Member).where(Member.member_code == member_code)).scalar_one_or_none()
    if member:
        return member

    member = Member(
        member_code=member_code,
        full_name=full_name,
        tier=tier,
        stored_value_enabled=stored_value_enabled,
    )
    db.add(member)
    db.flush()

    if stored_value_enabled:
        wallet = WalletAccount(member_id=member.id, balance=Decimal("150.00"), currency="USD", is_active=True)
        db.add(wallet)
        db.flush()
        db.add(
            WalletLedger(
                wallet_account_id=wallet.id,
                member_id=member.id,
                entry_type=WalletEntryType.CREDIT.value,
                amount=Decimal("150.00"),
                balance_after=Decimal("150.00"),
                reason="seed top-up",
                operator_user_id=None,
            )
        )

    db.add(
        PointsLedger(
            member_id=member.id,
            points_delta=120,
            reason="seed baseline",
            pre_tax_amount=Decimal("120.00"),
            operator_user_id=None,
        )
    )
    return member


def _ensure_campaign(db: Session, actor_user_id: int | None) -> Campaign:
    campaign = db.execute(select(Campaign).where(Campaign.name == "Seed 10 Percent")).scalar_one_or_none()
    if campaign:
        return campaign

    campaign = Campaign(
        name="Seed 10 Percent",
        campaign_type="percent_off",
        percent_off=Decimal("0.1000"),
        fixed_amount_off=None,
        threshold_amount=None,
        effective_start=date.today() - timedelta(days=365),
        effective_end=date.today() + timedelta(days=365),
        daily_redemption_cap=500,
        per_member_daily_limit=2,
        is_active=True,
        created_by_user_id=actor_user_id,
    )
    db.add(campaign)
    db.flush()
    return campaign


def _ensure_inventory_baseline(db: Session) -> tuple[int, int]:
    created_items = 0
    created_ledgers = 0

    for store_id, code, name in DEMO_STORES:
        location = db.execute(select(InventoryLocation).where(InventoryLocation.id == store_id)).scalar_one_or_none()
        if not location:
            location = InventoryLocation(id=store_id, code=code, name=name)
            db.add(location)

    db.flush()

    for idx, sku in enumerate(["SKU-COF-001", "SKU-TEA-002", "SKU-PAS-003"], start=1):
        item = db.execute(select(InventoryItem).where(InventoryItem.sku == sku)).scalar_one_or_none()
        if not item:
            item = InventoryItem(
                sku=sku,
                name=["Coffee Beans", "Tea Leaves", "Pastry Mix"][idx - 1],
                unit="kg",
                batch_tracking_enabled=True,
                expiry_tracking_enabled=False,
            )
            db.add(item)
            db.flush()
            created_items += 1

            document = InventoryDocument(
                doc_type="receiving",
                status="posted",
                source_location_id=None,
                target_location_id=DEMO_STORES[0][0],
                note="seed receive",
                operator_user_id=None,
            )
            db.add(document)
            db.flush()
            line = InventoryDocumentLine(
                document_id=document.id,
                item_id=item.id,
                quantity=Decimal("150.000"),
                batch_no=f"BATCH-{idx}",
                note="seed qty",
            )
            db.add(line)
            db.flush()

            db.add(
                InventoryLedger(
                    item_id=item.id,
                    location_id=DEMO_STORES[0][0],
                    entry_type="receive",
                    quantity_delta=Decimal("150.000"),
                    reservation_delta=Decimal("0.000"),
                    document_id=document.id,
                    document_line_id=line.id,
                    order_reference=f"S{DEMO_STORES[0][0]}-SEED-RECV",
                    batch_no=f"BATCH-{idx}",
                )
            )
            db.add(
                InventoryLedger(
                    item_id=item.id,
                    location_id=DEMO_STORES[0][0],
                    entry_type="transfer_out",
                    quantity_delta=Decimal("-45.000"),
                    reservation_delta=Decimal("0.000"),
                    order_reference=f"S{DEMO_STORES[0][0]}-SEED-OUT",
                    batch_no=f"BATCH-{idx}",
                )
            )
            created_ledgers += 2

    return created_items, created_ledgers


def _ensure_training_seed(db: Session, actor_user_id: int | None) -> tuple[int, int, int, int, int]:
    created_topics = 0
    created_questions = 0
    created_assignments = 0
    created_states = 0
    created_snapshots = 0

    topics_config = [
        (
            "SAFE-CASH-HANDLING",
            "Safe Cash Handling",
            "medium",
            [
                (
                    "When should a cashier perform a till drop?",
                    "At threshold and shift close",
                    "Only at opening",
                    "At threshold and shift close",
                    "Only when requested",
                    "Never during business",
                ),
                (
                    "What is required for refund approval?",
                    "Manager override",
                    "Cashier signature",
                    "Manager override",
                    "Customer phone number",
                    "Verbal confirmation only",
                ),
            ],
        ),
        (
            "COLD-CHAIN-BASICS",
            "Cold Chain Basics",
            "easy",
            [
                (
                    "What action is required when freezer temp exceeds threshold?",
                    "Escalate and quarantine stock",
                    "Ignore for 30 minutes",
                    "Escalate and quarantine stock",
                    "Restart POS terminal",
                    "Reduce shelf labels",
                ),
            ],
        ),
    ]

    for topic_code, topic_name, difficulty, questions in topics_config:
        topic = db.execute(select(QuizTopic).where(QuizTopic.code == topic_code)).scalar_one_or_none()
        if not topic:
            topic = QuizTopic(
                code=topic_code,
                name=topic_name,
                difficulty=difficulty,
                created_by_user_id=actor_user_id,
            )
            db.add(topic)
            db.flush()
            created_topics += 1

        for question_text, correct_answer, option_a, option_b, option_c, option_d in questions:
            existing_question = db.execute(
                select(QuizQuestion).where(
                    QuizQuestion.topic_id == topic.id,
                    QuizQuestion.question_text == question_text,
                )
            ).scalar_one_or_none()
            if existing_question:
                continue

            question = QuizQuestion(
                topic_id=topic.id,
                question_text=question_text,
                correct_answer=correct_answer,
                option_a=option_a,
                option_b=option_b,
                option_c=option_c,
                option_d=option_d,
            )
            db.add(question)
            db.flush()
            created_questions += 1

            db.add(
                QuizAttempt(
                    employee_user_id=1,
                    topic_id=topic.id,
                    question_id=question.id,
                    selected_answer=correct_answer,
                    is_correct=True,
                    attempted_at=datetime.now(timezone.utc) - timedelta(days=2),
                )
            )

        employee = db.execute(select(User).where(User.username == "employee")).scalar_one_or_none()
        if employee:
            existing_assignment = db.execute(
                select(QuizAssignment).where(
                    QuizAssignment.employee_user_id == employee.id,
                    QuizAssignment.topic_id == topic.id,
                )
            ).scalar_one_or_none()
            if not existing_assignment:
                db.add(
                    QuizAssignment(
                        employee_user_id=employee.id,
                        topic_id=topic.id,
                        assigned_by_user_id=actor_user_id,
                        active=True,
                    )
                )
                created_assignments += 1

            existing_state = db.execute(
                select(SpacedRepetitionState).where(
                    SpacedRepetitionState.employee_user_id == employee.id,
                    SpacedRepetitionState.topic_id == topic.id,
                )
            ).scalar_one_or_none()
            if not existing_state:
                db.add(
                    SpacedRepetitionState(
                        employee_user_id=employee.id,
                        topic_id=topic.id,
                        next_review_date=date.today() + timedelta(days=2),
                        interval_days=2,
                        consecutive_correct=2,
                        recent_misses=0,
                        ease_factor=Decimal("2.600"),
                        recommendation_reason="Seeded review due soon",
                    )
                )
                created_states += 1

            existing_snapshot = db.execute(
                select(ReviewQueueSnapshot).where(
                    ReviewQueueSnapshot.employee_user_id == employee.id,
                    ReviewQueueSnapshot.topic_id == topic.id,
                    ReviewQueueSnapshot.due_date == date.today() + timedelta(days=2),
                )
            ).scalar_one_or_none()
            if not existing_snapshot:
                db.add(
                    ReviewQueueSnapshot(
                        employee_user_id=employee.id,
                        topic_id=topic.id,
                        due_date=date.today() + timedelta(days=2),
                        recommendation_reason="Seeded review due soon",
                    )
                )
                created_snapshots += 1

    return (
        created_topics,
        created_questions,
        created_assignments,
        created_states,
        created_snapshots,
    )


def _ensure_dashboard_seed(db: Session, actor_user_id: int | None) -> int:
    existing = db.execute(select(func.count(DashboardLayout.id))).scalar_one()
    if existing and existing > 0:
        return 0

    layout_json = [
        {
            "id": "seed-kpi-revenue",
            "kind": "kpi",
            "title": "Revenue",
            "metric": "revenue",
            "dimension": None,
            "x": 0,
            "y": 0,
            "w": 4,
            "h": 2,
        },
        {
            "id": "seed-trend-orders",
            "kind": "trend",
            "title": "Orders Trend",
            "metric": "orders",
            "dimension": "date",
            "x": 4,
            "y": 0,
            "w": 8,
            "h": 3,
        },
        {
            "id": "seed-breakdown-store",
            "kind": "breakdown",
            "title": "Store Breakdown",
            "metric": "gross_margin",
            "dimension": "store",
            "x": 0,
            "y": 3,
            "w": 6,
            "h": 3,
        },
    ]

    db.add(
        DashboardLayout(
            name="Regional Performance Starter",
            description="Seeded dashboard for demo journeys",
            layout_json=str(layout_json).replace("'", '"'),
            allowed_store_ids_json="[101,102,103]",
            default_start_date=date.today() - timedelta(days=13),
            default_end_date=date.today(),
            created_by_user_id=actor_user_id,
            is_archived=False,
        )
    )
    return 1


def seed_demo_data(db: Session, current_user: AuthUser) -> dict[str, int]:
    members = [
        _ensure_member(db, "MEM-DEMO-001", "Amina Retail", "silver", True),
        _ensure_member(db, "MEM-DEMO-002", "Noah Checkout", "gold", True),
        _ensure_member(db, "MEM-DEMO-003", "Lina Operations", "base", False),
    ]

    campaign = _ensure_campaign(db, current_user.id)

    created_coupons = 0
    for member in members[:2]:
        coupon_code = f"CPN-SEED-{member.member_code[-3:]}"
        coupon = db.execute(select(Coupon).where(Coupon.coupon_code == coupon_code)).scalar_one_or_none()
        if coupon:
            continue

        coupon = Coupon(
            campaign_id=campaign.id,
            coupon_code=coupon_code,
            issuance_method="account_assignment",
            member_id=member.id,
            issued_by_user_id=current_user.id,
            assigned_at=datetime.now(timezone.utc) - timedelta(days=5),
            redeemed_at=datetime.now(timezone.utc) - timedelta(days=4),
            redeemed_by_user_id=current_user.id,
            order_reference=f"S101-{member.member_code}-ORDER",
            redemption_member_id=member.id,
        )
        db.add(coupon)
        db.flush()

        db.add(
            CouponIssuanceEvent(
                coupon_id=coupon.id,
                campaign_id=campaign.id,
                member_id=member.id,
                operator_user_id=current_user.id,
                channel="account_assignment",
                qr_payload=None,
            )
        )

        db.add(
            CouponRedemptionEvent(
                coupon_id=coupon.id,
                campaign_id=campaign.id,
                member_id=member.id,
                operator_user_id=current_user.id,
                order_reference=f"S101-{member.member_code}-ORDER",
                pre_tax_amount=Decimal("42.50"),
                discount_amount=Decimal("4.25"),
                status="success",
                reason_code="SUCCESS",
                message="Seed redemption",
                created_at=datetime.now(timezone.utc) - timedelta(days=4),
            )
        )
        created_coupons += 1

    created_items, created_ledger_rows = _ensure_inventory_baseline(db)
    created_dashboards = _ensure_dashboard_seed(db, current_user.id)
    (
        created_topics,
        created_training_questions,
        created_training_assignments,
        created_training_states,
        created_training_snapshots,
    ) = _ensure_training_seed(db, current_user.id)

    masked_preview = mask_record(
        {
            "member_code": "MEM-DEMO-001",
            "coupon_code": "CPN-SEED-001",
            "wallet_reference": "WALLET-SEED-001",
            "note": "seed executed",
        },
        {"member_code", "coupon_code", "wallet_reference"},
    )

    audit_event(
        db,
        action="seed.executed",
        resource_type="system",
        resource_id="seed-demo-data",
        actor_user_id=current_user.id,
        detail={
            "members_seeded": len(members),
            "campaigns_seeded": 1,
            "coupons_seeded": created_coupons,
            "inventory_items_seeded": created_items,
            "inventory_ledger_rows_seeded": created_ledger_rows,
            "training_topics_seeded": created_topics,
            "training_questions_seeded": created_training_questions,
            "training_assignments_seeded": created_training_assignments,
            "training_states_seeded": created_training_states,
            "training_snapshots_seeded": created_training_snapshots,
            "dashboards_seeded": created_dashboards,
            "masked_preview": masked_preview,
        },
    )

    return {
        "created_members": len(members),
        "created_campaigns": 1,
        "created_coupons": created_coupons,
        "created_inventory_items": created_items,
        "created_inventory_ledger_rows": created_ledger_rows,
        "created_training_topics": created_topics,
        "created_training_questions": created_training_questions,
        "created_training_assignments": created_training_assignments,
        "created_training_states": created_training_states,
        "created_training_snapshots": created_training_snapshots,
        "created_dashboard_layouts": created_dashboards,
    }
