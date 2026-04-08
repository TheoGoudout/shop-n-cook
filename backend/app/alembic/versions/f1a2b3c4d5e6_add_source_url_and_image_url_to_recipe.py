"""add_source_url_and_image_url_to_recipe

Revision ID: f1a2b3c4d5e6
Revises: d5e6f7a8b9c0
Create Date: 2026-04-08 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f1a2b3c4d5e6'
down_revision = 'd5e6f7a8b9c0'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('recipe', sa.Column('source_url', sa.Text(), nullable=True))
    op.add_column('recipe', sa.Column('image_url', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('recipe', 'image_url')
    op.drop_column('recipe', 'source_url')
