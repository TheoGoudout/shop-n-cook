"""add ingredient pricing and user budget

Gives the ingredient catalog a reference price — stored the way a price is
quoted, as an amount per a quantity of a unit — plus the two bridges that let
that price answer a question asked in a different dimension: ``density_g_per_ml``
for volume and ``piece_weight_g`` for counted units.

``usersettings`` gains the budget the README has been advertising, and the
currency it is denominated in.

Revision ID: o7p8q9r0s1t2
Revises: n6o7p8q9r0s1
Create Date: 2026-09-13 15:21:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "o7p8q9r0s1t2"
down_revision = "n6o7p8q9r0s1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enum-backed columns are stored as plain strings here, matching every
    # other enum column in this schema. SQLAlchemy still round-trips the enum
    # *member name*, so nothing may write a lowercase literal into them.
    op.add_column(
        "ingredient",
        sa.Column("price_amount", sa.Numeric(precision=10, scale=4), nullable=True),
    )
    op.add_column("ingredient", sa.Column("price_quantity", sa.Float(), nullable=True))
    op.add_column(
        "ingredient", sa.Column("price_unit", sa.String(length=50), nullable=True)
    )
    op.add_column(
        "ingredient", sa.Column("density_g_per_ml", sa.Float(), nullable=True)
    )
    op.add_column("ingredient", sa.Column("piece_weight_g", sa.Float(), nullable=True))
    op.add_column(
        "ingredient", sa.Column("price_source", sa.String(length=20), nullable=True)
    )
    op.add_column(
        "ingredient",
        sa.Column("price_updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.add_column(
        "usersettings",
        sa.Column("budget_amount", sa.Numeric(precision=10, scale=2), nullable=True),
    )
    # Existing rows need a currency, so the column arrives with a default.
    op.add_column(
        "usersettings",
        sa.Column(
            "currency", sa.String(length=3), nullable=False, server_default="EUR"
        ),
    )


def downgrade() -> None:
    op.drop_column("usersettings", "currency")
    op.drop_column("usersettings", "budget_amount")
    op.drop_column("ingredient", "price_updated_at")
    op.drop_column("ingredient", "price_source")
    op.drop_column("ingredient", "piece_weight_g")
    op.drop_column("ingredient", "density_g_per_ml")
    op.drop_column("ingredient", "price_unit")
    op.drop_column("ingredient", "price_quantity")
    op.drop_column("ingredient", "price_amount")
