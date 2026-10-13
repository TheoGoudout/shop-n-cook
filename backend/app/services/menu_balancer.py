"""Ask an LLM to suggest a balanced week from the recipes a user can cook.

The scorer in ``menu_generator`` knows diet flags, seasons, cuisines and cost,
but not what a dish *is*: that Monday's steak and Tuesday's burger are both red
meat, or that three creamy gratins make a heavy week. Reading titles and
ingredient lists is what an LLM is good at, so it is asked to compose the week.

It only ever suggests. Its answer is a recipe for some cooking slots, taken
from a shortlist the generator already deemed eligible, and ``generate_menu``
puts every suggestion through the same checks as its own picks (diet, meal
type, budget, no repeats). Any failure — no provider configured, a timeout, an
answer that does not parse — returns no suggestions, and the scorer composes
the menu on its own.
"""

import json
import logging
import random
import uuid
from decimal import Decimal
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, ValidationError

from app.models.recipe import Recipe
from app.services.menu_generator import (
    GenerationRequest,
    Slot,
    auto_pickable,
    cooking_slots,
    cost_of,
    is_eligible,
    score,
)
from app.services.pricing import PriceBook
from app.services.recipe_import import llm as llm_module

__all__ = ["suggest_menu"]

logger = logging.getLogger(__name__)

#: Recipes shown to the model. Enough to compose a varied week from, few enough
#: to keep the prompt small and the answer quick.
SHORTLIST_SIZE = 40
#: Ingredients listed per recipe: the main ones come first in most recipes.
_INGREDIENTS_SHOWN = 8

_SYSTEM_PROMPT = """\
You plan a household's meals for the coming days, choosing only from the \
recipes you are given.

Compose a balanced, varied menu:
- vary the main protein across the week (red meat, poultry, fish, eggs, \
legumes, tofu…) and do not serve the same one two meals in a row;
- include vegetables every day, and alternate richer dishes with lighter ones;
- vary cuisines, cooking methods and textures;
- prefer quicker recipes on weekdays and keep longer ones for the weekend;
- respect each slot's meal (a breakfast slot gets a breakfast);
- when a budget is given, keep the total of the costs within it.

Use each recipe at most once. Reply with JSON only, no prose:
{"meals": [{"slot": <slot number>, "recipe": <recipe number>}, ...]}
"""


class _Choice(BaseModel):
    slot: int
    recipe: int


class _Answer(BaseModel):
    meals: list[_Choice]


def _shortlist(
    recipes: list[Recipe],
    request: GenerationRequest,
    slots: list[Slot],
    costs: dict[uuid.UUID, Decimal | None],
) -> list[Recipe]:
    """Up to ``SHORTLIST_SIZE`` eligible recipes, drawn by score.

    A weighted draw rather than the top of the ranking, so each seed shows the
    model a different part of the library and the menus keep changing.
    """
    best: dict[uuid.UUID, float] = {}
    for recipe in recipes:
        for day, meal_type in slots:
            if auto_pickable(recipe, meal_type) and is_eligible(
                recipe, request, meal_type
            ):
                points = score(
                    recipe, request, day, meal_type, {}, set(), costs.get(recipe.id)
                )
                best[recipe.id] = max(points, best.get(recipe.id, points))
    eligible = [r for r in recipes if r.id in best]
    if len(eligible) <= SHORTLIST_SIZE:
        return eligible
    # Weighted sampling without replacement (Efraimidis–Spirakis): the
    # largest ``u ** (1 / w)`` keys win. Scores are shifted so weights are > 0.
    rng = random.Random(request.seed)
    low = min(best.values())
    keyed = sorted(
        eligible,
        key=lambda r: rng.random() ** (1 / (1 + (best[r.id] - low) / 10)),
        reverse=True,
    )
    return keyed[:SHORTLIST_SIZE]


def _describe(recipe: Recipe, number: int, cost: Decimal | None) -> dict[str, Any]:
    total_time = (recipe.prep_time_minutes or 0) + (recipe.cook_time_minutes or 0)
    described: dict[str, Any] = {
        "number": number,
        "title": recipe.title,
        "ingredients": [
            ri.ingredient_name for ri in recipe.recipe_ingredients[:_INGREDIENTS_SHOWN]
        ],
    }
    optional: dict[str, Any] = {
        "meal": recipe.meal_type.value if recipe.meal_type else None,
        "cuisine": recipe.cuisine_type,
        "minutes": total_time or None,
        "kcal_per_serving": recipe.kcal_per_serving,
        "vegetarian": recipe.is_vegetarian or recipe.is_vegan or None,
        "cost": str(cost) if cost is not None else None,
    }
    described.update({k: v for k, v in optional.items() if v is not None})
    return described


def _text_of(content: Any) -> str:
    """The text of a chat model reply, plain or Anthropic-style content blocks."""
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        text = "".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        )
    else:
        text = ""
    # Tolerate code fences or a sentence around the JSON object.
    start, end = text.find("{"), text.rfind("}")
    return text[start : end + 1] if start != -1 and end > start else text


def suggest_menu(
    recipes: list[Recipe],
    request: GenerationRequest,
    prices: PriceBook | None = None,
) -> dict[Slot, uuid.UUID]:
    """A recipe for each cooking slot the model could fill; empty on any failure."""
    shape = cooking_slots(request)
    slots = [slot for slot, _ in shape]
    if not slots:
        return {}
    costs = {
        r.id: cost_of(r, prices, request.servings * request.batch_portions)
        for r in recipes
    }
    shortlist = _shortlist(recipes, request, slots, costs)
    if not shortlist:
        return {}

    payload = {
        "servings_per_meal": request.servings,
        "budget": str(request.budget) if request.budget is not None else None,
        "slots": [
            {
                "slot": i,
                "date": day.isoformat(),
                "weekday": day.strftime("%A"),
                "meal": meal_type.value,
                **(
                    {"also_eaten_as_leftovers_on": [d.isoformat() for d, _ in rest]}
                    if rest
                    else {}
                ),
            }
            for i, ((day, meal_type), rest) in enumerate(shape)
        ],
        "recipes": [
            _describe(recipe, i, costs.get(recipe.id))
            for i, recipe in enumerate(shortlist)
        ],
    }
    messages = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=json.dumps(payload, ensure_ascii=False)),
    ]

    try:
        llm_module.configure_langsmith()
        response = llm_module.get_llm().invoke(messages)
        answer = _Answer.model_validate_json(_text_of(response.content))
    except (ValueError, ValidationError) as exc:
        # ValueError covers a missing provider key as well as bad JSON.
        logger.warning("Menu balancing unavailable: %s", exc)
        return {}
    except Exception:
        # A provider outage must never stop a menu from being composed.
        logger.exception("Menu balancing failed")
        return {}

    suggestions: dict[Slot, uuid.UUID] = {}
    used: set[int] = set()
    for choice in answer.meals:
        if not 0 <= choice.slot < len(slots) or not 0 <= choice.recipe < len(shortlist):
            continue
        if choice.recipe in used or slots[choice.slot] in suggestions:
            continue
        used.add(choice.recipe)
        suggestions[slots[choice.slot]] = shortlist[choice.recipe].id
    return suggestions
