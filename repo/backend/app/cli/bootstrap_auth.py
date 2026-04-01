import logging

from app.db.session import session_scope
from app.services.auth_service import ensure_seed_users, resolve_bootstrap_password


logger = logging.getLogger("meridianops.auth")


def main() -> int:
    try:
        password = resolve_bootstrap_password()
    except ValueError as exc:
        print(f"bootstrap_error={exc}")
        return 1

    with session_scope() as db:
        ensure_seed_users(db, password=password)

    logger.info("auth_seed_bootstrap_completed")
    print("status=ok message=seed_users_bootstrapped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
