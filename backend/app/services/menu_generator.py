"""Compose a week of meals from the recipes a user can cook.

The generator itself is a scorer, not a prompt: diet flags, seasons, prep time,
cuisine and cost are data we already hold, and the hard constraints (diet,
time, budget) must hold every time. An LLM may *suggest* a balanced week
(``services/menu_balancer.py``), but its suggestions go through the same
checks as everything else, and the scorer fills any slot it gets wrong.

The algorithm is a greedy fill with a variety penalty:

1. discard anything violating a hard constraint (diet, season, time, meal type),
   and anything classified for another kind of meal — a lunch or dinner slot
   takes only lunch, dinner or unclassified recipes, and desserts, drinks and
   "other" (sauces, stocks, sides) are never chosen;
2. score what remains on how well it fits the request, penalising recipes the
   household already ate in the last few weeks;
3. fill slots in order, re-ranking after each pick so that a cuisine already
   used this week is penalised — this is what stops seven pasta nights;
4. pick at random among the recipes scoring close to the best, the better ones
   more likely. Always taking the single best recipe made every menu the same
   handful of dishes; sampling keeps the preferences while letting the whole
   library come up;
5. stop adding a recipe once it would take the plan over budget, unless nothing
   affordable is left to pick;
6. when batch cooking, a pick also fills the next free slots on later days as
   leftovers, and is priced for every meal it covers.

The random choices are seeded, so the same request against the same library
always produces the same menu, and a different seed a different one.
"""

import hashlib
import math
import random
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from app.models.recipe import Difficulty, MealType, Recipe, Season
from app.services.pricing import PriceBook

__all__ = [
    "GenerationRequest",
    "PlannedMeal",
    "Slot",
    "auto_pickable",
    "cooking_slots",
    "cost_of",
    "generate_menu",
    "is_eligible",
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
#: Eaten in the household's plans of the last few weeks: still possible, but a
#: menu should not hand back last week's.
_RECENT_PENALTY = 20.0

# Sampling. Only recipes within the window of the best score are drawn, so a
# repeat cuisine (25) or an out-of-season recipe (30) is never preferred over a
# fitting one; within it, each ``_TEMPERATURE`` points below the best makes a
# recipe e (~2.7) times less likely.
_SAMPLING_WINDOW = 24.0
_TEMPERATURE = 8.0


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
    #: Which meals to plan on each weekday, Monday first (``date.weekday()``
    #: order). ``None`` means every day gets ``meal_types``; an empty entry
    #: means that day is skipped — eating out, at the in-laws', …
    meals_by_weekday: tuple[tuple[MealType, ...], ...] | None = None
    #: Batch cooking: how many meals one cooking covers. Above one, each recipe
    #: is cooked in a larger quantity and eaten again on the following days.
    batch_portions: int = 1
    #: Recipes the household ate recently, made less likely to come back.
    recent_recipe_ids: frozenset[uuid.UUID] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if self.meals_by_weekday is not None and len(self.meals_by_weekday) != 7:
            raise ValueError("meals_by_weekday needs one entry per weekday")
        if self.batch_portions < 1:
            raise ValueError("batch_portions must be at least 1")

    @property
    def dates(self) -> list[date]:
        return [self.start_date + timedelta(days=i) for i in range(self.days)]

    def meal_types_for(self, day: date) -> tuple[MealType, ...]:
        """The meals to plan on ``day``."""
        if self.meals_by_weekday is None:
            return self.meal_types
        return self.meals_by_weekday[day.weekday()]

    @property
    def slot_count(self) -> int:
        return sum(len(self.meal_types_for(day)) for day in self.dates)


@dataclass(frozen=True)
class PlannedMeal:
    """One chosen recipe, and where it goes."""

    recipe: Recipe
    entry_date: date
    meal_type: MealType
    #: Servings eaten at each meal, the cooked one and every leftover alike.
    servings: int
    #: Cost of the whole batch: ``servings`` for every meal it covers.
    estimated_cost: Decimal | None
    #: Later slots eaten from this same cooking, when batch cooking.
    leftovers: tuple[tuple[date, MealType], ...] = ()

    @property
    def portions(self) -> int:
        """How many meals this one cooking covers."""
        return 1 + len(self.leftovers)


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


#: Which classified recipes the generator may choose on its own for each slot.
#: Lunch and dinner are interchangeable — people do swap them — but a breakfast
#: or a snack is not a dinner. Desserts, drinks and "other" (sauces, stocks,
#: dressings, sides: parts of a meal rather than one) are absent, so they are
#: never chosen automatically. Any of them can still be added by hand.
_AUTO_PICKABLE: dict[MealType, frozenset[MealType]] = {
    MealType.BREAKFAST: frozenset({MealType.BREAKFAST}),
    MealType.LUNCH: frozenset({MealType.LUNCH, MealType.DINNER}),
    MealType.DINNER: frozenset({MealType.LUNCH, MealType.DINNER}),
    MealType.SNACK: frozenset({MealType.SNACK}),
}


def auto_pickable(recipe: Recipe, meal_type: MealType) -> bool:
    """Whether the generator may choose this recipe on its own for this slot.

    An unclassified recipe stays allowed everywhere: a missing meal type is not
    evidence that the recipe is unsuitable.
    """
    if recipe.meal_type is None:
        return True
    return recipe.meal_type in _AUTO_PICKABLE.get(meal_type, frozenset())


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

    if recipe.id in request.recent_recipe_ids:
        points -= _RECENT_PENALTY

    # Prefer recipes we can actually cost, so the budget figure means something.
    if cost is None:
        points -= _UNPRICED_PENALTY

    return points


def cost_of(recipe: Recipe, prices: PriceBook | None, servings: int) -> Decimal | None:
    """What cooking ``recipe`` for ``servings`` costs, or ``None`` if unpriced."""
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

    Sampling walks the candidates in rank order, so equally-scoring recipes
    need an order that does not depend on how the database returned them.
    Hashing the id together with the seed keeps runs reproducible without
    favouring the same recipes for every seed.
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
) -> list[tuple[Recipe, float]]:
    """Candidates with their score, best-first, in a seed-dependent stable order."""
    scored = [
        (
            r,
            score(
                r,
                request,
                day,
                meal_type,
                used_cuisines,
                used_recipe_ids,
                costs.get(r.id),
            ),
        )
        for r in candidates
    ]
    scored.sort(key=lambda pair: (-pair[1], tiebreak(pair[0].id)))
    return scored


