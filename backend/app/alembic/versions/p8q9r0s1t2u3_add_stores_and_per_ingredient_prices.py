"""add stores and per-ingredient prices

Adds the retailers a basket can be costed against, and a price per
(ingredient, store). A store also carries a ``price_index`` used only where it
has no curated price of its own, which is what keeps a sparse price matrix
useful instead of leaving most of a list unpriced.

``usersettings.preferred_store_id`` selects the store a user's costs are shown
in; it is ``SET NULL`` on delete so removing a retailer degrades those users to
the catalog baseline rather than cascading away their settings.

Revision ID: p8q9r0s1t2u3
Revises: o7p8q9r0s1t2
Create Date: 2026-09-13 16:05:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "p8q9r0s1t2u3"
down_revision = "o7p8q9r0s1t2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "store",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("country", sa.String(length=2), nullable=False, server_default="FR"),
        sa.Column(
            "currency", sa.String(length=3), nullable=False, server_default="EUR"
        ),
        sa.Column("price_index", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("logo_url", sa.String(length=2048), nullable=True),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_store_slug"), "store", ["slug"], unique=True)

    op.create_table(
        "ingredientprice",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ingredient_id", sa.Uuid(), nullable=False),
        sa.Column("store_id", sa.Uuid(), nullable=False),
        sa.Column("price_amount", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("price_quantity", sa.Float(), nullable=False),
        # Enum-backed, but stored as a string like every other enum column in
        # this schema. SQLAlchemy round-trips the member *name*, so nothing may
        # write a lowercase literal here.
        sa.Column("price_unit", sa.String(length=50), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["ingredient_id"], ["ingredient.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["store_id"], ["store.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "ingredient_id", "store_id", name="uq_ingredient_store_price"
        ),
    )
    op.create_index(
        op.f("ix_ingredientprice_ingredient_id"),
        "ingredientprice",
        ["ingredient_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ingredientprice_store_id"),
        "ingredientprice",
        ["store_id"],
        unique=False,
    )

    op.add_column(
        "usersettings", sa.Column("preferred_store_id", sa.Uuid(), nullable=True)
    )
    op.create_foreign_key(
        "fk_usersettings_preferred_store",
        "usersettings",
        "store",
        ["preferred_store_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_usersettings_preferred_store", "usersettings", type_="foreignkey"
    )
    op.drop_column("usersettings", "preferred_store_id")
    op.drop_index(op.f("ix_ingredientprice_store_id"), table_name="ingredientprice")
    op.drop_index(
        op.f("ix_ingredientprice_ingredient_id"), table_name="ingredientprice"
    )
    op.drop_table("ingredientprice")
    op.drop_index(op.f("ix_store_slug"), table_name="store")
    op.drop_table("store")
