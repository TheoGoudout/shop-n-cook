"""Menu composition: the constraints it must never break, and the ones it trades."""

import uuid
from datetime import date
from decimal import Decimal

import pytest

from app.models.ingredient import Ingredient, Unit
from app.models.recipe import (
    Difficulty,
    MealType,
    Recipe,
    RecipeIngredient,
    Season,
)
from app.services.menu_generator import (
    GenerationRequest,
    generate_menu,
    is_eligible,
    pick_replacement,
    score,
    season_for_date,
)
from app.services.pricing import PriceBook

MONDAY = date(2026, 3, 2)  # a spring date
MIDSUMMER = date(2026, 7, 15)


def make_recipe(
    title: str = "dish",
    *,
    vegan: bool = False,
    vegetarian: bool = False,
    gluten_free: bool = False,
    dairy_free: bool = False,
    seasons: list[Season] | None = None,
    cuisine: str | None = None,
    meal_type: MealType | None = None,
    difficulty: Difficulty | None = None,
    prep: int | None = None,
    cook: int | None = None,
    servings: int = 2,
    ingredient: tuple[str, float, Unit] | None = None,
) -> Recipe:
    recipe = Recipe(
        id=uuid.uuid4(),
        title=title,
        owner_id=uuid.uuid4(),
        servings=servings,
        is_vegan=vegan,
        is_vegetarian=vegetarian,
        is_gluten_free=gluten_free,
        is_dairy_free=dairy_free,
        seasons=seasons or [],
        cuisine_type=cuisine,
        meal_type=meal_type,
        difficulty=difficulty,
        prep_time_minutes=prep,
        cook_time_minutes=cook,
    )
    if ingredient:
        name, quantity, unit = ingredient
        recipe.recipe_ingredients = [
            RecipeIngredient(
                id=uuid.uuid4(),
                recipe_id=recipe.id,
                ingredient_name=name,
                quantity=quantity,
                unit=unit,
            )
        ]
    else:
        recipe.recipe_ingredients = []
    return recipe


def request(**kwargs: object) -> GenerationRequest:
    return GenerationRequest(start_date=MONDAY, **kwargs)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Seasons                                                                      #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("day", "expected"),
    [
        (date(2026, 1, 15), Season.WINTER),
        (date(2026, 4, 15), Season.SPRING),
        (date(2026, 7, 15), Season.SUMMER),
        (date(2026, 10, 15), Season.AUTUMN),
        (date(2026, 12, 15), Season.WINTER),
    ],
)
def test_season_for_date(day: date, expected: Season) -> None:
    assert season_for_date(day) is expected


def test_every_month_maps_to_a_season() -> None:
    for month in range(1, 13):
        assert season_for_date(date(2026, month, 1)) in set(Season)


# --------------------------------------------------------------------------- #
# Hard constraints — these are never traded away                               #
# --------------------------------------------------------------------------- #


def test_a_vegan_menu_contains_only_vegan_recipes() -> None:
    recipes = [make_recipe("meaty"), make_recipe("plants", vegan=True)]
    meals = generate_menu(recipes, request(days=5, require_vegan=True))
    assert meals
    assert all(m.recipe.is_vegan for m in meals)


def test_a_vegan_recipe_satisfies_a_vegetarian_request() -> None:
    """Vegan food is vegetarian; excluding it would be a bug, not strictness."""
    vegan_only = make_recipe("plants", vegan=True, vegetarian=False)
    assert is_eligible(vegan_only, request(require_vegetarian=True), MealType.DINNER)


def test_gluten_free_and_dairy_free_are_enforced() -> None:
    recipes = [
        make_recipe("gluteny"),
        make_recipe("safe", gluten_free=True, dairy_free=True),
    ]
    meals = generate_menu(
        recipes, request(days=3, require_gluten_free=True, require_dairy_free=True)
    )
    assert meals
    assert all(m.recipe.is_gluten_free and m.recipe.is_dairy_free for m in meals)


def test_an_impossible_diet_yields_an_empty_menu_not_a_wrong_one() -> None:
    """A short honest menu beats one that quietly ignores the constraint."""
    meals = generate_menu([make_recipe("meaty")], request(days=5, require_vegan=True))
    assert meals == []


def test_max_prep_minutes_excludes_slow_recipes() -> None:
    quick = make_recipe("quick", prep=10, cook=10)
    slow = make_recipe("slow", prep=60, cook=60)
    meals = generate_menu([quick, slow], request(days=3, max_prep_minutes=30))
    assert {m.recipe.id for m in meals} == {quick.id}


def test_a_recipe_without_timings_survives_a_time_limit() -> None:
    """Absent metadata must not be read as "slow"."""
    untimed = make_recipe("untimed")
    assert is_eligible(untimed, request(max_prep_minutes=15), MealType.DINNER)


