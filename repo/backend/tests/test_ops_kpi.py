import json
import sys
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from io import BytesIO

from PIL import Image
from pypdf import PdfReader
from sqlalchemy import select

from app.cli import backfill_kpi
from app.db.models import AuditLog, InventoryItem, InventoryLedger, InventoryLocation, KPIDailyMetric, KPIJobRun
from app.services.auth_service import create_user
from app.services import kpi_service
from app.services.scheduler_service import NightlyScheduler


def _login(client, username: str, password: str = "ChangeMeNow123"):
    client.post("/api/v1/auth/logout")
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return response


def _create_dashboard(client) -> int:
    today = date.today()
    payload = {
        "name": "Ops Dashboard",
        "description": "Ops KPI dashboard",
        "widgets": [
            {
                "id": "ops-kpi",
                "kind": "kpi",
                "title": "Revenue",
                "metric": "revenue",
                "dimension": None,
                "x": 0,
                "y": 0,
                "w": 4,
                "h": 2,
            }
        ],
        "allowed_store_ids": [101, 102],
        "default_start_date": (today - timedelta(days=7)).isoformat(),
        "default_end_date": today.isoformat(),
    }
    created = client.post("/api/v1/analytics/dashboards", json=payload)
    assert created.status_code == 200
    return int(created.json()["id"])


def test_scheduler_next_run_utc_boundary() -> None:
    scheduler = NightlyScheduler(run_hour_utc=2)
    early = datetime(2026, 3, 26, 1, 0, tzinfo=timezone.utc)
    late = datetime(2026, 3, 26, 2, 0, tzinfo=timezone.utc)

    assert scheduler._next_run_utc(early) == datetime(2026, 3, 26, 2, 0, tzinfo=timezone.utc)
    assert scheduler._next_run_utc(late) == datetime(2026, 3, 27, 2, 0, tzinfo=timezone.utc)


def test_operations_permissions_and_scheduler_controls(client) -> None:
    today = date.today().isoformat()
    payload = {"start_date": today, "end_date": today, "store_ids": [101]}

    _login(client, "cashier")
    assert client.get("/api/v1/ops/scheduler/status").status_code == 403
    assert client.post("/api/v1/ops/kpi/backfill", json=payload).status_code == 403

    _login(client, "manager")
    assert client.get("/api/v1/ops/scheduler/status").status_code == 200
    assert client.post("/api/v1/ops/scheduler/start").status_code == 403
    assert client.post("/api/v1/ops/seed/demo").status_code == 403

    _login(client, "admin")
    start_response = client.post("/api/v1/ops/scheduler/start")
    stop_response = client.post("/api/v1/ops/scheduler/stop")
    seed_response = client.post("/api/v1/ops/seed/demo")

    assert start_response.status_code == 200
    assert start_response.json()["enabled"] is True
    assert stop_response.status_code == 200
    assert stop_response.json()["enabled"] is False
    assert seed_response.status_code == 200


def test_store_manager_cannot_access_other_store_kpi_data(client, db_session) -> None:
    metric_date = date.today()
    db_session.add(
        KPIDailyMetric(
            business_date=metric_date,
            store_id=102,
            conversion_rate=Decimal("0.1000"),
            average_order_value=Decimal("25.50"),
            inventory_turnover=Decimal("1.0000"),
            total_attempts=10,
            successful_orders=4,
            revenue_total=Decimal("123.45"),
            inventory_outbound_qty=Decimal("5.000"),
            average_inventory_qty=Decimal("10.000"),
            run_id=None,
        )
    )
    db_session.commit()

    _login(client, "manager")

    denied_metrics = client.get(
        "/api/v1/ops/kpi/metrics",
        params={"start_date": metric_date.isoformat(), "end_date": metric_date.isoformat(), "store_id": 102},
    )
    assert denied_metrics.status_code == 403

    denied_backfill = client.post(
        "/api/v1/ops/kpi/backfill",
        json={
            "start_date": metric_date.isoformat(),
            "end_date": metric_date.isoformat(),
            "store_ids": [102],
        },
    )
    assert denied_backfill.status_code == 403

    own_store_metrics = client.get(
        "/api/v1/ops/kpi/metrics",
        params={"start_date": metric_date.isoformat(), "end_date": metric_date.isoformat()},
    )
    assert own_store_metrics.status_code == 200


