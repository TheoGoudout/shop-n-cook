"""Guard the database representation of enum-backed columns.

SQLModel maps a Python enum field to SQLAlchemy's ``Enum`` type, which
persists the member *name* (``URL``), not its value (``url``). Migrations that
backfill such a column, or give it a server default, must write the same
literal — otherwise every read of the row raises
``LookupError: 'url' is not among the defined enum values``.
"""

import ast
import re
from pathlib import Path
from typing import Any

import pytest
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlmodel import SQLModel

import app.models  # noqa: F401  (registers every table on SQLModel.metadata)

VERSIONS_DIR = Path(__file__).parents[2] / "app" / "alembic" / "versions"
DIALECT = postgresql.dialect()

ENUM_COLUMNS: dict[tuple[str, str], sa.Enum] = {
    (table.name, column.name): column.type
    for table in SQLModel.metadata.sorted_tables
    for column in table.columns
    if isinstance(column.type, sa.Enum)
}


def _to_db(enum_type: sa.Enum, value: Any) -> Any:
    return enum_type.bind_processor(DIALECT)(value)


def _from_db(enum_type: sa.Enum, value: Any) -> Any:
    return enum_type.result_processor(DIALECT, None)(value)


@pytest.mark.parametrize("table_column", sorted(ENUM_COLUMNS))
def test_enum_columns_round_trip_member_names(table_column: tuple[str, str]) -> None:
    enum_type = ENUM_COLUMNS[table_column]
    assert enum_type.enum_class is not None
    for member in enum_type.enum_class:
        assert _to_db(enum_type, member) == member.name
        assert _from_db(enum_type, member.name) is member


def _sql_literals(tree: ast.Module, column: str) -> list[str]:
    """Literals assigned to ``column`` in raw SQL inside a migration.

    Only ``SET`` clauses are inspected — a ``WHERE`` may legitimately match on
    a legacy literal the enum can no longer read.
    """
    pattern = re.compile(rf"(?:SET|,)\s+{column}\s*=\s*'([^']*)'", re.IGNORECASE)
    return [
        match
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
        for match in pattern.findall(node.value)
    ]


def _server_defaults(tree: ast.Module, column: str) -> list[str]:
    """``server_default`` values declared for ``column`` in a migration."""
    defaults: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        first = node.args[0]
        if not (isinstance(first, ast.Constant) and first.value == column):
            continue
        for keyword in node.keywords:
            if keyword.arg == "server_default" and isinstance(
                keyword.value, ast.Constant
            ):
                if isinstance(keyword.value.value, str):
                    defaults.append(keyword.value.value)
    return defaults


@pytest.mark.parametrize(
    "path", sorted(VERSIONS_DIR.glob("*.py")), ids=lambda p: p.name
)
def test_migrations_write_valid_enum_literals(path: Path) -> None:
    tree = ast.parse(path.read_text())
    for (_, column), enum_type in ENUM_COLUMNS.items():
        for literal in _sql_literals(tree, column) + _server_defaults(tree, column):
            assert _from_db(enum_type, literal) is not None, (
                f"{path.name} writes {literal!r} to {column}, which the "
                f"{enum_type.name} enum cannot read back"
            )
