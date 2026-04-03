"""Tests for security hardening: bcrypt-only, at-rest encryption, audit endpoints."""

import bcrypt

from app.core.security import hash_password, verify_password


def test_bcrypt_only_hash_produces_bcrypt_prefix():
    """Ensure hash_password always produces bcrypt hashes (prefix $2b$)."""
    hashed = hash_password("TestPassword123")
    assert hashed.startswith("$2b$") or hashed.startswith("$2a$")


def test_bcrypt_verify_correct_password():
    hashed = hash_password("SecurePass12345")
    assert verify_password("SecurePass12345", hashed) is True


def test_bcrypt_verify_wrong_password():
    hashed = hash_password("SecurePass12345")
    assert verify_password("WrongPassword99", hashed) is False


def test_bcrypt_module_is_available():
    """bcrypt is now a hard import — this test verifies it doesn't silently fall back."""
    import app.core.security as sec
    # The module should have imported bcrypt directly, not conditionally
    assert hasattr(sec, '_bcrypt')
    assert sec._bcrypt is not None


def test_audit_events_endpoint_requires_auth(client) -> None:
    resp = client.get("/api/v1/audit/events")
    assert resp.status_code == 401


def test_audit_events_endpoint_requires_manager_role(client) -> None:
    _login(client, "employee")
    resp = client.get("/api/v1/audit/events")
    assert resp.status_code == 403


def test_audit_events_accessible_by_admin(client) -> None:
    _login(client, "admin")
    resp = client.get("/api/v1/audit/events")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_audit_member_events_endpoint(client) -> None:
    _login(client, "admin")
    resp = client.get("/api/v1/audit/events/member")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_audit_campaign_events_endpoint(client) -> None:
    _login(client, "admin")
    resp = client.get("/api/v1/audit/events/campaign")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_audit_order_events_endpoint(client) -> None:
    _login(client, "admin")
    resp = client.get("/api/v1/audit/events/order")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_audit_events_filter_by_resource_type(client) -> None:
    _login(client, "admin")
    resp = client.get("/api/v1/audit/events?resource_type=member")
    assert resp.status_code == 200


def test_audit_events_filter_by_action(client) -> None:
    _login(client, "admin")
    resp = client.get("/api/v1/audit/events?action=member")
    assert resp.status_code == 200


def _login(client, username: str, password: str = "ChangeMeNow123"):
    client.post("/api/v1/auth/logout")
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
