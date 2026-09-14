"""add meal plans

A meal plan is a named date range holding entries, each pinning one recipe to a
(date, meal_type) slot at a chosen number of servings. The unique constraint
includes the recipe, so two different dishes on the same evening are allowed
while the same dish cannot be added to one slot twice.

``shopping_list_id`` links a plan to the list generated from it. It is
``SET NULL`` on delete: deleting the list should not delete the plan that
produced it.

Revision ID: q9r0s1t2u3v4
Revises: p8q9r0s1t2u3
Create Date: 2026-09-13 16:40:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "q9r0s1t2u3v4"
down_revision = "p8q9r0s1t2u3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mealplan",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("shopping_list_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["shopping_list_id"], ["shoppinglist.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_mealplan_owner_id"), "mealplan", ["owner_id"])

    op.create_table(
        "mealplanentry",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("meal_plan_id", sa.Uuid(), nullable=False),
        sa.Column("recipe_id", sa.Uuid(), nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=False),
        # Enum-backed, stored as a string like every other enum column here.
        # SQLAlchemy round-trips the member *name*, so the default is "DINNER".
        sa.Column(
            "meal_type", sa.String(length=20), nullable=False, server_default="DINNER"
        ),
        sa.Column("servings", sa.Integer(), nullable=False, server_default="2"),
        sa.ForeignKeyConstraint(["meal_plan_id"], ["mealplan.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipe.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "meal_plan_id",
            "entry_date",
            "meal_type",
            "recipe_id",
            name="uq_meal_plan_slot_recipe",
        ),
    )
    op.create_index(
        op.f("ix_mealplanentry_meal_plan_id"), "mealplanentry", ["meal_plan_id"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_mealplanentry_meal_plan_id"), table_name="mealplanentry")
    op.drop_table("mealplanentry")
    op.drop_index(op.f("ix_mealplan_owner_id"), table_name="mealplan")
    op.drop_table("mealplan")
