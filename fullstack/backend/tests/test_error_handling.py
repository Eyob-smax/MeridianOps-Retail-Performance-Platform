from app.api.v1.endpoints import health as health_endpoint
from app.main import app
from fastapi.testclient import TestClient


def _login(client, username: str, password: str = "ChangeMeNow123"):
    client.post("/api/v1/auth/logout")
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200


def _assert_error_envelope(payload: dict, *, expected_status: int, expected_code: str, expected_path: str):
    assert payload["status_code"] == expected_status
    assert payload["error_code"] == expected_code
    assert payload["path"] == expected_path
    assert isinstance(payload.get("request_id"), str)
    assert len(payload["request_id"]) > 0
    assert isinstance(payload.get("detail"), str)


def test_error_envelope_for_unauthorized(client):
    response = client.get("/api/v1/auth/session")

    assert response.status_code == 401
    assert response.headers.get("X-Request-ID")
    payload = response.json()
    _assert_error_envelope(
        payload,
        expected_status=401,
        expected_code="unauthorized",
        expected_path="/api/v1/auth/session",
    )


def test_error_envelope_for_forbidden(client):
    _login(client, "cashier")
    response = client.get("/api/v1/secure/administrator")

    assert response.status_code == 403
    payload = response.json()
    _assert_error_envelope(
        payload,
        expected_status=403,
        expected_code="forbidden",
        expected_path="/api/v1/secure/administrator",
    )


def test_error_envelope_for_validation_failure(client):
    _login(client, "manager")
    response = client.post("/api/v1/campaigns", json={})

    assert response.status_code == 422
    payload = response.json()
    _assert_error_envelope(
        payload,
        expected_status=422,
        expected_code="validation_error",
        expected_path="/api/v1/campaigns",
    )
    assert payload["detail"] == "Validation failed"
    assert isinstance(payload.get("errors"), list)
    assert len(payload["errors"]) > 0


def test_error_envelope_for_not_found(client):
    response = client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    payload = response.json()
    _assert_error_envelope(
        payload,
        expected_status=404,
        expected_code="not_found",
        expected_path="/api/v1/does-not-exist",
    )


def test_error_envelope_for_unexpected_server_error(client, monkeypatch):
    def boom(*_args, **_kwargs):
        raise RuntimeError("unexpected-failure")

    monkeypatch.setattr(health_endpoint, "get_app_health", boom)
    with TestClient(app, raise_server_exceptions=False) as resilient_client:
        response = resilient_client.get("/api/v1/health")

    assert response.status_code == 500
    payload = response.json()
    _assert_error_envelope(
        payload,
        expected_status=500,
        expected_code="internal_server_error",
        expected_path="/api/v1/health",
    )
    assert payload["detail"] == "Internal server error"
