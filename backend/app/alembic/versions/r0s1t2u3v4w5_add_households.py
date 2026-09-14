"""add households

A household groups users so they share shopping lists and meal plans. Members
are a separate table rather than a column on ``user`` because a membership
carries its own role and join date, and because the unique constraint is what
stops a user being added to one household twice.

Invites are stored rather than signed into a token so that an owner can see and
revoke a pending invitation, and so that a pending invite can hold a seat
against the member cap.

Revision ID: r0s1t2u3v4w5
Revises: q9r0s1t2u3v4
Create Date: 2026-09-14 02:20:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "r0s1t2u3v4w5"
down_revision = "q9r0s1t2u3v4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "household",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_household_owner_id"), "household", ["owner_id"])

    op.create_table(
        "householdmember",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        # Enum-backed, stored as a string like every other enum column here.
        # SQLAlchemy round-trips the member *name*, so the default is "MEMBER".
        sa.Column(
            "role", sa.String(length=20), nullable=False, server_default="MEMBER"
        ),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["household_id"], ["household.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("household_id", "user_id", name="uq_household_member"),
    )
    op.create_index(
        op.f("ix_householdmember_household_id"), "householdmember", ["household_id"]
    )
    op.create_index(op.f("ix_householdmember_user_id"), "householdmember", ["user_id"])

    op.create_table(
        "householdinvite",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["household_id"], ["household.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_householdinvite_household_id"), "householdinvite", ["household_id"]
    )
    op.create_index(op.f("ix_householdinvite_email"), "householdinvite", ["email"])


def downgrade() -> None:
    op.drop_index(op.f("ix_householdinvite_email"), table_name="householdinvite")
    op.drop_index(
        op.f("ix_householdinvite_household_id"), table_name="householdinvite"
    )
    op.drop_table("householdinvite")
    op.drop_index(op.f("ix_householdmember_user_id"), table_name="householdmember")
    op.drop_index(
        op.f("ix_householdmember_household_id"), table_name="householdmember"
    )
    op.drop_table("householdmember")
    op.drop_index(op.f("ix_household_owner_id"), table_name="household")
    op.drop_table("household")
