"""add batch cooking and saved generation settings

``mealplanentry.batch_of_id`` marks a meal as leftovers of another entry in the
same plan, cooked earlier in the week. Deleting the cooked entry sets it back
to ``NULL`` so the leftovers become ordinary meals rather than vanishing.

``mealplan.generation_settings`` keeps the form a menu was generated with, so
swapping one of its meals later still honours the same diet and limits.

Revision ID: t2u3v4w5x6y7
Revises: s1t2u3v4w5x6
Create Date: 2026-10-03 11:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "t2u3v4w5x6y7"
down_revision = "s1t2u3v4w5x6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("mealplanentry", sa.Column("batch_of_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "mealplanentry_batch_of_id_fkey",
        "mealplanentry",
        "mealplanentry",
        ["batch_of_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "mealplan", sa.Column("generation_settings", sa.JSON(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("mealplan", "generation_settings")
    op.drop_constraint(
        "mealplanentry_batch_of_id_fkey", "mealplanentry", type_="foreignkey"
    )
    op.drop_column("mealplanentry", "batch_of_id")
