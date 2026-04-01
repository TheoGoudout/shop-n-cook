import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import col, func, select

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    Message,
    Recipe,
    RecipeCreate,
    RecipeIngredient,
    RecipeIngredientCreate,
    RecipeIngredientPublic,
    RecipeIngredientUpdate,
    RecipePublic,
    RecipesPublic,
    RecipeUpdate,
)

router = APIRouter(prefix="/recipes", tags=["recipes"])


def _to_public(recipe: Recipe) -> RecipePublic:
    return RecipePublic(
        id=recipe.id,
        owner_id=recipe.owner_id,
        title=recipe.title,
        description=recipe.description,
        base_servings=recipe.base_servings,
        created_at=recipe.created_at,
        ingredients=[
            RecipeIngredientPublic(
                id=i.id,
                recipe_id=i.recipe_id,
                name=i.name,
                quantity=i.quantity,
                unit=i.unit,
            )
            for i in recipe.ingredients
        ],
    )


@router.get("/", response_model=RecipesPublic)
def read_recipes(
    session: SessionDep, current_user: CurrentUser, skip: int = 0, limit: int = 100
) -> Any:
    count_statement = (
        select(func.count()).select_from(Recipe).where(Recipe.owner_id == current_user.id)
    )
    count = session.exec(count_statement).one()
    statement = (
        select(Recipe)
        .where(Recipe.owner_id == current_user.id)
        .order_by(col(Recipe.created_at).desc())
        .offset(skip)
        .limit(limit)
    )
    recipes = session.exec(statement).all()
    return RecipesPublic(data=[_to_public(r) for r in recipes], count=count)


@router.get("/{id}", response_model=RecipePublic)
def read_recipe(session: SessionDep, current_user: CurrentUser, id: uuid.UUID) -> Any:
    recipe = session.get(Recipe, id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    if recipe.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return _to_public(recipe)


@router.post("/", response_model=RecipePublic)
def create_recipe(
    *, session: SessionDep, current_user: CurrentUser, recipe_in: RecipeCreate
) -> Any:
    recipe = Recipe(
        title=recipe_in.title,
        description=recipe_in.description,
        base_servings=recipe_in.base_servings,
        owner_id=current_user.id,
    )
    session.add(recipe)
    session.flush()

    for ing_in in recipe_in.ingredients:
        ingredient = RecipeIngredient(
            recipe_id=recipe.id,
            name=ing_in.name,
            quantity=ing_in.quantity,
            unit=ing_in.unit,
        )
        session.add(ingredient)

    session.commit()
    session.refresh(recipe)
    return _to_public(recipe)


@router.put("/{id}", response_model=RecipePublic)
def update_recipe(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    recipe_in: RecipeUpdate,
) -> Any:
    recipe = session.get(Recipe, id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    if recipe.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    if recipe_in.title is not None:
        recipe.title = recipe_in.title
    if recipe_in.description is not None:
        recipe.description = recipe_in.description
    if recipe_in.base_servings is not None:
        recipe.base_servings = recipe_in.base_servings

    if recipe_in.ingredients is not None:
        # Replace all ingredients
        for existing in list(recipe.ingredients):
            session.delete(existing)
        session.flush()
        session.expire(recipe)  # clear stale in-memory relationship cache
        for ing_in in recipe_in.ingredients:
            ingredient = RecipeIngredient(
                recipe_id=recipe.id,
                name=ing_in.name,
                quantity=ing_in.quantity,
                unit=ing_in.unit,
            )
            session.add(ingredient)

    session.commit()
    session.refresh(recipe)
    return _to_public(recipe)


@router.delete("/{id}")
def delete_recipe(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Message:
    recipe = session.get(Recipe, id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    if recipe.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    session.delete(recipe)
    session.commit()
    return Message(message="Recipe deleted successfully")


# ---------------------------------------------------------------------------
# Ingredient sub-routes
# ---------------------------------------------------------------------------

@router.post("/{id}/ingredients", response_model=RecipeIngredientPublic)
def add_ingredient(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    ingredient_in: RecipeIngredientCreate,
) -> Any:
    recipe = session.get(Recipe, id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    if recipe.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    ingredient = RecipeIngredient(
        recipe_id=recipe.id,
        name=ingredient_in.name,
        quantity=ingredient_in.quantity,
        unit=ingredient_in.unit,
    )
    session.add(ingredient)
    session.commit()
    session.refresh(ingredient)
    return RecipeIngredientPublic(
        id=ingredient.id,
        recipe_id=ingredient.recipe_id,
        name=ingredient.name,
        quantity=ingredient.quantity,
        unit=ingredient.unit,
    )


@router.put("/{id}/ingredients/{ingredient_id}", response_model=RecipeIngredientPublic)
def update_ingredient(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    ingredient_id: uuid.UUID,
    ingredient_in: RecipeIngredientUpdate,
) -> Any:
    recipe = session.get(Recipe, id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    if recipe.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    ingredient = session.get(RecipeIngredient, ingredient_id)
    if not ingredient or ingredient.recipe_id != id:
        raise HTTPException(status_code=404, detail="Ingredient not found")

    if ingredient_in.name is not None:
        ingredient.name = ingredient_in.name
    if ingredient_in.quantity is not None:
        ingredient.quantity = ingredient_in.quantity
    if ingredient_in.unit is not None:
        ingredient.unit = ingredient_in.unit

    session.add(ingredient)
    session.commit()
    session.refresh(ingredient)
    return RecipeIngredientPublic(
        id=ingredient.id,
        recipe_id=ingredient.recipe_id,
        name=ingredient.name,
        quantity=ingredient.quantity,
        unit=ingredient.unit,
    )


@router.delete("/{id}/ingredients/{ingredient_id}")
def delete_ingredient(
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    ingredient_id: uuid.UUID,
) -> Message:
    recipe = session.get(Recipe, id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    if recipe.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    ingredient = session.get(RecipeIngredient, ingredient_id)
    if not ingredient or ingredient.recipe_id != id:
        raise HTTPException(status_code=404, detail="Ingredient not found")

    session.delete(ingredient)
    session.commit()
    return Message(message="Ingredient deleted successfully")
