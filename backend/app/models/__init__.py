# Import order matters: user first (no deps). This ensures SQLModel
# registers all table models before Alembic or the engine resolves relationships.
from sqlmodel import SQLModel  # noqa: F401 — re-exported for alembic env.py

from app.models.base import Message, get_datetime_utc
from app.models.user import (
    NewPassword,
    Token,
    TokenPayload,
    UpdatePassword,
    User,
    UserBase,
    UserCreate,
    UserPublic,
    UserRegister,
    UsersPublic,
    UserUpdate,
    UserUpdateMe,
)

__all__ = [
    # base
    "SQLModel",
    "Message",
    "get_datetime_utc",
    # user / auth
    "Token",
    "TokenPayload",
    "NewPassword",
    "UserBase",
    "UserCreate",
    "UserRegister",
    "UserUpdate",
    "UserUpdateMe",
    "UpdatePassword",
    "User",
    "UserPublic",
    "UsersPublic",
]
