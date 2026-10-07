"""Turn a ``ParsedRecipe`` into the payloads the recipe CRUD layer accepts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.models import (
    Ingredient,
    IngredientCategory,
    Recipe,
    RecipeCreate,
    RecipeIngredientCreate,
    RecipeStepCreate,
    RecipeUpdate,
)
from app.models.recipe import ImportSource
from app.services.recipe_import.models import (
    ParsedIngredient,
    ParsedRecipe,
    ParsedStep,
)

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


def _clean(parsed: ParsedRecipe) -> ParsedRecipe:
    """``parsed`` without what the recipe schemas would reject.

    Nobody gets to fix the model's output before it is saved, so an ingredient
    with no positive quantity is dropped and a description over the length
    limit is trimmed, rather than failing the whole import.
    """
    description = parsed.description
    if description and len(description) > _DESCRIPTION_MAX_LENGTH:
        description = description[: _DESCRIPTION_MAX_LENGTH - 1].rstrip() + "…"
    return parsed.model_copy(
        update={
            "title": parsed.title.strip()[:255],
            "description": description,
            "servings": parsed.servings
            if parsed.servings and parsed.servings > 0
            else None,
            "ingredients": [ing for ing in parsed.ingredients if ing.quantity > 0],
        }
    )


#: What an import says about a recipe beyond its ingredients and steps.
_CONTENT_FIELDS = {
    "title",
    "description",
    "servings",
    "prep_time_minutes",
    "cook_time_minutes",
    "source_url",
    "image_url",
    "seasons",
    "is_vegan",
    "is_vegetarian",
    "is_gluten_free",
    "is_dairy_free",
    "kcal_per_serving",
    "difficulty",
    "meal_type",
    "cuisine_type",
}


def _content(parsed: ParsedRecipe) -> dict[str, Any]:
    """Everything an import says about a recipe, as recipe-schema fields."""
    parsed = _clean(parsed)
    ingredients, steps = _ingredients_and_steps(parsed.ingredients, parsed)
    return {
        **parsed.model_dump(include=_CONTENT_FIELDS),
        "ingredients": ingredients,
        "steps": steps,
    }


def parsed_to_update(parsed: ParsedRecipe) -> RecipeUpdate:
    """Replace a recipe's whole content with what was just re-imported."""
    return RecipeUpdate(**_content(parsed))


#: Fields ``parsed_to_fill`` may complete: those whose empty value can only
#: mean "unknown". The diet flags are left alone — ``False`` may be a
#: person's answer, and an import must not overrule it.
_FILLABLE = (
    "description",
    "servings",
    "prep_time_minutes",
    "cook_time_minutes",
    "image_url",
    "seasons",
    "kcal_per_serving",
    "difficulty",
    "meal_type",
    "cuisine_type",
)


def parsed_to_fill(parsed: ParsedRecipe, recipe: Recipe) -> RecipeUpdate:
    """Only what ``recipe`` is missing, taken from what was just re-imported.

    Nothing the recipe already has is touched, so whatever its owner wrote or
    corrected survives. Ingredients are filled only when it has none (and then
    its steps with them); steps alone are filled when it has none, linked to
    its existing ingredients by name.
    """
    parsed = _clean(parsed)
    update: dict[str, object] = {
        name: getattr(parsed, name)
        for name in _FILLABLE
        if not getattr(recipe, name) and getattr(parsed, name)
    }
    if not recipe.recipe_ingredients and parsed.ingredients:
        ingredients, steps = _ingredients_and_steps(parsed.ingredients, parsed)
        update["ingredients"] = ingredients
        if not recipe.steps and steps:
            update["steps"] = steps
    elif not recipe.steps and parsed.steps:
        existing = [
            ParsedIngredient(
                name=ri.ingredient_name,
                quantity=ri.quantity,
                unit=ri.unit,
                notes=ri.notes,
            )
            for ri in recipe.recipe_ingredients
        ]
        _, update["steps"] = _ingredients_and_steps(existing, parsed)
    return RecipeUpdate.model_validate(update)


def parsed_to_create(parsed: ParsedRecipe, *, is_public: bool) -> RecipeCreate:
    """A new recipe imported from ``parsed.source_url``, without a human review."""
    return RecipeCreate(
        **_content(parsed),
        is_public=is_public,
        import_consent=True,
        import_source=ImportSource.URL,
        import_language=parsed.language,
    )


def recipe_to_parsed(recipe: Recipe, catalog: Mapping[str, Ingredient]) -> ParsedRecipe:
    """A saved recipe in the shape an import returns, for the client to review.

    ``catalog`` maps ingredient names to their catalogue entries, which hold
    the English names and categories a recipe row does not.
    """
    by_id = {ri.id: ri for ri in recipe.recipe_ingredients}
    ingredients = []
    for ri in recipe.recipe_ingredients:
        entry = catalog.get(ri.ingredient_name)
        ingredients.append(
            ParsedIngredient(
                name=ri.ingredient_name,
                name_en=entry.name_en if entry else None,
                category=entry.category if entry else IngredientCategory.OTHER,
                quantity=ri.quantity,
                unit=ri.unit,
                notes=ri.notes,
            )
        )
    steps = [
        ParsedStep(
            instruction=step.instruction,
            ingredient_names=[
                by_id[si.recipe_ingredient_id].ingredient_name
                for si in step.step_ingredients
                if si.recipe_ingredient_id in by_id
            ],
        )
        for step in sorted(recipe.steps, key=lambda s: s.step_number)
    ]
    return ParsedRecipe(
        **recipe.model_dump(include=_CONTENT_FIELDS - {"seasons"}),
        seasons=recipe.seasons or [],  # the column is nullable
        ingredients=ingredients,
        steps=steps,
        language=recipe.import_language,
    )
