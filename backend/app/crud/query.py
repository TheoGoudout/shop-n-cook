"""Query helpers shared by the CRUD modules."""

import uuid
from collections.abc import Sequence
from typing import Any, TypeVar

from sqlalchemy import ColumnElement
from sqlalchemy.orm.interfaces import ORMOption
from sqlmodel import Session, SQLModel, col, func, select

ModelT = TypeVar("ModelT", bound=SQLModel)


def owner_filter(
    owner_column: Any, owner_ids: set[uuid.UUID] | None
) -> list[ColumnElement[bool]]:
    """Rows owned by any of ``owner_ids``; no restriction at all for ``None``."""
    return [] if owner_ids is None else [col(owner_column).in_(owner_ids)]


def paginate(
    session: Session,
    model: type[ModelT],
    *,
    where: Sequence[ColumnElement[bool]] = (),
    order_by: Any,
    skip: int,
    limit: int,
    options: Sequence[ORMOption] = (),
) -> tuple[list[ModelT], int]:
    """One page of ``model`` rows matching ``where``, and how many match in all."""
    count = session.exec(select(func.count()).select_from(model).where(*where)).one()
    rows = session.exec(
        select(model)
        .where(*where)
        .options(*options)
        .order_by(order_by)
        .offset(skip)
        .limit(limit)
    ).all()
    return list(rows), count
