"""add recipe crawler

``crawledrecipe`` is the crawler's memory: one row per recipe page it has
judged, unique on the page's canonical URL, which is what stops a recipe from
being imported twice. Its ``QUALIFIED`` rows are the import backlog. ``recipecrawlrun`` logs each pass; the latest one decides
when the next is due.

``status`` holds the ``CrawlStatus`` member *name* (``IMPORTED``), as every
enum column here does.

Revision ID: t2u3v4w5x6y7
Revises: s1t2u3v4w5x6
Create Date: 2026-10-03 11:00:00.000000

"""

import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op

# revision identifiers, used by Alembic.
revision = "t2u3v4w5x6y7"
down_revision = "s1t2u3v4w5x6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recipecrawlrun",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pages_fetched", sa.Integer(), nullable=False),
        sa.Column("qualified_count", sa.Integer(), nullable=False),
        sa.Column("imported_count", sa.Integer(), nullable=False),
        sa.Column("rejected_count", sa.Integer(), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "crawledrecipe",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("site", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column("url", sqlmodel.sql.sqltypes.AutoString(length=2048), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "reason", sqlmodel.sql.sqltypes.AutoString(length=500), nullable=True
        ),
        sa.Column("title", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
        sa.Column("rating_value", sa.Float(), nullable=True),
        sa.Column("rating_count", sa.Integer(), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("recipe_id", sa.Uuid(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipe.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_crawledrecipe_site"), "crawledrecipe", ["site"], unique=False
    )
    op.create_index(op.f("ix_crawledrecipe_url"), "crawledrecipe", ["url"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_crawledrecipe_url"), table_name="crawledrecipe")
    op.drop_index(op.f("ix_crawledrecipe_site"), table_name="crawledrecipe")
    op.drop_table("crawledrecipe")
    op.drop_table("recipecrawlrun")
