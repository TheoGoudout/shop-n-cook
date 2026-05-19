"""convert ingredients to plain strings

Revision ID: i1j2k3l4m5n6
Revises: h7i8j9k0l1m2
Create Date: 2026-05-19 10:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

revision = "i1j2k3l4m5n6"
down_revision = "h7i8j9k0l1m2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- shoppinglistitem: replace ingredient_id FK with plain name string ---
    op.add_column(
        "shoppinglistitem", sa.Column("name", sa.String(255), nullable=True)
    )
    op.execute(
        """
        UPDATE shoppinglistitem sli
        SET name = i.name
        FROM ingredient i
        WHERE sli.ingredient_id = i.id
        """
    )
    op.alter_column("shoppinglistitem", "name", nullable=False)
    op.drop_constraint(
        "shoppinglistitem_ingredient_id_fkey", "shoppinglistitem", type_="foreignkey"
    )
    op.drop_column("shoppinglistitem", "ingredient_id")

    # --- recipeingredient: replace ingredient_id FK with plain ingredient_name string ---
    op.add_column(
        "recipeingredient",
        sa.Column("ingredient_name", sa.String(255), nullable=True),
    )
    op.execute(
        """
        UPDATE recipeingredient ri
        SET ingredient_name = i.name
        FROM ingredient i
        WHERE ri.ingredient_id = i.id
        """
    )
    op.alter_column("recipeingredient", "ingredient_name", nullable=False)
    op.drop_constraint(
        "recipeingredient_ingredient_id_fkey", "recipeingredient", type_="foreignkey"
    )
    op.drop_column("recipeingredient", "ingredient_id")

    # --- drop ingredient table (no longer referenced) ---
    op.drop_table("ingredient")


def downgrade() -> None:
    raise NotImplementedError("Downgrade not supported for this migration")
