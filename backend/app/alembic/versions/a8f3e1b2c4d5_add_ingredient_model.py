"""Add ingredient model

Revision ID: a8f3e1b2c4d5
Revises: 1a31ce608336
Create Date: 2026-04-02 00:00:00.000000

"""

import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op

# revision identifiers, used by Alembic.
revision = "a8f3e1b2c4d5"
down_revision = "fe56fa70289e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ingredient",
        sa.Column(
            "name",
            sqlmodel.sql.sqltypes.AutoString(length=255),
            nullable=False,
        ),
        sa.Column(
            "category",
            sqlmodel.sql.sqltypes.AutoString(length=50),
            nullable=False,
        ),
        sa.Column(
            "default_unit",
            sqlmodel.sql.sqltypes.AutoString(length=50),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ingredient_name"), "ingredient", ["name"], unique=True
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_ingredient_name"), table_name="ingredient")
    op.drop_table("ingredient")
