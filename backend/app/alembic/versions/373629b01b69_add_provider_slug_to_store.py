"""add provider_slug to store

Revision ID: 373629b01b69
Revises: r0s1t2u3v4w5
Create Date: 2026-09-25 18:17:50.550184

Hand-trimmed. Autogenerate also proposed converting a dozen VARCHAR columns to
native enum types and dropping the unique constraint on ``ingredient.name`` —
pre-existing drift between the models and what earlier migrations created, not
part of this change. Applying it here would have been destructive and
unreviewable, so this migration carries only the new column.
"""

import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op

# revision identifiers, used by Alembic.
revision = "373629b01b69"
down_revision = "r0s1t2u3v4w5"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "store",
        sa.Column(
            "provider_slug",
            sqlmodel.sql.sqltypes.AutoString(length=64),
            nullable=True,
        ),
    )
    op.create_index(
        op.f("ix_store_provider_slug"), "store", ["provider_slug"], unique=False
    )


def downgrade():
    op.drop_index(op.f("ix_store_provider_slug"), table_name="store")
    op.drop_column("store", "provider_slug")
