from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import User


def get_user_by_username(db: Session, username: str) -> User | None:
    normalized = username.strip().lower()
    return db.execute(select(User).where(User.username == normalized, User.is_active.is_(True))).scalar_one_or_none()