def _sample(ranked: list[tuple[Recipe, float]], rng: random.Random) -> Recipe:
    """Draw one of the recipes scoring close to the best, the better more likely."""
    best = ranked[0][1]
    pool = [(r, s) for r, s in ranked if best - s <= _SAMPLING_WINDOW]
    weights = [math.exp((s - best) / _TEMPERATURE) for _, s in pool]
    return rng.choices([r for r, _ in pool], weights=weights)[0]


Slot = tuple[date, MealType]


def _leftover_slots(
    slots: list[Slot], start: int, filled: set[Slot], portions: int
) -> list[Slot]:
    """Where the rest of a batch cooked for ``slots[start]`` is eaten.

    Leftovers go to the next free slots on *later* days — nobody wants the same
    dish for lunch and dinner — one per day, so a batch of three is spread over
    three days rather than eaten twice tomorrow.
    """
    cook_day = slots[start][0]
    days_used = {cook_day}
    leftovers: list[Slot] = []
    for slot in slots[start + 1 :]:
        if len(leftovers) == portions - 1:
            break
        day = slot[0]
        if slot in filled or day in days_used:
            continue
        leftovers.append(slot)
        days_used.add(day)
    return leftovers


def _all_slots(request: GenerationRequest) -> list[Slot]:
    return [
        (day, meal_type)
        for day in request.dates
        for meal_type in request.meal_types_for(day)
    ]


def cooking_slots(request: GenerationRequest) -> list[tuple[Slot, list[Slot]]]:
    """The slots a recipe is cooked in, each with the slots eaten as leftovers.

    This is the menu's shape when every slot can be filled; without batch
    cooking, every slot is cooked and has no leftovers.
    """
    slots = _all_slots(request)
    filled: set[Slot] = set()
    shape: list[tuple[Slot, list[Slot]]] = []
    for index, slot in enumerate(slots):
        if slot in filled:
            continue
        leftovers = _leftover_slots(slots, index, filled, request.batch_portions)
        filled.add(slot)
        filled.update(leftovers)
        shape.append((slot, leftovers))
    return shape


