"""add import_source to recipe

Revision ID: m5n6o7p8q9r0
Revises: l4m5n6o7p8q9
Create Date: 2026-08-31 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

revision = "m5n6o7p8q9r0"
down_revision = "l4m5n6o7p8q9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "recipe",
        sa.Column("import_source", sa.String(length=10), nullable=True),
    )
    # Recipes that already carry a source_url were imported from the web.
    op.execute(
        "UPDATE recipe SET import_source = 'url' "
        "WHERE source_url IS NOT NULL AND source_url <> ''"
    )


def downgrade() -> None:
    op.drop_column("recipe", "import_source")
