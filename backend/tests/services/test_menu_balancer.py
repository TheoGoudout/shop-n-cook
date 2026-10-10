"""The LLM menu balancer: it only suggests, and never stands in the way."""

import json
from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock, patch

from app.models.recipe import MealType
from app.services import menu_balancer
from app.services.menu_balancer import suggest_menu
from tests.services.test_menu_generator import MONDAY, make_recipe, request


def _llm(content: Any) -> MagicMock:
    llm = MagicMock()
    llm.invoke.return_value = MagicMock(content=content)
    return llm


def _sent(llm: MagicMock) -> dict[str, Any]:
    """The JSON payload the model was shown."""
    messages = llm.invoke.call_args.args[0]
    return json.loads(messages[-1].content)  # type: ignore[no-any-return]


def test_the_models_choices_become_suggestions_per_slot() -> None:
    recipes = [make_recipe(f"r{i}") for i in range(3)]
    llm = _llm(
        json.dumps({"meals": [{"slot": 0, "recipe": 2}, {"slot": 1, "recipe": 0}]})
    )
    with patch("app.services.recipe_import.llm.get_llm", return_value=llm):
        suggestions = suggest_menu(recipes, request(days=2))

    shown = {r["number"]: r["title"] for r in _sent(llm)["recipes"]}
    by_title = {r.title: r.id for r in recipes}
    assert suggestions == {
        (MONDAY, MealType.DINNER): by_title[shown[2]],
        (MONDAY + timedelta(days=1), MealType.DINNER): by_title[shown[0]],
    }


def test_anthropic_style_content_blocks_and_fences_are_read() -> None:
    recipes = [make_recipe("only")]
    llm = _llm(
        [
            {
                "type": "text",
                "text": '```json\n{"meals": [{"slot": 0, "recipe": 0}]}\n```',
            }
        ]
    )
    with patch("app.services.recipe_import.llm.get_llm", return_value=llm):
        suggestions = suggest_menu(recipes, request(days=1))
    assert suggestions == {(MONDAY, MealType.DINNER): recipes[0].id}


def test_only_eligible_recipes_are_shown_to_the_model() -> None:
    meaty = make_recipe("meaty")
    vegan = make_recipe("vegan", vegan=True)
    llm = _llm('{"meals": []}')
    with patch("app.services.recipe_import.llm.get_llm", return_value=llm):
        suggest_menu([meaty, vegan], request(days=1, require_vegan=True))
    assert [r["title"] for r in _sent(llm)["recipes"]] == ["vegan"]


def test_the_shortlist_is_capped() -> None:
    recipes = [make_recipe(f"r{i}") for i in range(menu_balancer.SHORTLIST_SIZE + 10)]
    llm = _llm('{"meals": []}')
    with patch("app.services.recipe_import.llm.get_llm", return_value=llm):
        suggest_menu(recipes, request(days=7))
    assert len(_sent(llm)["recipes"]) == menu_balancer.SHORTLIST_SIZE


def test_leftover_days_are_shown_when_batch_cooking() -> None:
    llm = _llm('{"meals": []}')
    with patch("app.services.recipe_import.llm.get_llm", return_value=llm):
        suggest_menu(
            [make_recipe("a"), make_recipe("b")], request(days=4, batch_portions=2)
        )
    slots = _sent(llm)["slots"]
    assert len(slots) == 2
    assert slots[0]["also_eaten_as_leftovers_on"] == [
        (MONDAY + timedelta(days=1)).isoformat()
    ]


def test_out_of_range_and_repeated_choices_are_dropped() -> None:
    recipes = [make_recipe("a"), make_recipe("b")]
    llm = _llm(
        json.dumps(
            {
                "meals": [
                    {"slot": 0, "recipe": 7},
                    {"slot": 5, "recipe": 0},
                    {"slot": 0, "recipe": 0},
                    {"slot": 1, "recipe": 0},
                ]
            }
        )
    )
    with patch("app.services.recipe_import.llm.get_llm", return_value=llm):
        suggestions = suggest_menu(recipes, request(days=2))
    assert list(suggestions) == [(MONDAY, MealType.DINNER)]


def test_an_unreadable_answer_means_no_suggestions() -> None:
    with patch(
        "app.services.recipe_import.llm.get_llm", return_value=_llm("I suggest pasta.")
    ):
        assert suggest_menu([make_recipe("a")], request(days=1)) == {}


def test_no_configured_provider_means_no_suggestions() -> None:
    with patch(
        "app.services.recipe_import.llm.get_llm",
        side_effect=ValueError("ANTHROPIC_API_KEY is not configured"),
    ):
        assert suggest_menu([make_recipe("a")], request(days=1)) == {}


def test_a_provider_outage_means_no_suggestions() -> None:
    llm = MagicMock()
    llm.invoke.side_effect = RuntimeError("503")
    with patch("app.services.recipe_import.llm.get_llm", return_value=llm):
        assert suggest_menu([make_recipe("a")], request(days=1)) == {}


def test_nothing_eligible_means_no_call_at_all() -> None:
    with patch("app.services.recipe_import.llm.get_llm") as get_llm:
        assert suggest_menu([make_recipe("meaty")], request(require_vegan=True)) == {}
    get_llm.assert_not_called()


def test_a_week_without_meals_means_no_call_at_all() -> None:
    with patch("app.services.recipe_import.llm.get_llm") as get_llm:
        assert (
            suggest_menu([make_recipe("a")], request(meals_by_weekday=((),) * 7)) == {}
        )
    get_llm.assert_not_called()
