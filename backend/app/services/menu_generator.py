"""Compose a week of meals from the recipes a user can cook.

Deliberately **not** LLM-backed. Menu selection is a constraint problem over
data we already hold — diet flags, seasons, prep time, cuisine, and now cost —
and a scorer is faster, free, reproducible, and testable in a way a prompt is
not. The LLM earns its place reading recipes off the web; it has nothing to add
to arithmetic.

The algorithm is a greedy fill with a variety penalty:

1. discard anything violating a hard constraint (diet, season, time, meal type);
2. score what remains on how well it fits the request;
3. fill slots in order, re-ranking after each pick so that a cuisine already
   used this week is penalised — this is what stops seven pasta nights;
4. stop adding a recipe once it would take the plan over budget, unless nothing
   affordable is left to pick.

Ties break on recipe id, and the shuffle is seeded, so the same request against
the same library always produces the same menu. That matters: a user who does
not like a menu should get a different one by asking for a swap, not by
refreshing and hoping.
"""

import hashlib
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from app.models.recipe import Difficulty, MealType, Recipe, Season
from app.services.pricing import PriceBook

__all__ = [
    "GenerationRequest",
    "PlannedMeal",
    "generate_menu",
    "pick_replacement",
    "season_for_date",
]

#: Northern-hemisphere meteorological seasons, by month.
_SEASON_BY_MONTH: dict[int, Season] = {
    12: Season.WINTER,
    1: Season.WINTER,
    2: Season.WINTER,
    3: Season.SPRING,
    4: Season.SPRING,
    5: Season.SPRING,
    6: Season.SUMMER,
    7: Season.SUMMER,
    8: Season.SUMMER,
    9: Season.AUTUMN,
    10: Season.AUTUMN,
    11: Season.AUTUMN,
}

# Scoring weights. Season and variety dominate because they are what make a
# menu feel composed rather than sampled; the rest are gentle nudges.
_SEASON_BONUS = 30.0
_CUISINE_REPEAT_PENALTY = 25.0
_RECIPE_REPEAT_PENALTY = 60.0
_DIFFICULTY_BONUS = 8.0
_QUICK_BONUS = 10.0
_UNPRICED_PENALTY = 5.0


def season_for_date(day: date) -> Season:
    """Which season a date falls in."""
    return _SEASON_BY_MONTH[day.month]


@dataclass(frozen=True)
class GenerationRequest:
    """What the user asked for.

    ``budget`` is for the whole plan, not per meal — that is how a shopper
    thinks about a week's food, and it is what makes the constraint bite.
    """

    start_date: date
    days: int = 7
    meal_types: tuple[MealType, ...] = (MealType.DINNER,)
    servings: int = 2
    budget: Decimal | None = None
    require_vegan: bool = False
    require_vegetarian: bool = False
    require_gluten_free: bool = False
    require_dairy_free: bool = False
    max_prep_minutes: int | None = None
    match_season: bool = True
    exclude_recipe_ids: frozenset[uuid.UUID] = field(default_factory=frozenset)
    seed: int = 0

    @property
    def dates(self) -> list[date]:
        return [self.start_date + timedelta(days=i) for i in range(self.days)]

    @property
    def slot_count(self) -> int:
        return self.days * len(self.meal_types)


@dataclass(frozen=True)
class PlannedMeal:
    """One chosen recipe, and where it goes."""

    recipe: Recipe
    entry_date: date
    meal_type: MealType
    servings: int
    estimated_cost: Decimal | None


def _total_time(recipe: Recipe) -> int:
    return (recipe.prep_time_minutes or 0) + (recipe.cook_time_minutes or 0)


