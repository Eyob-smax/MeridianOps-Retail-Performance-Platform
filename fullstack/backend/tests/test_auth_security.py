from decimal import Decimal

from app.core.encryption import FieldEncryptor
from app.core.config import settings
from app.core.masking import mask_record, mask_sensitive
from app.core.security import password_is_valid


def _login(client, username: str, password: str):
    return client.post("/api/v1/auth/login", json={"username": username, "password": password})


def test_password_policy_enforced() -> None:
    assert password_is_valid("123456789012") is True
    assert password_is_valid("short") is False


def test_login_and_session_flow(client) -> None:
    response = _login(client, "admin", "ChangeMeNow123")
    assert response.status_code == 200
    payload = response.json()
    assert payload["user"]["username"] == "admin"
    assert "administrator" in payload["user"]["roles"]

    session_response = client.get("/api/v1/auth/session")
    assert session_response.status_code == 200
    assert session_response.json()["authenticated"] is True

    logout_response = client.post("/api/v1/auth/logout")
    assert logout_response.status_code == 200

    session_after_logout = client.get("/api/v1/auth/session")
    assert session_after_logout.status_code == 401


def test_lockout_after_five_failures(client) -> None:
    status = 0
    payload: dict[str, str] = {}
    for _ in range(5):
        response = _login(client, "manager", "wrongpassword123")
        status = response.status_code
        payload = response.json()

    assert status == 401
    assert "locked" in payload["detail"].lower()

    locked_response = _login(client, "manager", "ChangeMeNow123")
    assert locked_response.status_code == 401
    assert "locked" in locked_response.json()["detail"].lower()


def test_unauthenticated_secure_endpoint_returns_401(client) -> None:
    response = client.get("/api/v1/secure/administrator")
    assert response.status_code == 401


def test_rbac_matrix(client) -> None:
    cases = [
        ("admin", "/api/v1/secure/administrator", 200),
        ("cashier", "/api/v1/secure/administrator", 403),
        ("manager", "/api/v1/secure/store-manager", 200),
        ("cashier", "/api/v1/secure/store-manager", 403),
        ("clerk", "/api/v1/secure/inventory-clerk", 200),
        ("employee", "/api/v1/secure/inventory-clerk", 403),
        ("cashier", "/api/v1/secure/cashier", 200),
        ("employee", "/api/v1/secure/cashier", 403),
        ("employee", "/api/v1/secure/employee", 200),
        ("cashier", "/api/v1/secure/employee", 403),
    ]

    for username, endpoint, expected_status in cases:
        client.post("/api/v1/auth/logout")
        login_response = _login(client, username, "ChangeMeNow123")
        assert login_response.status_code == 200

        response = client.get(endpoint)
        assert response.status_code == expected_status


def test_masking_helpers() -> None:
    assert mask_sensitive("sensitive") == "se***ve"
    assert mask_sensitive("abc") == "***"

    masked = mask_record(
        {"member_name": "Jane Doe", "wallet": "123456789", "points": 120},
        {"wallet", "member_name"},
    )
    assert masked["wallet"] == "12***89"
    assert masked["member_name"] == "Ja***oe"
    assert masked["points"] == 120


def test_optional_encryption_layer() -> None:
    encryptor = FieldEncryptor("local-test-key")
    encrypted = encryptor.encrypt("secret-value")

    assert encrypted is not None
    assert encrypted != "secret-value"
    assert encryptor.decrypt(encrypted) == "secret-value"


def test_member_points_and_wallet_flow(client) -> None:
    _login(client, "manager", "ChangeMeNow123")

    create_payload = {
        "member_code": "MEM-001",
        "full_name": "Jane Store",
        "tier": "silver",
        "stored_value_enabled": True,
    }
    created = client.post("/api/v1/members", json=create_payload)
    assert created.status_code == 200
    assert created.json()["tier"] == "silver"

    accrue = client.post(
        "/api/v1/members/MEM-001/points/accrue",
        json={"pre_tax_amount": "19.99", "reason": "purchase"},
    )
    assert accrue.status_code == 200
    assert accrue.json()["points_balance"] == 19

    adjust = client.post(
        "/api/v1/members/MEM-001/points/adjust",
        json={"points_delta": -4, "reason": "manual correction"},
    )
    assert adjust.status_code == 200
    assert adjust.json()["points_balance"] == 15

    credit = client.post(
        "/api/v1/members/MEM-001/wallet/credit",
        json={"amount": "50.00", "reason": "top up"},
    )
    assert credit.status_code == 200
    assert Decimal(credit.json()["wallet_balance"]) == Decimal("50.00")

    debit = client.post(
        "/api/v1/members/MEM-001/wallet/debit",
        json={"amount": "20.25", "reason": "purchase"},
    )
    assert debit.status_code == 200
    assert Decimal(debit.json()["wallet_balance"]) == Decimal("29.75")

    over_debit = client.post(
        "/api/v1/members/MEM-001/wallet/debit",
        json={"amount": "30.00", "reason": "too much"},
    )
    assert over_debit.status_code == 400
    assert "insufficient" in over_debit.json()["detail"].lower()

    points_ledger = client.get("/api/v1/members/MEM-001/points-ledger")
    assert points_ledger.status_code == 200
    assert len(points_ledger.json()) >= 2

    wallet_ledger = client.get("/api/v1/members/MEM-001/wallet-ledger")
    assert wallet_ledger.status_code == 200
    assert len(wallet_ledger.json()) >= 2