def test_store_manager_cannot_access_other_store_dashboard_audit(client, db_session) -> None:
    create_user(
        db=db_session,
        username="manager102",
        password="ChangeMeNow123",
        display_name="Store Manager 102",
        roles=["store_manager"],
        store_id=102,
    )
    db_session.commit()

    _login(client, "manager")
    dashboard_id = _create_dashboard(client)
    audit = client.get(f"/api/v1/analytics/dashboards/{dashboard_id}/audit")
    assert audit.status_code == 200

    _login(client, "manager102")
    forbidden_audit = client.get(f"/api/v1/analytics/dashboards/{dashboard_id}/audit")
    assert forbidden_audit.status_code == 403


def test_kpi_backfill_materializes_metrics_and_logs_runs(client, db_session) -> None:
    _login(client, "admin")
    seeded = client.post("/api/v1/ops/seed/demo")
    assert seeded.status_code == 200
    seeded_payload = seeded.json()
    assert seeded_payload["created_training_topics"] >= 0
    assert seeded_payload["created_training_questions"] >= 0

    _login(client, "manager")
    start_date = (date.today() - timedelta(days=7)).isoformat()
    end_date = date.today().isoformat()

    backfill = client.post(
        "/api/v1/ops/kpi/backfill",
        json={
            "start_date": start_date,
            "end_date": end_date,
            "store_ids": [101],
        },
    )
    assert backfill.status_code == 200
    backfill_payload = backfill.json()
    assert backfill_payload["status"] == "success"
    assert backfill_payload["records_written"] >= 1

    runs_response = client.get("/api/v1/ops/kpi/runs")
    assert runs_response.status_code == 200
    runs_payload = runs_response.json()
    assert runs_payload
    assert runs_payload[0]["id"] == backfill_payload["run_id"]
    assert runs_payload[0]["status"] == "success"

    metrics_response = client.get(
        "/api/v1/ops/kpi/metrics",
        params={"start_date": start_date, "end_date": end_date, "store_id": 101},
    )
    assert metrics_response.status_code == 200
    metrics_payload = metrics_response.json()
    assert metrics_payload
    first_metric = metrics_payload[0]
    assert Decimal(first_metric["conversion_rate"]) >= Decimal("0")
    assert Decimal(first_metric["average_order_value"]) >= Decimal("0")
    assert Decimal(first_metric["inventory_turnover"]) >= Decimal("0")

    persisted = db_session.execute(select(KPIDailyMetric)).scalars().all()
    assert persisted


def test_dashboard_data_uses_kpi_metrics(client, db_session) -> None:
    metric_date = date.today()
    db_session.add(
        KPIDailyMetric(
            business_date=metric_date,
            store_id=101,
            conversion_rate=Decimal("0.1000"),
            average_order_value=Decimal("25.50"),
            inventory_turnover=Decimal("1.0000"),
            total_attempts=10,
            successful_orders=4,
            revenue_total=Decimal("123.45"),
            inventory_outbound_qty=Decimal("5.000"),
            average_inventory_qty=Decimal("10.000"),
            run_id=None,
        )
    )
    db_session.commit()

    _login(client, "manager")
    dashboard_id = _create_dashboard(client)

    detail = client.get(
        f"/api/v1/analytics/dashboards/{dashboard_id}",
        params={
            "store_ids": "101",
            "start_date": metric_date.isoformat(),
            "end_date": metric_date.isoformat(),
        },
    )
    assert detail.status_code == 200

    payload = detail.json()
    rows = payload["data"]["rows"]
    assert rows
    row = rows[0]
    assert row["orders"] == 4
    assert Decimal(row["revenue"]) == Decimal("123.45")

    totals = payload["data"]["totals"]
    assert totals["orders"] == 4
    assert Decimal(totals["revenue"]) == Decimal("123.45")