def is_eligible(
    recipe: Recipe, request: GenerationRequest, meal_type: MealType
) -> bool:
    """Whether a recipe may be used at all — the hard constraints.

    A dietary requirement is never traded off against a better score: someone
    who asked for gluten-free gets gluten-free or gets a shorter menu.
    """
    if recipe.id in request.exclude_recipe_ids:
        return False
    if request.require_vegan and not recipe.is_vegan:
        return False
    # Vegan food is vegetarian, so a vegan recipe satisfies a vegetarian ask.
    if request.require_vegetarian and not (recipe.is_vegetarian or recipe.is_vegan):
        return False
    if request.require_gluten_free and not recipe.is_gluten_free:
        return False
    if request.require_dairy_free and not recipe.is_dairy_free:
        return False
    if request.max_prep_minutes is not None:
        # A recipe that declares no timings is not excluded by a time limit —
        # absent metadata should not be read as "slow".
        total = _total_time(recipe)
        if total > request.max_prep_minutes:
            return False
    # An unset meal_type means the recipe is unclassified, not unsuitable.
    if recipe.meal_type is not None and recipe.meal_type != meal_type:
        # Desserts and drinks are specific enough that using one as a dinner is
        # plainly wrong; everything else is just a weak preference.
        if recipe.meal_type in (MealType.DESSERT, MealType.DRINK):
            return False
    return True


def score(
    recipe: Recipe,
    request: GenerationRequest,
    day: date,
    meal_type: MealType,
    used_cuisines: dict[str, int],
    used_recipe_ids: set[uuid.UUID],
    cost: Decimal | None,
) -> float:
    """How well this recipe suits this slot, given what is already chosen."""
    points = 0.0

    if request.match_season and recipe.seasons:
        if season_for_date(day) in recipe.seasons:
            points += _SEASON_BONUS

    if recipe.meal_type == meal_type:
        points += _DIFFICULTY_BONUS

    if recipe.difficulty is Difficulty.EASY:
        points += _DIFFICULTY_BONUS

    total = _total_time(recipe)
    if total and total <= 30:
        points += _QUICK_BONUS

    # Variety: each prior use of a cuisine makes the next one less appealing.
    if recipe.cuisine_type:
        points -= _CUISINE_REPEAT_PENALTY * used_cuisines.get(
            recipe.cuisine_type.lower(), 0
        )

    if recipe.id in used_recipe_ids:
        points -= _RECIPE_REPEAT_PENALTY

    # Prefer recipes we can actually cost, so the budget figure means something.
    if cost is None:
        points -= _UNPRICED_PENALTY

    return points


def _cost_of(recipe: Recipe, prices: PriceBook | None, servings: int) -> Decimal | None:
    if prices is None:
        return None
    scale = servings / (recipe.servings or 1)
    summary = prices.summarize(
        [
            (ri.ingredient_name, ri.quantity * scale, ri.unit)
            for ri in recipe.recipe_ingredients
        ]
    )
    return summary.total


def _tiebreaker(seed: int) -> Callable[[uuid.UUID], str]:
    """A stable per-seed ordering over recipe ids.

    Equally-scoring recipes are extremely common — most of a library shares a
    score when no seasons or cuisines are set — so the tiebreak decides the
    menu far more often than the scorer does. Breaking on the raw id would give
    every user with the same library the identical week and make ``seed``
    inert; hashing the id together with the seed keeps runs reproducible while
    letting a different seed genuinely produce a different menu.
    """

    def key(recipe_id: uuid.UUID) -> str:
        digest = hashlib.blake2b(f"{seed}:{recipe_id.hex}".encode(), digest_size=8)
        return digest.hexdigest()

    return key


def _rank(
    candidates: list[Recipe],
    request: GenerationRequest,
    day: date,
    meal_type: MealType,
    used_cuisines: dict[str, int],
    used_recipe_ids: set[uuid.UUID],
    costs: dict[uuid.UUID, Decimal | None],
    tiebreak: Callable[[uuid.UUID], str],
) -> list[Recipe]:
    """Candidates best-first, with a deterministic, seed-dependent tiebreak."""
    return sorted(
        candidates,
        key=lambda r: (
            -score(
                r,
                request,
                day,
                meal_type,
                used_cuisines,
                used_recipe_ids,
                costs.get(r.id),
            ),
            tiebreak(r.id),
        ),
    )


