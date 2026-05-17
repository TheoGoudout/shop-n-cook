"""add_is_public_to_recipe

Revision ID: g6h7i8j9k0l1
Revises: f1a2b3c4d5e6
Create Date: 2026-05-17 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'g6h7i8j9k0l1'
down_revision = 'f1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('recipe', sa.Column('is_public', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    op.drop_column('recipe', 'is_public')