def test_campaign_issue_and_redeem_flow(client) -> None:
    _login(client, "manager", "ChangeMeNow123")

    member_resp = client.post(
        "/api/v1/members",
        json={
            "member_code": "MEM-CAMPAIGN",
            "full_name": "Campaign Member",
            "tier": "gold",
            "stored_value_enabled": True,
        },
    )
    assert member_resp.status_code == 200

    campaign_resp = client.post(
        "/api/v1/campaigns",
        json={
            "name": "Spring 10 Off 50",
            "campaign_type": "full_reduction",
            "effective_start": "2026-01-01",
            "effective_end": "2027-12-31",
            "daily_redemption_cap": 200,
            "per_member_daily_limit": 1,
            "fixed_amount_off": "10.00",
            "threshold_amount": "50.00",
        },
    )
    assert campaign_resp.status_code == 200
    campaign_id = campaign_resp.json()["id"]

    issue_resp = client.post(
        "/api/v1/campaigns/issue",
        json={
            "campaign_id": campaign_id,
            "issuance_method": "account_assignment",
            "member_code": "MEM-CAMPAIGN",
        },
    )
    assert issue_resp.status_code == 200
    coupon_code = issue_resp.json()["coupon_code"]

    threshold_fail = client.post(
        "/api/v1/campaigns/redeem",
        json={
            "coupon_code": coupon_code,
            "member_code": "MEM-CAMPAIGN",
            "pre_tax_amount": "49.99",
            "order_reference": "ORDER-FAIL-1",
        },
    )
    assert threshold_fail.status_code == 200
    assert threshold_fail.json()["reason_code"] == "THRESHOLD_NOT_MET"

    redeem_ok = client.post(
        "/api/v1/campaigns/redeem",
        json={
            "coupon_code": coupon_code,
            "member_code": "MEM-CAMPAIGN",
            "pre_tax_amount": "88.50",
            "order_reference": "ORDER-OK-1",
        },
    )
    assert redeem_ok.status_code == 200
    assert redeem_ok.json()["success"] is True
    assert redeem_ok.json()["discount_amount"] == "10.00"
    assert redeem_ok.json()["final_amount"] == "78.50"

    redeem_again = client.post(
        "/api/v1/campaigns/redeem",
        json={
            "coupon_code": coupon_code,
            "member_code": "MEM-CAMPAIGN",
            "pre_tax_amount": "88.50",
            "order_reference": "ORDER-OK-2",
        },
    )
    assert redeem_again.status_code == 200
    assert redeem_again.json()["reason_code"] == "ALREADY_REDEEMED"


def test_campaign_member_daily_limit(client) -> None:
    _login(client, "manager", "ChangeMeNow123")

    create_member = client.post(
        "/api/v1/members",
        json={
            "member_code": "MEM-LIMIT",
            "full_name": "Limit Member",
            "tier": "base",
            "stored_value_enabled": False,
        },
    )
    assert create_member.status_code == 200

    campaign_resp = client.post(
        "/api/v1/campaigns",
        json={
            "name": "One Per Day",
            "campaign_type": "percent_off",
            "effective_start": "2026-01-01",
            "effective_end": "2027-12-31",
            "daily_redemption_cap": 200,
            "per_member_daily_limit": 1,
            "percent_off": "0.10",
        },
    )
    assert campaign_resp.status_code == 200
    campaign_id = campaign_resp.json()["id"]

    first_issue = client.post(
        "/api/v1/campaigns/issue",
        json={
            "campaign_id": campaign_id,
            "issuance_method": "account_assignment",
            "member_code": "MEM-LIMIT",
        },
    )
    assert first_issue.status_code == 200

    second_issue = client.post(
        "/api/v1/campaigns/issue",
        json={
            "campaign_id": campaign_id,
            "issuance_method": "account_assignment",
            "member_code": "MEM-LIMIT",
        },
    )
    assert second_issue.status_code == 200

    first_redeem = client.post(
        "/api/v1/campaigns/redeem",
        json={
            "coupon_code": first_issue.json()["coupon_code"],
            "member_code": "MEM-LIMIT",
            "pre_tax_amount": "100.00",
            "order_reference": "LIMIT-1",
        },
    )
    assert first_redeem.status_code == 200
    assert first_redeem.json()["success"] is True

    second_redeem = client.post(
        "/api/v1/campaigns/redeem",
        json={
            "coupon_code": second_issue.json()["coupon_code"],
            "member_code": "MEM-LIMIT",
            "pre_tax_amount": "100.00",
            "order_reference": "LIMIT-2",
        },
    )
    assert second_redeem.status_code == 200
    assert second_redeem.json()["reason_code"] == "MEMBER_DAILY_LIMIT_REACHED"


def test_login_cookie_secure_flag_disabled_for_local_env(client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "app_env", "local")
    response = _login(client, "admin", "ChangeMeNow123")
    set_cookie = response.headers.get("set-cookie", "").lower()
    assert "secure" not in set_cookie


def test_login_cookie_secure_flag_enabled_for_non_local_env(client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "app_env", "production")
    response = _login(client, "admin", "ChangeMeNow123")
    set_cookie = response.headers.get("set-cookie", "").lower()
    assert "secure" in set_cookie