def generate_menu(
    recipes: list[Recipe],
    request: GenerationRequest,
    prices: PriceBook | None = None,
) -> list[PlannedMeal]:
    """Choose a recipe for each slot in the request.

    Returns fewer meals than slots when the constraints cannot be met — an
    honest short menu beats one that quietly ignores the diet it was given.
    """
    costs: dict[uuid.UUID, Decimal | None] = {
        r.id: _cost_of(r, prices, request.servings) for r in recipes
    }

    pool = list(recipes)
    tiebreak = _tiebreaker(request.seed)

    used_cuisines: dict[str, int] = {}
    used_recipe_ids: set[uuid.UUID] = set()
    spent = Decimal(0)
    chosen: list[PlannedMeal] = []

    for day in request.dates:
        for meal_type in request.meal_types:
            eligible = [r for r in pool if is_eligible(r, request, meal_type)]
            if not eligible:
                continue

            ranked = _rank(
                eligible,
                request,
                day,
                meal_type,
                used_cuisines,
                used_recipe_ids,
                costs,
                tiebreak,
            )

            pick = _first_affordable(ranked, costs, spent, request.budget)
            if pick is None:
                # Nothing left that fits the budget; the menu ends here rather
                # than silently going over.
                return chosen

            cost = costs.get(pick.id)
            if cost is not None:
                spent += cost
            if pick.cuisine_type:
                key = pick.cuisine_type.lower()
                used_cuisines[key] = used_cuisines.get(key, 0) + 1
            used_recipe_ids.add(pick.id)

            chosen.append(
                PlannedMeal(
                    recipe=pick,
                    entry_date=day,
                    meal_type=meal_type,
                    servings=request.servings,
                    estimated_cost=cost,
                )
            )

    return chosen


def _first_affordable(
    ranked: list[Recipe],
    costs: dict[uuid.UUID, Decimal | None],
    spent: Decimal,
    budget: Decimal | None,
) -> Recipe | None:
    """Best-ranked recipe that still fits the budget.

    An unpriced recipe is allowed through: refusing it would mean a budget
    silently excluded everything we simply do not know the price of.
    """
    if budget is None:
        return ranked[0] if ranked else None
    for recipe in ranked:
        cost = costs.get(recipe.id)
        if cost is None or spent + cost <= budget:
            return recipe
    return None


def pick_replacement(
    recipes: list[Recipe],
    request: GenerationRequest,
    day: date,
    meal_type: MealType,
    *,
    current_recipe_id: uuid.UUID,
    other_recipe_ids: frozenset[uuid.UUID] = frozenset(),
    prices: PriceBook | None = None,
) -> Recipe | None:
    """Swap one slot without disturbing the rest of the plan.

    The recipe being replaced is excluded so a swap always changes something,
    and the rest of the week is passed in as ``other_recipe_ids`` so the
    replacement still respects the variety rules.
    """
    costs: dict[uuid.UUID, Decimal | None] = {
        r.id: _cost_of(r, prices, request.servings) for r in recipes
    }
    used_cuisines: dict[str, int] = {}
    for recipe in recipes:
        if recipe.id in other_recipe_ids and recipe.cuisine_type:
            key = recipe.cuisine_type.lower()
            used_cuisines[key] = used_cuisines.get(key, 0) + 1

    eligible = [
        r
        for r in recipes
        if r.id != current_recipe_id and is_eligible(r, request, meal_type)
    ]
    if not eligible:
        return None

    ranked = _rank(
        eligible,
        request,
        day,
        meal_type,
        used_cuisines,
        set(other_recipe_ids),
        costs,
        _tiebreaker(request.seed),
    )
    return ranked[0]
