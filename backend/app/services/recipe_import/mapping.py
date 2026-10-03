"""Turn a ``ParsedRecipe`` into the payloads the recipe CRUD layer accepts."""

from __future__ import annotations

from app.models import (
    RecipeCreate,
    RecipeIngredientCreate,
    RecipeStepCreate,
    RecipeUpdate,
)
from app.models.recipe import ImportSource
from app.services.recipe_import.models import ParsedIngredient, ParsedRecipe

#: ``RecipeBase.description``'s limit; a model's summary occasionally runs past it.
_DESCRIPTION_MAX_LENGTH = 1000


def _ingredients_and_steps(
    ingredients_in: list[ParsedIngredient], parsed: ParsedRecipe
) -> tuple[list[RecipeIngredientCreate], list[RecipeStepCreate]]:
    """Map ingredients, then link each step to them by (case-insensitive) name."""
    name_to_idx = {ing.name.lower(): i for i, ing in enumerate(ingredients_in)}
    ingredients = [
        RecipeIngredientCreate(
            ingredient_name=ing.name,
            name_en=ing.name_en,
            quantity=ing.quantity,
            unit=ing.unit,
            notes=ing.notes,
            category=ing.category,
        )
        for ing in ingredients_in
    ]
    steps = [
        RecipeStepCreate(
            step_number=i + 1,
            instruction=step.instruction,
            ingredient_indices=[
                name_to_idx[n.lower()]
                for n in step.ingredient_names
                if n.lower() in name_to_idx
            ],
        )
        for i, step in enumerate(parsed.steps)
    ]
    return ingredients, steps


def parsed_to_update(parsed: ParsedRecipe) -> RecipeUpdate:
    """Replace a recipe's whole content with what was just re-imported."""
    ingredients, steps = _ingredients_and_steps(parsed.ingredients, parsed)
    return RecipeUpdate(
        title=parsed.title,
        description=parsed.description,
        servings=parsed.servings,
        prep_time_minutes=parsed.prep_time_minutes,
        cook_time_minutes=parsed.cook_time_minutes,
        source_url=parsed.source_url,
        image_url=parsed.image_url,
        ingredients=ingredients,
        steps=steps,
        seasons=parsed.seasons,
        is_vegan=parsed.is_vegan,
        is_vegetarian=parsed.is_vegetarian,
        is_gluten_free=parsed.is_gluten_free,
        is_dairy_free=parsed.is_dairy_free,
        kcal_per_serving=parsed.kcal_per_serving,
        difficulty=parsed.difficulty,
        meal_type=parsed.meal_type,
        cuisine_type=parsed.cuisine_type,
    )


def parsed_to_create(parsed: ParsedRecipe, *, is_public: bool) -> RecipeCreate:
    """A new recipe imported from ``parsed.source_url``, without a human review.

    Nobody gets to fix the model's output first, so anything ``RecipeCreate``
    would reject is dropped or trimmed here rather than failing the import: an
    ingredient with no positive quantity, a description over the length limit.
    """
    usable = [ing for ing in parsed.ingredients if ing.quantity > 0]
    ingredients, steps = _ingredients_and_steps(usable, parsed)
    description = parsed.description
    if description and len(description) > _DESCRIPTION_MAX_LENGTH:
        description = description[: _DESCRIPTION_MAX_LENGTH - 1].rstrip() + "…"
    return RecipeCreate(
        title=parsed.title.strip()[:255],
        description=description,
        servings=parsed.servings if parsed.servings and parsed.servings > 0 else None,
        prep_time_minutes=parsed.prep_time_minutes,
        cook_time_minutes=parsed.cook_time_minutes,
        source_url=parsed.source_url,
        image_url=parsed.image_url,
        is_public=is_public,
        ingredients=ingredients,
        steps=steps,
        seasons=parsed.seasons,
        is_vegan=parsed.is_vegan,
        is_vegetarian=parsed.is_vegetarian,
        is_gluten_free=parsed.is_gluten_free,
        is_dairy_free=parsed.is_dairy_free,
        kcal_per_serving=parsed.kcal_per_serving,
        difficulty=parsed.difficulty,
        meal_type=parsed.meal_type,
        cuisine_type=parsed.cuisine_type,
        import_consent=True,
        import_source=ImportSource.URL,
    )
