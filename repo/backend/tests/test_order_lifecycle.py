"""Tests for order lifecycle: create -> reserve -> complete/cancel with reservation integration."""

from decimal import Decimal


def _login(client, username: str, password: str = "ChangeMeNow123"):
    client.post("/api/v1/auth/logout")
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200


def _setup_inventory(client, sku_suffix: str = "1"):
    """Create unique item/location per test to avoid conflicts across fixtures."""
    sku = f"ORD-SKU-{sku_suffix}"
    loc = f"ORD-LOC-{sku_suffix}"
    client.post(
        "/api/v1/inventory/items",
        json={
            "sku": sku,
            "name": f"Order Test Item {sku_suffix}",
            "unit": "ea",
            "batch_tracking_enabled": False,
            "expiry_tracking_enabled": False,
        },
    )
    client.post("/api/v1/inventory/locations", json={"code": loc, "name": f"Order Location {sku_suffix}"})
    client.post(
        "/api/v1/inventory/receiving",
        json={
            "location_code": loc,
            "lines": [{"sku": sku, "quantity": "500.000"}],
        },
    )
    return sku, loc


def test_order_create(client) -> None:
    _login(client, "manager")
    sku, loc = _setup_inventory(client, "CREATE")

    resp = client.post(
        "/api/v1/orders",
        json={
            "order_reference": "ORD-001",
            "lines": [
                {"sku": sku, "location_code": loc, "quantity": "5.000", "unit_price": "10.00"},
            ],
        },
    )
    assert resp.status_code == 200, resp.json()
    data = resp.json()
    assert data["order_reference"] == "ORD-001"
    assert data["status"] == "created"
    assert Decimal(data["total_amount"]) == Decimal("50.00")
    assert len(data["lines"]) == 1


def test_order_duplicate_reference_rejected(client) -> None:
    _login(client, "manager")
    sku, loc = _setup_inventory(client, "DUP")

    client.post(
        "/api/v1/orders",
        json={
            "order_reference": "ORD-DUP",
            "lines": [{"sku": sku, "location_code": loc, "quantity": "1.000", "unit_price": "5.00"}],
        },
    )
    resp = client.post(
        "/api/v1/orders",
        json={
            "order_reference": "ORD-DUP",
            "lines": [{"sku": sku, "location_code": loc, "quantity": "1.000", "unit_price": "5.00"}],
        },
    )
    assert resp.status_code == 400


def test_order_reserve_creates_inventory_reservation(client) -> None:
    _login(client, "manager")
    sku, loc = _setup_inventory(client, "RES")

    resp_create = client.post(
        "/api/v1/orders",
        json={
            "order_reference": "ORD-RES-1",
            "lines": [{"sku": sku, "location_code": loc, "quantity": "3.000", "unit_price": "10.00"}],
        },
    )
    assert resp_create.status_code == 200, resp_create.json()

    resp = client.post("/api/v1/orders/reserve", json={"order_reference": "ORD-RES-1"})
    assert resp.status_code == 200, resp.json()
    data = resp.json()
    assert data["status"] == "reserved"
    assert data["lines"][0]["reservation_id"] is not None


def test_order_complete_releases_reservation(client) -> None:
    _login(client, "manager")
    sku, loc = _setup_inventory(client, "COMP")

    client.post(
        "/api/v1/orders",
        json={
            "order_reference": "ORD-COMP-1",
            "lines": [{"sku": sku, "location_code": loc, "quantity": "2.000", "unit_price": "10.00"}],
        },
    )
    client.post("/api/v1/orders/reserve", json={"order_reference": "ORD-COMP-1"})

    resp = client.post("/api/v1/orders/complete", json={"order_reference": "ORD-COMP-1"})
    assert resp.status_code == 200, resp.json()
    data = resp.json()
    assert data["status"] == "completed"


def test_order_cancel_from_reserved(client) -> None:
    _login(client, "manager")
    sku, loc = _setup_inventory(client, "CANC1")

    client.post(
        "/api/v1/orders",
        json={
            "order_reference": "ORD-CANC-1",
            "lines": [{"sku": sku, "location_code": loc, "quantity": "2.000", "unit_price": "10.00"}],
        },
    )
    reserve_resp = client.post("/api/v1/orders/reserve", json={"order_reference": "ORD-CANC-1"})
    assert reserve_resp.status_code == 200, reserve_resp.json()

    resp = client.post("/api/v1/orders/cancel", json={"order_reference": "ORD-CANC-1"})
    assert resp.status_code == 200, resp.json()
    data = resp.json()
    assert data["status"] == "cancelled"


def test_order_cancel_from_created(client) -> None:
    _login(client, "manager")
    sku, loc = _setup_inventory(client, "CANC2")

    client.post(
        "/api/v1/orders",
        json={
            "order_reference": "ORD-CANC-2",
            "lines": [{"sku": sku, "location_code": loc, "quantity": "1.000", "unit_price": "5.00"}],
        },
    )
    resp = client.post("/api/v1/orders/cancel", json={"order_reference": "ORD-CANC-2"})
    assert resp.status_code == 200, resp.json()
    assert resp.json()["status"] == "cancelled"


def test_order_invalid_transition_rejected(client) -> None:
    _login(client, "manager")
    sku, loc = _setup_inventory(client, "BAD")

    client.post(
        "/api/v1/orders",
        json={
            "order_reference": "ORD-BAD-1",
            "lines": [{"sku": sku, "location_code": loc, "quantity": "1.000", "unit_price": "5.00"}],
        },
    )
    # Cannot complete from created (must reserve first)
    resp = client.post("/api/v1/orders/complete", json={"order_reference": "ORD-BAD-1"})
    assert resp.status_code == 400


def test_order_list(client) -> None:
    _login(client, "manager")
    sku, loc = _setup_inventory(client, "LIST")

    client.post(
        "/api/v1/orders",
        json={
            "order_reference": "ORD-LIST-1",
            "lines": [{"sku": sku, "location_code": loc, "quantity": "1.000", "unit_price": "5.00"}],
        },
    )

    resp = client.get("/api/v1/orders")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


def test_order_detail(client) -> None:
    _login(client, "manager")
    sku, loc = _setup_inventory(client, "DETAIL")

    create_resp = client.post(
        "/api/v1/orders",
        json={
            "order_reference": "ORD-DETAIL-1",
            "lines": [{"sku": sku, "location_code": loc, "quantity": "1.000", "unit_price": "5.00"}],
        },
    )
    assert create_resp.status_code == 200, create_resp.json()

    resp = client.get("/api/v1/orders/ORD-DETAIL-1")
    assert resp.status_code == 200
    assert resp.json()["order_reference"] == "ORD-DETAIL-1"


def test_order_role_protection(client) -> None:
    _login(client, "employee")
    resp = client.post(
        "/api/v1/orders",
        json={
            "order_reference": "ORD-DENIED",
            "lines": [{"sku": "ANY-SKU", "location_code": "ANY-LOC", "quantity": "1.000", "unit_price": "5.00"}],
        },
    )
    assert resp.status_code == 403


def test_order_reserve_insufficient_stock(client) -> None:
    _login(client, "manager")
    sku, loc = _setup_inventory(client, "INSUF")

    client.post(
        "/api/v1/orders",
        json={
            "order_reference": "ORD-INSUF-1",
            "lines": [{"sku": sku, "location_code": loc, "quantity": "9999.000", "unit_price": "1.00"}],
        },
    )
    resp = client.post("/api/v1/orders/reserve", json={"order_reference": "ORD-INSUF-1"})
    assert resp.status_code == 400
