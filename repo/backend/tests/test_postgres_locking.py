from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.models import Campaign, CouponRedemptionEvent, InventoryLedger, InventoryLocation, InventoryReservation
from app.schemas.auth import AuthUser
from app.schemas.campaigns import CouponRedeemRequest
from app.schemas.inventory import ReservationCreateRequest, TransferRequest, InventoryDocumentLineInput
from app.services.campaign_service import redeem_coupon
from app.services.inventory_service import create_reservation, post_transfer, InventoryError


def _pg_url() -> str | None:
    return os.getenv("POSTGRES_TEST_DATABASE_URL")


def _is_truthy_env(name: str) -> bool:
    value = os.getenv(name, "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _require_postgres_locking_tests() -> bool:
    return _is_truthy_env("REQUIRE_POSTGRES_LOCKING_TESTS") or _is_truthy_env("CI")


@pytest.fixture(scope="module")
def pg_engine():
    url = _pg_url()
    if not url:
        if _require_postgres_locking_tests():
            pytest.fail(
                "POSTGRES_TEST_DATABASE_URL is required when CI or REQUIRE_POSTGRES_LOCKING_TESTS=1"
            )
        pytest.skip("POSTGRES_TEST_DATABASE_URL is not set; skipping PostgreSQL locking tests")

    engine = create_engine(url, future=True)
    Base.metadata.create_all(bind=engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def pg_session_factory(pg_engine):
    return sessionmaker(bind=pg_engine, autoflush=False, autocommit=False, class_=Session)


@pytest.fixture
def seeded_coupon(pg_session_factory):
    with pg_session_factory() as db:
        campaign = Campaign(
            name="PG Lock Campaign",
            campaign_type="fixed_amount",
            effective_start=date(2026, 1, 1),
            effective_end=date(2027, 12, 31),
            daily_redemption_cap=200,
            per_member_daily_limit=1,
            fixed_amount_off=Decimal("10.00"),
            is_active=True,
        )
        db.add(campaign)
        db.flush()

        from app.db.models import Coupon

        coupon = Coupon(
            campaign_id=campaign.id,
            coupon_code="CPN-PG-LOCK-001",
            issuance_method="printable_qr",
            member_id=None,
            issued_by_user_id=None,
        )
        db.add(coupon)
        db.commit()
        return coupon.coupon_code, campaign.id


@pytest.fixture
def seeded_inventory(pg_session_factory):
    with pg_session_factory() as db:
        from app.db.models import InventoryItem

        item = InventoryItem(
            sku="SKU-PG-LOCK-1",
            name="PG Lock Item",
            unit="ea",
            batch_tracking_enabled=False,
            expiry_tracking_enabled=False,
        )
        loc = InventoryLocation(code="MAIN-PG", name="Main PG")
        db.add(item)
        db.add(loc)
        db.flush()

        db.add(
            InventoryLedger(
                item_id=item.id,
                location_id=loc.id,
                entry_type="seed",
                quantity_delta=Decimal("5.000"),
                reservation_delta=Decimal("0.000"),
            )
        )
        db.commit()
        return item.sku, loc.code


def test_postgres_coupon_redeem_is_single_winner_under_concurrency(pg_session_factory, seeded_coupon):
    coupon_code, campaign_id = seeded_coupon

    def attempt(order_ref: str):
        with pg_session_factory() as db:
            result = redeem_coupon(
                db,
                CouponRedeemRequest(
                    coupon_code=coupon_code,
                    member_code=None,
                    pre_tax_amount=Decimal("50.00"),
                    order_reference=order_ref,
                ),
                operator_user_id=None,
            )
            db.commit()
            return result.reason_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(attempt, "PG-ORDER-1")
        second = pool.submit(attempt, "PG-ORDER-2")

    outcomes = sorted([first.result(), second.result()])
    assert outcomes == ["ALREADY_REDEEMED", "SUCCESS"]

    with pg_session_factory() as db:
        success_count = db.execute(
            select(CouponRedemptionEvent).where(
                CouponRedemptionEvent.campaign_id == campaign_id,
                CouponRedemptionEvent.status == "success",
            )
        ).scalars().all()
        assert len(success_count) == 1


def test_postgres_inventory_reservation_prevents_double_spend(pg_session_factory, seeded_inventory):
    sku, location_code = seeded_inventory
    actor = AuthUser(id=1, username="pg-user", display_name="pg-user", roles=["inventory_clerk"])

    def reserve(order_ref: str):
        with pg_session_factory() as db:
            try:
                response = create_reservation(
                    db,
                    ReservationCreateRequest(
                        order_reference=order_ref,
                        sku=sku,
                        location_code=location_code,
                        quantity=Decimal("4.000"),
                    ),
                    actor,
                )
                db.commit()
                return response.status
            except Exception as exc:  # noqa: BLE001
                db.rollback()
                return str(exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(reserve, "ORDER-PG-1")
        second = pool.submit(reserve, "ORDER-PG-2")

    outcomes = [first.result(), second.result()]
    success_count = sum(1 for item in outcomes if item == "open")
    assert success_count == 1
    assert any("Insufficient available stock" in item for item in outcomes if item != "open")

    with pg_session_factory() as db:
        reservations = db.execute(select(InventoryReservation)).scalars().all()
        assert len(reservations) == 1
        assert reservations[0].reserved_qty == Decimal("4.000")


@pytest.fixture
def seeded_transfer_inventory(pg_session_factory):
    """Seed two locations with stock for transfer concurrency tests."""
    with pg_session_factory() as db:
        from app.db.models import InventoryItem

        item = InventoryItem(
            sku="SKU-PG-XFER",
            name="Transfer Lock Item",
            unit="ea",
            batch_tracking_enabled=False,
            expiry_tracking_enabled=False,
        )
        source = InventoryLocation(code="SRC-PG", name="Source PG")
        target = InventoryLocation(code="TGT-PG", name="Target PG")
        db.add(item)
        db.add(source)
        db.add(target)
        db.flush()

        # Seed 5 units at source
        db.add(
            InventoryLedger(
                item_id=item.id,
                location_id=source.id,
                entry_type="seed",
                quantity_delta=Decimal("5.000"),
                reservation_delta=Decimal("0.000"),
            )
        )
        db.commit()
        return item.sku, source.code, target.code


def test_postgres_transfer_prevents_double_spend(pg_session_factory, seeded_transfer_inventory):
    """Two concurrent transfers of 4 units from same source (only 5 available) — only one should succeed."""
    sku, source_code, target_code = seeded_transfer_inventory
    # Use a seeded user so FK constraints are satisfied on the PG database.
    from app.db.models import User
    from app.core.security import hash_password
    with pg_session_factory() as db:
        existing = db.execute(select(User).where(User.username == "pg_xfer_user")).scalar_one_or_none()
        if not existing:
            u = User(username="pg_xfer_user", display_name="PG Xfer", password_hash=hash_password("Dummy12345678"))
            db.add(u)
            db.commit()
            user_id = u.id
        else:
            user_id = existing.id
    actor = AuthUser(id=user_id, store_id=None, username="pg_xfer_user", display_name="PG Xfer", roles=["inventory_clerk"])

    def transfer():
        with pg_session_factory() as db:
            try:
                post_transfer(
                    db,
                    TransferRequest(
                        source_location_code=source_code,
                        target_location_code=target_code,
                        lines=[InventoryDocumentLineInput(sku=sku, quantity=Decimal("4.000"))],
                    ),
                    actor,
                )
                db.commit()
                return "success"
            except (InventoryError, Exception) as exc:
                db.rollback()
                return str(exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(transfer)
        second = pool.submit(transfer)

    outcomes = [first.result(), second.result()]
    success_count = sum(1 for o in outcomes if o == "success")
    fail_count = sum(1 for o in outcomes if "Insufficient" in o)
    assert success_count == 1, f"Expected exactly 1 success, got outcomes: {outcomes}"
    assert fail_count == 1, f"Expected exactly 1 insufficient-stock failure, got outcomes: {outcomes}"
