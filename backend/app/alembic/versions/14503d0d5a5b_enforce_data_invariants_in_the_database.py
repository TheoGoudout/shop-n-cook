"""enforce data invariants in the database

Revision ID: 14503d0d5a5b
Revises: e663625767b7
Create Date: 2026-10-07 00:05:21.506681

Rules the API already validated now hold in the database itself, so no code
path — a background job, a script, a future bug — can store data the rest of
the app assumes impossible:

- a user belongs to at most one household (it was "enforced in CRUD", which a
  race between two accepted invites could slip past);
- quantities, servings and prices are positive, and a meal plan does not end
  before it starts.

Each constraint is preceded by a repair that is a no-op on valid data, so the
upgrade cannot fail on a row an older bug let through. Each repair follows the
rule the app already applies: an ingredient with no positive quantity is
dropped (``recipe_import.mapping``), a price that cannot be used is no price
(unpriced, never zero), and a member of two households keeps the one they own,
else the one they joined first.
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "14503d0d5a5b"
down_revision = "e663625767b7"
branch_labels = None
depends_on = None


#: ``(table, name, condition)`` for every CHECK constraint added here.
CHECKS = [
    ("mealplan", "ck_mealplan_dates", "end_date >= start_date"),
    ("mealplanentry", "ck_mealplanentry_servings", "servings >= 1"),
    ("shoppinglistrecipe", "ck_shoppinglistrecipe_servings", "servings_planned >= 1"),
    ("shoppinglistitem", "ck_shoppinglistitem_quantity", "quantity > 0"),
    (
        "shoppinglistitem",
        "ck_shoppinglistitem_quantity_at_home",
        "quantity_at_home >= 0",
    ),
    ("recipeingredient", "ck_recipeingredient_quantity", "quantity > 0"),
    ("ingredientprice", "ck_ingredientprice_amount", "price_amount >= 0"),
    ("ingredientprice", "ck_ingredientprice_quantity", "price_quantity > 0"),
    ("store", "ck_store_price_index", "price_index > 0"),
    ("usersettings", "ck_usersettings_household_size", "household_size >= 1"),
]

#: Statements that bring legacy rows within the constraints above.
REPAIRS = [
    # A member of several households keeps the one they own, else the first.
    # Role is stored by enum member name.
    """
    DELETE FROM householdmember
    WHERE id IN (
        SELECT id FROM (
            SELECT id, row_number() OVER (
                PARTITION BY user_id
                ORDER BY (role = 'OWNER') DESC, joined_at ASC NULLS LAST, id
            ) AS rank
            FROM householdmember
        ) AS ranked
        WHERE rank > 1
    )
    """,
    # Postgres evaluates every right-hand side on the old row: this swaps.
    """
    UPDATE mealplan SET start_date = end_date, end_date = start_date
    WHERE end_date < start_date
    """,
    "UPDATE mealplanentry SET servings = 1 WHERE servings < 1",
    "UPDATE shoppinglistrecipe SET servings_planned = 1 WHERE servings_planned < 1",
    "DELETE FROM shoppinglistitem WHERE quantity <= 0",
    "UPDATE shoppinglistitem SET quantity_at_home = 0 WHERE quantity_at_home < 0",
    "DELETE FROM recipeingredient WHERE quantity <= 0",
    "DELETE FROM ingredientprice WHERE price_amount < 0 OR price_quantity <= 0",
    "UPDATE store SET price_index = 1.0 WHERE price_index <= 0",
    "UPDATE usersettings SET household_size = 1 WHERE household_size < 1",
]


def upgrade():
    for statement in REPAIRS:
        op.execute(statement)

    op.drop_constraint("uq_household_member", "householdmember", type_="unique")
    op.drop_index("ix_householdmember_user_id", table_name="householdmember")
    op.create_index(
        "ix_householdmember_user_id", "householdmember", ["user_id"], unique=True
    )
    for table, name, condition in CHECKS:
        op.create_check_constraint(name, table, condition)


def downgrade():
    for table, name, _condition in reversed(CHECKS):
        op.drop_constraint(name, table, type_="check")

    op.drop_index("ix_householdmember_user_id", table_name="householdmember")
    op.create_index(
        "ix_householdmember_user_id", "householdmember", ["user_id"], unique=False
    )
    op.create_unique_constraint(
        "uq_household_member", "householdmember", ["household_id", "user_id"]
    )
