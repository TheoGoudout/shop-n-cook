"""add_recipe_steps

Revision ID: b2c3d4e5f6a7
Revises: f1a2b3c4d5e6
Create Date: 2026-05-14 10:00:00.000000

"""
import uuid

import sqlalchemy as sa
from alembic import op


revision = 'b2c3d4e5f6a7'
down_revision = 'f1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'recipestep',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('recipe_id', sa.Uuid(), nullable=False),
        sa.Column('step_number', sa.Integer(), nullable=False),
        sa.Column('instruction', sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(['recipe_id'], ['recipe.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'recipestepingredient',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('step_id', sa.Uuid(), nullable=False),
        sa.Column('recipe_ingredient_id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['step_id'], ['recipestep.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['recipe_ingredient_id'], ['recipeingredient.id'], ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id'),
    )

    # Migrate existing instructions to step 1
    connection = op.get_bind()
    recipes = connection.execute(
        sa.text("SELECT id, instructions FROM recipe WHERE instructions IS NOT NULL AND instructions != ''")
    ).fetchall()
    for recipe_id, instructions in recipes:
        connection.execute(
            sa.text(
                "INSERT INTO recipestep (id, recipe_id, step_number, instruction) "
                "VALUES (:id, :recipe_id, 1, :instruction)"
            ),
            {"id": str(uuid.uuid4()), "recipe_id": str(recipe_id), "instruction": instructions},
        )

    op.drop_column('recipe', 'instructions')


def downgrade():
    op.add_column('recipe', sa.Column('instructions', sa.Text(), nullable=True))

    # Restore instructions from step 1 (best-effort)
    connection = op.get_bind()
    steps = connection.execute(
        sa.text("SELECT recipe_id, instruction FROM recipestep WHERE step_number = 1")
    ).fetchall()
    for recipe_id, instruction in steps:
        connection.execute(
            sa.text("UPDATE recipe SET instructions = :instruction WHERE id = :id"),
            {"instruction": instruction, "id": str(recipe_id)},
        )

    op.drop_table('recipestepingredient')
    op.drop_table('recipestep')
