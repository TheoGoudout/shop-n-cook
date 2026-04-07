"""add_shopping_list_recipe_date_range_and_user_settings

Revision ID: c3d4e5f6a7b8
Revises: a9b326d13042
Create Date: 2026-04-07 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = 'c3d4e5f6a7b8'
down_revision = 'a9b326d13042'
branch_labels = None
depends_on = None


def upgrade():
    # Add date range columns to shoppinglist
    op.add_column('shoppinglist', sa.Column('start_date', sa.Date(), nullable=True))
    op.add_column('shoppinglist', sa.Column('end_date', sa.Date(), nullable=True))

    # Create shoppinglistrecipe table
    op.create_table(
        'shoppinglistrecipe',
        sa.Column('servings_planned', sa.Integer(), nullable=False),
        sa.Column('is_prepared', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('shopping_list_id', sa.Uuid(), nullable=False),
        sa.Column('recipe_id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['shopping_list_id'], ['shoppinglist.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['recipe_id'], ['recipe.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # Create usersettings table
    op.create_table(
        'usersettings',
        sa.Column('household_size', sa.Integer(), nullable=False, server_default='2'),
        sa.Column(
            'shopping_frequency',
            sqlmodel.sql.sqltypes.AutoString(length=50),
            nullable=False,
            server_default='weekly',
        ),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id'),
    )


def downgrade():
    op.drop_table('usersettings')
    op.drop_table('shoppinglistrecipe')
    op.drop_column('shoppinglist', 'end_date')
    op.drop_column('shoppinglist', 'start_date')
