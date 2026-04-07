"""add_recipe_and_shopping_list_models

Revision ID: a9b326d13042
Revises: a8f3e1b2c4d5
Create Date: 2026-04-03 16:04:45.504561

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = 'a9b326d13042'
down_revision = 'a8f3e1b2c4d5'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('recipe',
    sa.Column('title', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
    sa.Column('description', sqlmodel.sql.sqltypes.AutoString(length=1000), nullable=True),
    sa.Column('instructions', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('servings', sa.Integer(), nullable=True),
    sa.Column('prep_time_minutes', sa.Integer(), nullable=True),
    sa.Column('cook_time_minutes', sa.Integer(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('owner_id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['owner_id'], ['user.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('shoppinglist',
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('owner_id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['owner_id'], ['user.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('recipeingredient',
    sa.Column('quantity', sa.Float(), nullable=False),
    sa.Column('unit', sqlmodel.sql.sqltypes.AutoString(length=50), nullable=False),
    sa.Column('notes', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('recipe_id', sa.Uuid(), nullable=False),
    sa.Column('ingredient_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['ingredient_id'], ['ingredient.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['recipe_id'], ['recipe.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('shoppinglistitem',
    sa.Column('quantity', sa.Float(), nullable=False),
    sa.Column('unit', sqlmodel.sql.sqltypes.AutoString(length=50), nullable=False),
    sa.Column('is_checked', sa.Boolean(), nullable=False),
    sa.Column('notes', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('shopping_list_id', sa.Uuid(), nullable=False),
    sa.Column('ingredient_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['ingredient_id'], ['ingredient.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['shopping_list_id'], ['shoppinglist.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('shoppinglistitem')
    op.drop_table('recipeingredient')
    op.drop_table('shoppinglist')
    op.drop_table('recipe')