def test_desserts_and_drinks_are_not_served_as_dinner() -> None:
    dessert = make_recipe("cake", meal_type=MealType.DESSERT)
    drink = make_recipe("punch", meal_type=MealType.DRINK)
    dinner = make_recipe("stew", meal_type=MealType.DINNER)
    meals = generate_menu([dessert, drink, dinner], request(days=2))
    assert {m.recipe.id for m in meals} == {dinner.id}


def test_an_unclassified_recipe_may_be_used_for_any_meal() -> None:
    unclassified = make_recipe("anything", meal_type=None)
    assert is_eligible(unclassified, request(), MealType.BREAKFAST)
    assert is_eligible(unclassified, request(), MealType.DINNER)


def test_excluded_recipes_are_never_chosen() -> None:
    keep = make_recipe("keep")
    drop = make_recipe("drop")
    meals = generate_menu(
        [keep, drop], request(days=3, exclude_recipe_ids=frozenset({drop.id}))
    )
    assert {m.recipe.id for m in meals} == {keep.id}


# --------------------------------------------------------------------------- #
# Shape of the output                                                          #
# --------------------------------------------------------------------------- #


def test_one_meal_per_slot() -> None:
    recipes = [make_recipe(f"r{i}") for i in range(10)]
    meals = generate_menu(recipes, request(days=7))
    assert len(meals) == 7
    assert [m.entry_date for m in meals] == sorted({m.entry_date for m in meals})


def test_multiple_meal_types_fill_every_slot() -> None:
    recipes = [make_recipe(f"r{i}") for i in range(20)]
    meals = generate_menu(
        recipes,
        request(days=3, meal_types=(MealType.LUNCH, MealType.DINNER)),
    )
    assert len(meals) == 6
    assert {m.meal_type for m in meals} == {MealType.LUNCH, MealType.DINNER}


def test_servings_are_carried_onto_every_meal() -> None:
    meals = generate_menu([make_recipe("r")], request(days=2, servings=5))
    assert all(m.servings == 5 for m in meals)


def test_an_empty_library_yields_an_empty_menu() -> None:
    assert generate_menu([], request(days=7)) == []


# --------------------------------------------------------------------------- #
# Determinism                                                                  #
# --------------------------------------------------------------------------- #


def test_the_same_request_produces_the_same_menu() -> None:
    recipes = [make_recipe(f"r{i}") for i in range(15)]
    first = generate_menu(recipes, request(days=7, seed=42))
    second = generate_menu(recipes, request(days=7, seed=42))
    assert [m.recipe.id for m in first] == [m.recipe.id for m in second]


def test_a_different_seed_can_produce_a_different_menu() -> None:
    recipes = [make_recipe(f"r{i}") for i in range(30)]
    a = generate_menu(recipes, request(days=7, seed=1))
    b = generate_menu(recipes, request(days=7, seed=999))
    assert [m.recipe.id for m in a] != [m.recipe.id for m in b]


# --------------------------------------------------------------------------- #
# Variety                                                                      #
# --------------------------------------------------------------------------- #


def test_variety_beats_repetition_when_alternatives_exist() -> None:
    """Seven equally-good Italian nights is a worse menu than a mixed week."""
    recipes = [
        make_recipe("it1", cuisine="italian"),
        make_recipe("it2", cuisine="italian"),
        make_recipe("jp1", cuisine="japanese"),
        make_recipe("in1", cuisine="indian"),
        make_recipe("fr1", cuisine="french"),
    ]
    meals = generate_menu(recipes, request(days=4))
    cuisines = [m.recipe.cuisine_type for m in meals]
    assert len(set(cuisines)) >= 3


def test_a_repeat_is_allowed_when_there_is_nothing_else() -> None:
    """Variety is a preference, not a hard rule — a short library still fills."""
    only = make_recipe("only", cuisine="italian")
    meals = generate_menu([only], request(days=3))
    assert len(meals) == 3


def test_a_used_cuisine_scores_lower_than_an_unused_one() -> None:
    italian = make_recipe("pasta", cuisine="italian")
    japanese = make_recipe("ramen", cuisine="japanese")
    used = {"italian": 1}
    italian_score = score(
        italian, request(), MONDAY, MealType.DINNER, used, set(), None
    )
    japanese_score = score(
        japanese, request(), MONDAY, MealType.DINNER, used, set(), None
    )
    assert japanese_score > italian_score


def test_a_seasonal_recipe_scores_higher_in_its_season() -> None:
    summery = make_recipe("gazpacho", seasons=[Season.SUMMER])
    in_summer = score(summery, request(), MIDSUMMER, MealType.DINNER, {}, set(), None)
    in_spring = score(summery, request(), MONDAY, MealType.DINNER, {}, set(), None)
    assert in_summer > in_spring


def test_season_matching_can_be_turned_off() -> None:
    summery = make_recipe("gazpacho", seasons=[Season.SUMMER])
    on = score(summery, request(), MIDSUMMER, MealType.DINNER, {}, set(), None)
    off = score(
        summery,
        request(match_season=False),
        MIDSUMMER,
        MealType.DINNER,
        {},
        set(),
        None,
    )
    assert on > off


