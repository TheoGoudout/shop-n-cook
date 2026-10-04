from datetime import datetime, timezone
from enum import Enum
from typing import Any

import sqlalchemy as sa
from sqlmodel import SQLModel


def get_datetime_utc() -> datetime:
    return datetime.now(timezone.utc)


def stored_enum(enum_cls: type[Enum], length: int | None = None) -> Any:
    """The column type for an enum field: its member *name* in a VARCHAR.

    Left to itself, SQLModel maps an enum field to a native Postgres ENUM type,
    but every migration created these columns as VARCHAR — adding a member to a
    native ENUM needs a migration of its own, a VARCHAR does not. Declaring the
    storage here keeps the models and the migrations describing the same
    schema, which `alembic check` in test-backend.yml asserts. Behaviour is
    unchanged: SQLAlchemy's Enum stores and validates member names either way.

    ``length`` is the VARCHAR length the column was created with; ``None`` is an
    unbounded VARCHAR.

    Typed ``Any`` because SQLModel's ``Field(sa_type=...)`` stub accepts only a
    type class, while the runtime takes an instance as well — the same reason
    each ``DateTime(timezone=True)`` here carries a ``type: ignore``.
    """
    return sa.Enum(
        enum_cls,
        native_enum=False,
        length=length,
        create_constraint=False,
        name=enum_cls.__name__.lower(),
    )


class Message(SQLModel):
    message: str
