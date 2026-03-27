from decimal import Decimal


def _login(client, username: str, password: str = "ChangeMeNow123"):
    client.post("/api/v1/auth/logout")
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200


def test_inventory_role_protection(client) -> None:
    _login(client, "employee")
    denied = client.post(
        "/api/v1/inventory/items",
        json={
            "sku": "SKU-DENIED",
            "name": "Denied",
            "unit": "ea",
            "batch_tracking_enabled": False,
            "expiry_tracking_enabled": False,
        },
    )
    assert denied.status_code == 403


def test_inventory_receiving_transfer_reservation_and_count(client) -> None:
    _login(client, "clerk")

    item = client.post(
        "/api/v1/inventory/items",
        json={
            "sku": "SKU-INV-1",
            "name": "Test Item",
            "unit": "ea",
            "batch_tracking_enabled": False,
            "expiry_tracking_enabled": False,
        },
    )
    assert item.status_code == 200

    loc_main = client.post("/api/v1/inventory/locations", json={"code": "MAIN", "name": "Main"})
    loc_back = client.post("/api/v1/inventory/locations", json={"code": "BACK", "name": "Back"})
    assert loc_main.status_code == 200
    assert loc_back.status_code == 200

    receiving = client.post(
        "/api/v1/inventory/receiving",
        json={
            "location_code": "MAIN",
            "lines": [{"sku": "SKU-INV-1", "quantity": "20.000"}],
        },
    )
    assert receiving.status_code == 200

    transfer = client.post(
        "/api/v1/inventory/transfers",
        json={
            "source_location_code": "MAIN",
            "target_location_code": "BACK",
            "lines": [{"sku": "SKU-INV-1", "quantity": "8.000"}],
        },
    )
    assert transfer.status_code == 200

    reserve = client.post(
        "/api/v1/inventory/reservations",
        json={
            "order_reference": "ORDER-1",
            "sku": "SKU-INV-1",
            "location_code": "MAIN",
            "quantity": "5.000",
        },
    )
    assert reserve.status_code == 200
    reservation_id = reserve.json()["id"]

    position_main = client.get("/api/v1/inventory/positions/SKU-INV-1/MAIN")
    assert position_main.status_code == 200
    assert Decimal(position_main.json()["on_hand_qty"]) == Decimal("12.000")
    assert Decimal(position_main.json()["reserved_qty"]) == Decimal("5.000")
    assert Decimal(position_main.json()["available_qty"]) == Decimal("7.000")

    release = client.post("/api/v1/inventory/reservations/release", json={"reservation_id": reservation_id})
    assert release.status_code == 200

    position_after_release = client.get("/api/v1/inventory/positions/SKU-INV-1/MAIN")
    assert position_after_release.status_code == 200
    assert Decimal(position_after_release.json()["reserved_qty"]) == Decimal("0.000")
    assert Decimal(position_after_release.json()["available_qty"]) == Decimal("12.000")

    count = client.post(
        "/api/v1/inventory/counts",
        json={
            "location_code": "MAIN",
            "lines": [{"sku": "SKU-INV-1", "counted_qty": "10.000"}],
        },
    )
    assert count.status_code == 200

    position_after_count = client.get("/api/v1/inventory/positions/SKU-INV-1/MAIN")
    assert position_after_count.status_code == 200
    assert Decimal(position_after_count.json()["on_hand_qty"]) == Decimal("10.000")

    ledger = client.get("/api/v1/inventory/ledger", params={"limit": 20})
    assert ledger.status_code == 200
    assert len(ledger.json()) >= 6