def test_kpi_retry_and_failure_status_tracking(db_session, monkeypatch) -> None:
    attempts = {"count": 0}

    def flaky_writer(*_args, **_kwargs):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("transient-run-error")
        return 7

    monkeypatch.setattr(kpi_service, "_write_metrics_for_range", flaky_writer)
    run_success = kpi_service.run_kpi_materialization(
        db_session,
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 1),
        trigger_type="manual",
        actor_user_id=None,
        store_ids=[101],
    )
    db_session.commit()

    assert run_success.status == "success"
    assert run_success.attempts_made == 2
    assert run_success.records_written == 7

    def always_fail(*_args, **_kwargs):
        raise RuntimeError("hard-fail")

    monkeypatch.setattr(kpi_service, "_write_metrics_for_range", always_fail)
    run_failed = kpi_service.run_kpi_materialization(
        db_session,
        start_date=date(2026, 3, 2),
        end_date=date(2026, 3, 2),
        trigger_type="manual",
        actor_user_id=None,
        store_ids=[101],
    )
    db_session.commit()

    assert run_failed.status == "failed"
    assert run_failed.attempts_made == kpi_service.MAX_RETRIES
    assert "hard-fail" in (run_failed.error_message or "")

    persisted = db_session.execute(select(KPIJobRun).where(KPIJobRun.id == run_failed.id)).scalar_one()
    assert persisted.finished_at is not None


def test_kpi_inventory_turnover_scopes_by_store_id_not_location_id(db_session) -> None:
    metric_date = date.today()

    item = InventoryItem(sku="SKU-KPI-1", name="KPI Item", unit="ea")
    db_session.add(item)
    db_session.flush()

    db_session.add_all(
        [
            InventoryLocation(id=902, store_id=902, code="LOC-902", name="Legacy 902"),
            InventoryLocation(id=903, store_id=903, code="LOC-903", name="Legacy 903"),
        ]
    )
    db_session.flush()

    db_session.add_all(
        [
            # This row belongs to store 101 but intentionally uses location_id 902.
            InventoryLedger(
                store_id=101,
                item_id=item.id,
                location_id=902,
                entry_type="transfer_out",
                quantity_delta=Decimal("-10.000"),
                reservation_delta=Decimal("0.000"),
                order_reference="S101-TURNOVER-1",
                created_at=datetime.combine(metric_date, datetime.min.time(), tzinfo=timezone.utc),
            ),
            # This row belongs to store 902 and should not be counted for store 101.
            InventoryLedger(
                store_id=902,
                item_id=item.id,
                location_id=902,
                entry_type="transfer_out",
                quantity_delta=Decimal("-90.000"),
                reservation_delta=Decimal("0.000"),
                order_reference="S902-TURNOVER-1",
                created_at=datetime.combine(metric_date, datetime.min.time(), tzinfo=timezone.utc),
            ),
        ]
    )
    db_session.commit()

    outbound_qty, _avg_inventory_qty, _turnover = kpi_service._read_inventory_turnover(db_session, metric_date, 101)
    assert outbound_qty == Decimal("10.000")


def test_backfill_cli_command_invokes_range(monkeypatch, capsys) -> None:
    captured: dict[str, object] = {}

    class DummyRun:
        id = 99
        status = "success"
        records_written = 12
        processed_from_date = date(2026, 3, 1)
        processed_to_date = date(2026, 3, 2)
        attempts_made = 1
        max_attempts = 3
        error_message = None

    def fake_run_backfill_range(start_date, end_date, actor_user_id, store_ids):
        captured["start_date"] = start_date
        captured["end_date"] = end_date
        captured["actor_user_id"] = actor_user_id
        captured["store_ids"] = store_ids
        return DummyRun()

    monkeypatch.setattr(backfill_kpi, "run_backfill_range", fake_run_backfill_range)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "backfill",
            "--start-date",
            "2026-03-01",
            "--end-date",
            "2026-03-02",
            "--store-ids",
            "101, 103",
            "--actor-user-id",
            "7",
        ],
    )

    exit_code = backfill_kpi.main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "run_id=99" in output
    assert captured["start_date"] == date(2026, 3, 1)
    assert captured["end_date"] == date(2026, 3, 2)
    assert captured["store_ids"] == [101, 103]
    assert captured["actor_user_id"] == 7


