from datetime import datetime, timedelta, timezone
import json

from sqlalchemy import select

from app.db.models import AuditLog, NfcBadge, RotatingQRToken, User


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


def test_attendance_rejects_replayed_qr_token(client):
    _login(client, "manager")
    qr = client.post("/api/v1/attendance/qr/rotate")
    assert qr.status_code == 200
    token = qr.json()["token"]

    _login(client, "employee")
    first = client.post(
        "/api/v1/attendance/check-in",
        json={
            "device_id": "DEVICE-EMP-REPLAY-1",
            "qr_token": token,
        },
    )
    assert first.status_code == 200

    second = client.post(
        "/api/v1/attendance/check-out",
        json={
            "device_id": "DEVICE-EMP-REPLAY-1",
            "qr_token": token,
        },
    )
    assert second.status_code == 400
    assert "already used" in second.json()["detail"].lower()


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


def test_attendance_cross_day_shift_uses_prior_business_date(client):
    _login(client, "manager")
    rules_update = client.patch(
        "/api/v1/attendance/rules",
        json={
            "tolerance_minutes": 5,
            "auto_break_after_hours": 6,
            "auto_break_minutes": 30,
            "cross_day_shift_cutoff_hour": 6,
            "late_early_penalty_hours": "0.25",
        },
    )
    assert rules_update.status_code == 200

    qr_for_employee = client.post("/api/v1/attendance/qr/rotate")
    assert qr_for_employee.status_code == 200
    token1 = qr_for_employee.json()["token"]

    check_in_at = datetime(2026, 3, 27, 22, 0, tzinfo=timezone.utc)
    scheduled_start_at = datetime(2026, 3, 27, 22, 0, tzinfo=timezone.utc)
    scheduled_end_at = datetime(2026, 3, 28, 4, 0, tzinfo=timezone.utc)
    check_out_at = datetime(2026, 3, 28, 2, 0, tzinfo=timezone.utc)

    _login(client, "employee")
    check_in = client.post(
        "/api/v1/attendance/check-in",
        json={
            "device_id": "DEVICE-XDAY-1",
            "qr_token": token1,
            "check_in_at": check_in_at.isoformat(),
            "scheduled_start_at": scheduled_start_at.isoformat(),
            "scheduled_end_at": scheduled_end_at.isoformat(),
        },
    )
    assert check_in.status_code == 200

    _login(client, "manager")
    qr_for_checkout = client.post("/api/v1/attendance/qr/rotate")
    assert qr_for_checkout.status_code == 200
    token2 = qr_for_checkout.json()["token"]

    _login(client, "employee")
    check_out = client.post(
        "/api/v1/attendance/check-out",
        json={
            "device_id": "DEVICE-XDAY-1",
            "qr_token": token2,
            "check_out_at": check_out_at.isoformat(),
        },
    )
    assert check_out.status_code == 200
    assert check_out.json()["daily_result"]["business_date"] == "2026-03-27"


def test_attendance_nfc_checkin_checkout_creates_badge(client, db_session):
    _login(client, "employee")

    now = datetime.now(timezone.utc)
    check_in = client.post(
        "/api/v1/attendance/check-in",
        json={
            "device_id": "DEVICE-NFC-1",
            "nfc_tag": "NFC-EMP-1",
            "check_in_at": (now - timedelta(hours=4)).isoformat(),
        },
    )
    assert check_in.status_code == 200

    check_out = client.post(
        "/api/v1/attendance/check-out",
        json={
            "device_id": "DEVICE-NFC-1",
            "nfc_tag": "NFC-EMP-1",
            "check_out_at": now.isoformat(),
        },
    )
    assert check_out.status_code == 200
    assert check_out.json()["shift"]["status"] == "closed"

    user = db_session.execute(select(User).where(User.username == "employee")).scalar_one()
    badge = db_session.execute(select(NfcBadge).where(NfcBadge.user_id == user.id)).scalar_one()
    assert badge.tag_id == "NFC-EMP-1"


def test_attendance_audit_masks_qr_and_device_identifiers(client, db_session):
    _login(client, "manager")
    qr = client.post("/api/v1/attendance/qr/rotate")
    assert qr.status_code == 200
    token = qr.json()["token"]

    _login(client, "employee")
    check_in = client.post(
        "/api/v1/attendance/check-in",
        json={
            "device_id": "DEVICE-AUDIT-1",
            "qr_token": token,
        },
    )
    assert check_in.status_code == 200

    audit_row = db_session.execute(
        select(AuditLog)
        .where(AuditLog.action == "attendance.checkin")
        .order_by(AuditLog.id.desc())
    ).scalar_one()

    detail = json.loads(audit_row.detail_json)
    assert detail["qr_token"] != token
    assert "***" in detail["qr_token"]
    assert detail["device_id"] != "DEVICE-AUDIT-1"
    assert "***" in detail["device_id"]
