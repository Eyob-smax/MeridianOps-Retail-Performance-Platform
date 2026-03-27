from datetime import date, datetime, timedelta, timezone
from threading import Event, Thread

from app.db.session import session_scope
from app.services.kpi_service import run_kpi_materialization


class NightlyScheduler:
    def __init__(self, run_hour_utc: int = 2) -> None:
        self._stop_event = Event()
        self._thread: Thread | None = None
        self.enabled = False
        self.next_run_at: datetime | None = None
        self.run_hour_utc = max(0, min(23, run_hour_utc))

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self.enabled = True
        self._stop_event.clear()
        self._thread = Thread(target=self._loop, name="nightly-kpi-scheduler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self.enabled = False
        self._stop_event.set()

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            now = datetime.now(timezone.utc)
            self.next_run_at = self._next_run_utc(now)
            seconds_until_next = (self.next_run_at - now).total_seconds()
            wait_seconds = min(max(seconds_until_next, 5.0), 60.0)
            if self._stop_event.wait(wait_seconds):
                break

            if datetime.now(timezone.utc) < self.next_run_at:
                continue

            target_date = (self.next_run_at - timedelta(days=1)).date()
            try:
                with session_scope() as db:
                    run_kpi_materialization(
                        db,
                        start_date=target_date,
                        end_date=target_date,
                        trigger_type="scheduled",
                        actor_user_id=None,
                        store_ids=[0, 101, 102, 103],
                        scheduled_for=self.next_run_at,
                    )
            except Exception:
                # Errors are persisted by run_kpi_materialization failure path.
                pass

    def _next_run_utc(self, now: datetime) -> datetime:
        candidate = datetime.combine(now.date(), datetime.min.time(), tzinfo=timezone.utc).replace(
            hour=self.run_hour_utc
        )
        if now >= candidate:
            candidate = candidate + timedelta(days=1)
        return candidate


def run_backfill_range(
    start_date: date,
    end_date: date,
    actor_user_id: int | None,
    store_ids: list[int] | None = None,
):
    with session_scope() as db:
        return run_kpi_materialization(
            db,
            start_date=start_date,
            end_date=end_date,
            trigger_type="manual",
            actor_user_id=actor_user_id,
            store_ids=store_ids,
        )


def run_manual_once(target_date: date, actor_user_id: int | None = None):
    return run_backfill_range(target_date, target_date, actor_user_id=actor_user_id, store_ids=[0, 101, 102, 103])
