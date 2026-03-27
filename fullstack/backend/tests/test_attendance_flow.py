from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db.models import RotatingQRToken


def _login(client, username: str, password: str = "ChangeMeNow123"):
    client.post("/api/v1/auth/logout")
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200


def test_attendance_checkin_checkout_makeup_and_export(client):
    _login(client, "manager")

    policy = client.get("/api/v1/attendance/rules")
    assert policy.status_code == 200
    assert policy.json()["tolerance_minutes"] == 5

    qr_for_employee = client.post("/api/v1/attendance/qr/rotate")
    assert qr_for_employee.status_code == 200
    token1 = qr_for_employee.json()["token"]

    _login(client, "employee")

    now = datetime.now(timezone.utc)
    check_in = client.post(
        "/api/v1/attendance/check-in",
        json={
            "device_id": "DEVICE-EMP-1",
            "qr_token": token1,
            "check_in_at": (now - timedelta(hours=8)).isoformat(),
            "scheduled_start_at": (now - timedelta(hours=8, minutes=10)).isoformat(),
            "scheduled_end_at": now.isoformat(),
            "latitude": "9.012345",
            "longitude": "38.765432",
        },
    )
    assert check_in.status_code == 200
    assert check_in.json()["status"] == "open"

    _login(client, "manager")
    qr_for_checkout = client.post("/api/v1/attendance/qr/rotate")
    assert qr_for_checkout.status_code == 200
    token2 = qr_for_checkout.json()["token"]

    _login(client, "employee")
    check_out = client.post(
        "/api/v1/attendance/check-out",
        json={
            "device_id": "DEVICE-EMP-1",
            "qr_token": token2,
            "check_out_at": now.isoformat(),
            "latitude": "9.012346",
            "longitude": "38.765433",
        },
    )
    assert check_out.status_code == 200
    payload = check_out.json()
    assert payload["shift"]["status"] == "closed"
    assert float(payload["daily_result"]["worked_hours"]) > 0

    shifts = client.get("/api/v1/attendance/me/shifts")
    assert shifts.status_code == 200
    assert len(shifts.json()) >= 1

    makeup = client.post(
        "/api/v1/attendance/makeup-requests",
        json={"business_date": now.date().isoformat(), "reason": "Delayed due to stock count support."},
    )
    assert makeup.status_code == 200
    request_id = makeup.json()["id"]

    _login(client, "manager")
    approve = client.post(
        f"/api/v1/attendance/makeup-requests/{request_id}/approve",
        json={"manager_note": "Approved after CCTV and floor lead review."},
    )
    assert approve.status_code == 200
    assert approve.json()["status"] == "approved"

    export_csv = client.get(
        "/api/v1/attendance/payroll-export",
        params={"start_date": now.date().isoformat(), "end_date": now.date().isoformat()},
    )
    assert export_csv.status_code == 200
    assert "text/csv" in export_csv.headers.get("content-type", "")
    assert "worked_hours" in export_csv.text


def test_attendance_rejects_expired_qr_token(client, db_session):
    _login(client, "manager")
    qr = client.post("/api/v1/attendance/qr/rotate")
    assert qr.status_code == 200
    token = qr.json()["token"]

    qr_row = db_session.execute(select(RotatingQRToken).where(RotatingQRToken.token == token)).scalar_one()
    qr_row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.commit()

    _login(client, "employee")
    response = client.post(
        "/api/v1/attendance/check-in",
        json={
            "device_id": "DEVICE-EMP-EXPIRED",
            "qr_token": token,
        },
    )
    assert response.status_code == 400
    assert "expired" in response.json()["detail"].lower()


def test_attendance_rejects_device_binding_mismatch(client):
    _login(client, "manager")
    checkin_qr = client.post("/api/v1/attendance/qr/rotate")
    assert checkin_qr.status_code == 200

    _login(client, "employee")
    check_in = client.post(
        "/api/v1/attendance/check-in",
        json={
            "device_id": "DEVICE-BOUND-1",
            "qr_token": checkin_qr.json()["token"],
        },
    )
    assert check_in.status_code == 200

    _login(client, "manager")
    checkout_qr = client.post("/api/v1/attendance/qr/rotate")
    assert checkout_qr.status_code == 200

    _login(client, "employee")
    check_out = client.post(
        "/api/v1/attendance/check-out",
        json={
            "device_id": "DEVICE-BOUND-2",
            "qr_token": checkout_qr.json()["token"],
        },
    )
    assert check_out.status_code == 400
    assert "mismatch" in check_out.json()["detail"].lower()
