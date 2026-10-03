"""add pantry check

Lets a shopping list record what is already at home. The at-home quantity sits
beside the needed one rather than being subtracted from it, so adding,
rescaling or removing a recipe keeps moving the need by the right amount.
``pantry_checked_at`` is ``NULL`` until someone has done the check, which is
what lets the UI suggest it on a fresh list.

Revision ID: s1t2u3v4w5x6
Revises: c7d8e9f0a1b2
Create Date: 2026-10-03 10:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "s1t2u3v4w5x6"
down_revision = "c7d8e9f0a1b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "shoppinglistitem",
        sa.Column(
            "quantity_at_home", sa.Float(), nullable=False, server_default="0"
        ),
    )
    op.add_column(
        "shoppinglist",
        sa.Column("pantry_checked_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("shoppinglist", "pantry_checked_at")
    op.drop_column("shoppinglistitem", "quantity_at_home")
