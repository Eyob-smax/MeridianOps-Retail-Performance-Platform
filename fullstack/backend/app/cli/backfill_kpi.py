from datetime import date
import logging

from app.services.scheduler_service import run_backfill_range


logger = logging.getLogger("meridianops.kpi")


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"Invalid date format: {value}. Expected YYYY-MM-DD") from exc


def _parse_store_ids(value: str | None) -> list[int] | None:
    if value is None or not value.strip():
        return None
    output: list[int] = []
    for part in value.split(","):
        chunk = part.strip()
        if not chunk:
            continue
        try:
            output.append(int(chunk))
        except ValueError as exc:
            raise ValueError(f"Invalid store id '{chunk}'. Expected integer values") from exc
    return output if output else None


def _build_parser():
    import argparse

    parser = argparse.ArgumentParser(
        prog="python -m app.cli.backfill_kpi",
        description="Manually materialize KPI metrics for a date range",
    )
    parser.add_argument("--start-date", required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", required=True, help="End date (YYYY-MM-DD)")
    parser.add_argument(
        "--store-ids",
        default=None,
        help="Optional comma-separated store ids. Defaults to configured multi-store scope.",
    )
    parser.add_argument(
        "--actor-user-id",
        type=int,
        default=None,
        help="Optional actor user id for audit traceability",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    try:
        start_date = _parse_date(args.start_date)
        end_date = _parse_date(args.end_date)
        store_ids = _parse_store_ids(args.store_ids)
    except ValueError as exc:
        parser.error(str(exc))

    if end_date < start_date:
        parser.error("end-date must be on or after start-date")

    run = run_backfill_range(
        start_date=start_date,
        end_date=end_date,
        actor_user_id=args.actor_user_id,
        store_ids=store_ids,
    )

    logger.info(
        "kpi_backfill_completed",
        extra={
            "run_id": run.id,
            "status": run.status,
            "records_written": run.records_written,
            "from": str(run.processed_from_date),
            "to": str(run.processed_to_date),
            "attempts": run.attempts_made,
            "max_attempts": run.max_attempts,
        },
    )

    print(
        f"run_id={run.id} status={run.status} records_written={run.records_written} "
        f"range={run.processed_from_date}..{run.processed_to_date} attempts={run.attempts_made}/{run.max_attempts}"
    )
    if run.error_message:
        logger.error("kpi_backfill_failed", extra={"run_id": run.id, "error": run.error_message})
        print(f"error={run.error_message}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
