"""add name_en to ingredient

Revision ID: k3l4m5n6o7p8
Revises: j2k3l4m5n6o7
Create Date: 2026-05-20 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "k3l4m5n6o7p8"
down_revision = "j2k3l4m5n6o7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ingredient",
        sa.Column("name_en", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ingredient", "name_en")
