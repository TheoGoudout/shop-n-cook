"""add ingredient catalog

Revision ID: j2k3l4m5n6o7
Revises: i1j2k3l4m5n6
Create Date: 2026-05-19 11:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "j2k3l4m5n6o7"
down_revision = "i1j2k3l4m5n6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ingredient",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(), nullable=False, server_default="OTHER"),
        sa.Column("image_url", sa.String(length=2048), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(op.f("ix_ingredient_name"), "ingredient", ["name"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_ingredient_name"), table_name="ingredient")
    op.drop_table("ingredient")
