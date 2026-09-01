"""normalize enum column case

Enum-backed columns are mapped through SQLAlchemy's ``Enum`` type, which
persists the enum *name* (``URL``), not its value (``url``). A couple of
migrations wrote the value instead, and reading such a row blows up with
``LookupError: 'url' is not among the defined enum values``.

This repairs the rows that were written with the wrong case and realigns the
server defaults that would keep producing them.

Revision ID: n6o7p8q9r0s1
Revises: m5n6o7p8q9r0
Create Date: 2026-09-01 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

revision = "n6o7p8q9r0s1"
down_revision = "m5n6o7p8q9r0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # recipe.import_source: backfilled as 'url' by m5n6o7p8q9r0.
    op.execute("UPDATE recipe SET import_source = 'URL' WHERE import_source = 'url'")
    op.execute(
        "UPDATE recipe SET import_source = 'PHOTO' WHERE import_source = 'photo'"
    )

    # ingredient.category and usersettings.shopping_frequency carried a
    # lowercase server default. For both enums the name is the uppercased
    # value, so an uppercase pass is enough; rows already stored as names are
    # left untouched.
    op.execute("UPDATE ingredient SET category = upper(category)")
    op.execute("UPDATE usersettings SET shopping_frequency = upper(shopping_frequency)")
    op.alter_column(
        "ingredient",
        "category",
        existing_type=sa.String(),
        existing_nullable=False,
        server_default="OTHER",
    )
    op.alter_column(
        "usersettings",
        "shopping_frequency",
        existing_type=sa.String(length=50),
        existing_nullable=False,
        server_default="WEEKLY",
    )


def downgrade() -> None:
    """No-op.

    Lowercasing the values again would reintroduce the read error this
    migration exists to fix, and the server defaults it realigns are the ones
    the earlier migrations now create in the first place.
    """
