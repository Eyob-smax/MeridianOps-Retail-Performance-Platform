def test_health_endpoint(client):
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["api_status"]["status"] == "ok"


def test_database_health_endpoint_handles_unavailable_database(client, monkeypatch):
    from app.schemas.health import HealthCheck
    from app.services import health_service

    def fake_database_health() -> HealthCheck:
        return HealthCheck(status="degraded", detail="Database unavailable")

    monkeypatch.setattr(health_service, "get_database_health", fake_database_health)

    response = client.get("/api/v1/health/database")

    assert response.status_code == 503
    payload = response.json()
    assert payload["database_status"]["status"] == "degraded"