def generate_menu(
    recipes: list[Recipe],
    request: GenerationRequest,
    prices: PriceBook | None = None,
    suggested: Mapping[Slot, uuid.UUID] | None = None,
) -> list[PlannedMeal]:
    """Choose a recipe for each slot in the request.

    With ``batch_portions`` above one, each recipe chosen is cooked once for
    several meals and also fills the next free slots as leftovers, so the menu
    has fewer recipes than slots.

    ``suggested`` proposes a recipe for some cooking slots (an LLM's balanced
    week). A suggestion is taken only when it passes every check a scored pick
    does — eligible, affordable, not already on the menu; otherwise the slot is
    filled as if there were no suggestion.

    Returns fewer meals than slots when the constraints cannot be met — an
    honest short menu beats one that quietly ignores the diet it was given.
    """
    # Batch costs, by how many meals the batch covers. Scoring only cares
    # whether a recipe is priced, so it always reads the single-meal costs.
    costs_by_portions: dict[int, dict[uuid.UUID, Decimal | None]] = {}

    def costs_for(portions: int) -> dict[uuid.UUID, Decimal | None]:
        if portions not in costs_by_portions:
            costs_by_portions[portions] = {
                r.id: cost_of(r, prices, request.servings * portions) for r in recipes
            }
        return costs_by_portions[portions]

    costs = costs_for(1)

    pool = list(recipes)
    tiebreak = _tiebreaker(request.seed)
    rng = random.Random(request.seed)
    suggested = suggested or {}

    used_cuisines: dict[str, int] = {}
    used_recipe_ids: set[uuid.UUID] = set()
    spent = Decimal(0)
    chosen: list[PlannedMeal] = []

    slots = _all_slots(request)
    filled: set[Slot] = set()

    for index, (day, meal_type) in enumerate(slots):
        if (day, meal_type) in filled:
            continue
        eligible = [
            r
            for r in pool
            if auto_pickable(r, meal_type) and is_eligible(r, request, meal_type)
        ]
        if not eligible:
            continue

        leftovers = _leftover_slots(slots, index, filled, request.batch_portions)
        portions = 1 + len(leftovers)
        batch_costs = costs_for(portions)

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

        affordable = _affordable(ranked, batch_costs, spent, request.budget)
        if not affordable:
            # Nothing left that fits the budget; the menu ends here rather
            # than silently going over.
            return chosen

        wanted = suggested.get((day, meal_type))
        pick = next(
            (
                r
                for r, _ in affordable
                if r.id == wanted and r.id not in used_recipe_ids
            ),
            None,
        ) or _sample(affordable, rng)

        cost = batch_costs.get(pick.id)
        if cost is not None:
            spent += cost
        if pick.cuisine_type:
            key = pick.cuisine_type.lower()
            used_cuisines[key] = used_cuisines.get(key, 0) + 1
        used_recipe_ids.add(pick.id)
        filled.add((day, meal_type))
        filled.update(leftovers)

        chosen.append(
            PlannedMeal(
                recipe=pick,
                entry_date=day,
                meal_type=meal_type,
                servings=request.servings,
                estimated_cost=cost,
                leftovers=tuple(leftovers),
            )
        )

    return chosen


def _affordable(
    ranked: list[tuple[Recipe, float]],
    costs: dict[uuid.UUID, Decimal | None],
    spent: Decimal,
    budget: Decimal | None,
) -> list[tuple[Recipe, float]]:
    """The ranked recipes that still fit the budget, in the same order.

    An unpriced recipe is allowed through: refusing it would mean a budget
    silently excluded everything we simply do not know the price of.
    """
    if budget is None:
        return ranked
    return [
        (recipe, points)
        for recipe, points in ranked
        if (cost := costs.get(recipe.id)) is None or spent + cost <= budget
    ]


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
    replacement still respects the variety rules. The replacement is drawn like
    any other pick, so swapping again with another seed offers another recipe
    rather than flipping between the same two.
    """
    costs: dict[uuid.UUID, Decimal | None] = {
        r.id: cost_of(r, prices, request.servings) for r in recipes
    }
    used_cuisines: dict[str, int] = {}
    for recipe in recipes:
        if recipe.id in other_recipe_ids and recipe.cuisine_type:
            key = recipe.cuisine_type.lower()
            used_cuisines[key] = used_cuisines.get(key, 0) + 1

    eligible = [
        r
        for r in recipes
        if r.id != current_recipe_id
        and auto_pickable(r, meal_type)
        and is_eligible(r, request, meal_type)
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
    return _sample(ranked, random.Random(request.seed))