def test_log_and_export_masking_defaults(client, db_session) -> None:
    preview = json.loads(kpi_service.log_masking_preview())
    assert "***" in preview["member_code"]
    assert "***" in preview["coupon_code"]
    assert "***" in preview["wallet_reference"]

    _login(client, "manager")
    dashboard_id = _create_dashboard(client)
    link_response = client.post(f"/api/v1/analytics/dashboards/{dashboard_id}/share-links", json={})
    assert link_response.status_code == 200
    token = link_response.json()["token"]

    export_response = client.get(f"/api/v1/analytics/shared/{token}/export", params={"format": "csv"})
    assert export_response.status_code == 200

    audit_row = db_session.execute(
        select(AuditLog)
        .where(
            AuditLog.action == "dashboard.exported",
            AuditLog.actor_user_id.is_(None),
            AuditLog.resource_id == str(dashboard_id),
        )
        .order_by(AuditLog.id.desc())
    ).scalar_one()

    audit_detail = json.loads(audit_row.detail_json)
    assert audit_detail["shared_token"] != token
    assert "***" in audit_detail["shared_token"]
    assert token not in audit_row.detail_json


def test_shared_dashboard_link_inactive_and_expired_paths(client) -> None:
    _login(client, "manager")
    dashboard_id = _create_dashboard(client)

    active_link = client.post(f"/api/v1/analytics/dashboards/{dashboard_id}/share-links", json={})
    assert active_link.status_code == 200
    active_payload = active_link.json()

    deactivate = client.delete(
        f"/api/v1/analytics/dashboards/{dashboard_id}/share-links/{active_payload['id']}"
    )
    assert deactivate.status_code == 204

    inactive_access = client.get(f"/api/v1/analytics/shared/{active_payload['token']}")
    assert inactive_access.status_code == 400
    assert "inactive" in inactive_access.json()["detail"].lower()

    expired_time = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    expired_link = client.post(
        f"/api/v1/analytics/dashboards/{dashboard_id}/share-links",
        json={"expires_at": expired_time},
    )
    assert expired_link.status_code == 200
    expired_token = expired_link.json()["token"]

    expired_access = client.get(f"/api/v1/analytics/shared/{expired_token}")
    assert expired_access.status_code == 400
    assert "expired" in expired_access.json()["detail"].lower()


def test_shared_dashboard_png_export_is_valid_image(client) -> None:
    _login(client, "manager")
    dashboard_id = _create_dashboard(client)

    link_response = client.post(f"/api/v1/analytics/dashboards/{dashboard_id}/share-links", json={})
    assert link_response.status_code == 200
    token = link_response.json()["token"]

    export_response = client.get(f"/api/v1/analytics/shared/{token}/export", params={"format": "png"})
    assert export_response.status_code == 200
    assert "image/png" in export_response.headers.get("content-type", "")

    image = Image.open(BytesIO(export_response.content))
    image.verify()
    assert image.format == "PNG"


def test_shared_dashboard_pdf_export_contains_dashboard_title(client) -> None:
    _login(client, "manager")
    dashboard_id = _create_dashboard(client)

    link_response = client.post(f"/api/v1/analytics/dashboards/{dashboard_id}/share-links", json={})
    assert link_response.status_code == 200
    token = link_response.json()["token"]

    export_response = client.get(f"/api/v1/analytics/shared/{token}/export", params={"format": "pdf"})
    assert export_response.status_code == 200
    assert "application/pdf" in export_response.headers.get("content-type", "")

    pdf = PdfReader(BytesIO(export_response.content))
    assert len(pdf.pages) >= 1
    text = "\n".join((page.extract_text() or "") for page in pdf.pages)
    assert "MeridianOps Dashboard Export" in text
    assert "Ops Dashboard" in text
