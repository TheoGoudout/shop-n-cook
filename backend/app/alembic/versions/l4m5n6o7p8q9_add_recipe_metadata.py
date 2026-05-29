"""add recipe metadata fields

Revision ID: l4m5n6o7p8q9
Revises: k3l4m5n6o7p8
Create Date: 2026-05-29 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY

revision = "l4m5n6o7p8q9"
down_revision = "k3l4m5n6o7p8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "recipe",
        sa.Column(
            "seasons",
            ARRAY(sa.String()),
            nullable=True,
            server_default="{}",
        ),
    )
    op.add_column(
        "recipe",
        sa.Column(
            "is_vegan",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "recipe",
        sa.Column(
            "is_vegetarian",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "recipe",
        sa.Column(
            "is_gluten_free",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "recipe",
        sa.Column(
            "is_dairy_free",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "recipe",
        sa.Column("kcal_per_serving", sa.Integer(), nullable=True),
    )
    op.add_column(
        "recipe",
        sa.Column("difficulty", sa.String(length=10), nullable=True),
    )
    op.add_column(
        "recipe",
        sa.Column("meal_type", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "recipe",
        sa.Column("cuisine_type", sa.String(length=100), nullable=True),
    )


def downgrade() -> None:
    for col in [
        "cuisine_type",
        "meal_type",
        "difficulty",
        "kcal_per_serving",
        "is_dairy_free",
        "is_gluten_free",
        "is_vegetarian",
        "is_vegan",
        "seasons",
    ]:
        op.drop_column("recipe", col)