# --------------------------------------------------------------------------- #
# Budget                                                                       #
# --------------------------------------------------------------------------- #


def _price_book(name: str, amount: str) -> PriceBook:
    return PriceBook(
        [
            Ingredient(
                name=name,
                price_amount=Decimal(amount),
                price_quantity=1.0,
                price_unit=Unit.KILOGRAM,
            )
        ]
    )


def test_the_menu_stops_rather_than_exceeding_the_budget() -> None:
    """10.00 of budget and 4.00 a meal buys two meals, not seven."""
    recipes = [
        make_recipe(f"r{i}", ingredient=("beef", 2, Unit.KILOGRAM), servings=2)
        for i in range(7)
    ]
    prices = _price_book("beef", "2.00")  # 2 kg -> 4.00 per recipe
    meals = generate_menu(
        recipes, request(days=7, servings=2, budget=Decimal("10.00")), prices
    )
    total = sum(m.estimated_cost or Decimal(0) for m in meals)
    assert total <= Decimal("10.00")
    assert len(meals) == 2


def test_a_cheaper_recipe_is_preferred_once_the_budget_is_tight() -> None:
    cheap = make_recipe("cheap", ingredient=("rice", 1, Unit.KILOGRAM))
    dear = make_recipe("dear", ingredient=("beef", 10, Unit.KILOGRAM))
    prices = PriceBook(
        [
            Ingredient(
                name="rice",
                price_amount=Decimal("1.00"),
                price_quantity=1.0,
                price_unit=Unit.KILOGRAM,
            ),
            Ingredient(
                name="beef",
                price_amount=Decimal("20.00"),
                price_quantity=1.0,
                price_unit=Unit.KILOGRAM,
            ),
        ]
    )
    meals = generate_menu(
        [dear, cheap], request(days=1, budget=Decimal("5.00")), prices
    )
    assert [m.recipe.id for m in meals] == [cheap.id]


def test_no_budget_means_no_cost_ceiling() -> None:
    recipes = [
        make_recipe(f"r{i}", ingredient=("beef", 5, Unit.KILOGRAM)) for i in range(5)
    ]
    meals = generate_menu(recipes, request(days=5), _price_book("beef", "20.00"))
    assert len(meals) == 5


def test_an_unpriced_recipe_is_still_usable_under_a_budget() -> None:
    """A budget must not silently exclude everything we lack a price for."""
    unpriced = make_recipe("mystery")
    meals = generate_menu(
        [unpriced], request(days=3, budget=Decimal("5.00")), PriceBook([])
    )
    assert len(meals) == 3


def test_costs_are_reported_per_meal() -> None:
    recipe = make_recipe("r", ingredient=("beef", 1, Unit.KILOGRAM), servings=2)
    meals = generate_menu(
        [recipe], request(days=1, servings=4), _price_book("beef", "10.00")
    )
    # 1 kg at 2 servings, doubled to 4 servings = 2 kg = 20.00
    assert meals[0].estimated_cost == Decimal("20.00")


# --------------------------------------------------------------------------- #
# Swapping one slot                                                            #
# --------------------------------------------------------------------------- #


def test_a_swap_always_returns_something_different() -> None:
    current = make_recipe("current")
    other = make_recipe("other")
    replacement = pick_replacement(
        [current, other],
        request(),
        MONDAY,
        MealType.DINNER,
        current_recipe_id=current.id,
    )
    assert replacement is not None
    assert replacement.id == other.id


def test_a_swap_returns_none_when_there_is_no_alternative() -> None:
    only = make_recipe("only")
    assert (
        pick_replacement(
            [only], request(), MONDAY, MealType.DINNER, current_recipe_id=only.id
        )
        is None
    )


def test_a_swap_respects_the_diet() -> None:
    current = make_recipe("current", vegan=True)
    meaty = make_recipe("meaty")
    vegan_alt = make_recipe("vegan-alt", vegan=True)
    replacement = pick_replacement(
        [current, meaty, vegan_alt],
        request(require_vegan=True),
        MONDAY,
        MealType.DINNER,
        current_recipe_id=current.id,
    )
    assert replacement is not None
    assert replacement.id == vegan_alt.id


def test_a_swap_avoids_a_cuisine_already_used_that_week() -> None:
    """Swapping out of a pasta night should not hand back another one."""
    current = make_recipe("pasta1", cuisine="italian")
    elsewhere = make_recipe("pasta2", cuisine="italian")
    fresh = make_recipe("sushi", cuisine="japanese")
    replacement = pick_replacement(
        [current, elsewhere, fresh],
        request(),
        MONDAY,
        MealType.DINNER,
        current_recipe_id=current.id,
        other_recipe_ids=frozenset({elsewhere.id}),
    )
    assert replacement is not None
    assert replacement.id == fresh.id
