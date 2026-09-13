"""LLM price estimation: what it accepts, what it drops, what it must not touch."""

import json
import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from sqlmodel import Session

from app import crud
from app.models import IngredientCreate
from app.models.ingredient import Ingredient, PriceSource, Unit
from app.services.ingredient_price import (
    EstimatedPrice,
    apply_estimates,
    build_price_prompt,
    estimate_prices_batch,
    may_overwrite,
    parse_price_response,
)
from app.services.recipe_import import llm as llm_module
from tests.utils.utils import random_lower_string


def make(name: str, **kwargs: object) -> Ingredient:
    return Ingredient(name=name, **kwargs)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Parsing                                                                      #
# --------------------------------------------------------------------------- #


def test_parses_a_plain_json_array() -> None:
    raw = '[{"name": "flour", "price_amount": 2.5, "price_unit": "kg"}]'
    estimates = parse_price_response(raw)
    assert len(estimates) == 1
    assert estimates[0].name == "flour"
    assert estimates[0].price_amount == Decimal("2.5")
    assert estimates[0].price_unit is Unit.KILOGRAM


def test_strips_markdown_fences() -> None:
    raw = '```json\n[{"name": "rice", "price_amount": 1.8, "price_unit": "kg"}]\n```'
    assert len(parse_price_response(raw)) == 1


def test_handles_anthropic_content_blocks() -> None:
    raw = [
        {
            "type": "text",
            "text": '[{"name": "egg", "price_amount": 0.3, "price_unit": "piece"}]',
        }
    ]
    estimates = parse_price_response(raw)
    assert estimates[0].price_unit is Unit.PIECE


def test_optional_bridges_are_carried_through() -> None:
    raw = (
        '[{"name": "milk", "price_amount": 1.2, "price_unit": "L", '
        '"density_g_per_ml": 1.03, "piece_weight_g": null}]'
    )
    estimate = parse_price_response(raw)[0]
    assert estimate.density_g_per_ml == 1.03
    assert estimate.piece_weight_g is None


def test_malformed_json_yields_nothing_rather_than_raising() -> None:
    assert parse_price_response("not json at all") == []
    assert parse_price_response("") == []
    assert parse_price_response(None) == []


def test_a_non_array_response_is_rejected() -> None:
    assert parse_price_response('{"name": "flour"}') == []


def test_one_bad_entry_does_not_lose_the_whole_batch() -> None:
    raw = (
        '[{"name": "flour", "price_amount": 2.5, "price_unit": "kg"}, '
        '{"name": "broken", "price_unit": "kg"}, '
        '{"name": "rice", "price_amount": 1.8, "price_unit": "kg"}]'
    )
    estimates = parse_price_response(raw)
    assert [e.name for e in estimates] == ["flour", "rice"]


def test_an_unknown_unit_is_dropped() -> None:
    raw = '[{"name": "flour", "price_amount": 2.5, "price_unit": "furlong"}]'
    assert parse_price_response(raw) == []


def test_implausible_prices_are_dropped() -> None:
    """A hallucinated order of magnitude must not reach the catalog."""
    too_big = '[{"name": "flour", "price_amount": 99999, "price_unit": "kg"}]'
    assert parse_price_response(too_big) == []


def test_a_zero_or_negative_price_is_dropped() -> None:
    assert (
        parse_price_response('[{"name": "x", "price_amount": 0, "price_unit": "kg"}]')
        == []
    )
    assert (
        parse_price_response('[{"name": "x", "price_amount": -3, "price_unit": "kg"}]')
        == []
    )


# --------------------------------------------------------------------------- #
# Overwrite policy — the central guarantee                                     #
# --------------------------------------------------------------------------- #


def test_a_curated_price_is_never_overwritten() -> None:
    curated = make("flour", price_source=PriceSource.MANUAL)
    assert not may_overwrite(curated)


def test_an_unpriced_ingredient_may_be_estimated() -> None:
    assert may_overwrite(make("flour"))


def test_a_previous_estimate_may_be_refreshed() -> None:
    assert may_overwrite(make("flour", price_source=PriceSource.ESTIMATED))


def test_apply_estimates_leaves_curated_rows_alone() -> None:
    curated = make(
        "flour",
        price_amount=Decimal("2.00"),
        price_quantity=1.0,
        price_unit=Unit.KILOGRAM,
        price_source=PriceSource.MANUAL,
    )
    estimates = [
        EstimatedPrice(
            name="flour", price_amount=Decimal("9.99"), price_unit=Unit.KILOGRAM
        )
    ]
    changed = apply_estimates([curated], estimates)

    assert changed == []
    assert curated.price_amount == Decimal("2.00")
    assert curated.price_source is PriceSource.MANUAL


def test_apply_estimates_fills_an_unpriced_row() -> None:
    ingredient = make("flour")
    estimates = [
        EstimatedPrice(
            name="flour",
            price_amount=Decimal("2.50"),
            price_unit=Unit.KILOGRAM,
            density_g_per_ml=0.53,
        )
    ]
    changed = apply_estimates([ingredient], estimates)

    assert changed == [ingredient]
    assert ingredient.price_amount == Decimal("2.50")
    assert ingredient.price_quantity == 1.0
    assert ingredient.price_unit is Unit.KILOGRAM
    assert ingredient.density_g_per_ml == 0.53
    assert ingredient.price_source is PriceSource.ESTIMATED
    assert ingredient.price_updated_at is not None


def test_apply_estimates_matches_names_case_insensitively() -> None:
    ingredient = make("Flour")
    changed = apply_estimates(
        [ingredient],
        [
            EstimatedPrice(
                name="  flour ", price_amount=Decimal("2.50"), price_unit=Unit.KILOGRAM
            )
        ],
    )
    assert changed == [ingredient]


def test_an_estimate_for_an_ingredient_we_did_not_ask_about_is_ignored() -> None:
    ingredient = make("flour")
    changed = apply_estimates(
        [ingredient],
        [
            EstimatedPrice(
                name="saffron", price_amount=Decimal("30"), price_unit=Unit.KILOGRAM
            )
        ],
    )
    assert changed == []
    assert ingredient.price_amount is None


def test_bridges_are_only_set_when_the_model_supplied_them() -> None:
    """An omitted density must not wipe one that was already curated."""
    ingredient = make("oil", density_g_per_ml=0.92)
    apply_estimates(
        [ingredient],
        [
            EstimatedPrice(
                name="oil", price_amount=Decimal("3.00"), price_unit=Unit.LITER
            )
        ],
    )
    assert ingredient.density_g_per_ml == 0.92


# --------------------------------------------------------------------------- #
# Prompt                                                                       #
# --------------------------------------------------------------------------- #


def test_prompt_names_the_currency_and_the_allowed_units() -> None:
    prompt = build_price_prompt("GBP")
    assert "GBP" in prompt
    for unit in (Unit.KILOGRAM, Unit.LITER, Unit.PIECE):
        assert unit.value in prompt


# --------------------------------------------------------------------------- #
# The batch entry point, against a real database and a stubbed model           #
# --------------------------------------------------------------------------- #


def test_batch_writes_estimates_to_the_database(db: Session) -> None:
    ingredient = crud.create_ingredient(
        session=db,
        ingredient_in=IngredientCreate(name=f"quinoa-{random_lower_string()}"),
    )
    reply = SimpleNamespace(
        content=json.dumps(
            [
                {
                    "name": ingredient.name,
                    "price_amount": 5.5,
                    "price_unit": "kg",
                    "density_g_per_ml": None,
                    "piece_weight_g": None,
                }
            ]
        )
    )

    with patch.object(llm_module, "get_llm") as get_llm:
        get_llm.return_value.invoke.return_value = reply
        estimate_prices_batch([ingredient.id])

    db.refresh(ingredient)
    assert ingredient.price_amount == Decimal("5.5")
    assert ingredient.price_unit is Unit.KILOGRAM
    assert ingredient.price_source is PriceSource.ESTIMATED


def test_batch_leaves_a_curated_price_untouched(db: Session) -> None:
    ingredient = crud.create_ingredient(
        session=db,
        ingredient_in=IngredientCreate(name=f"vanilla-{random_lower_string()}"),
    )
    ingredient.price_amount = Decimal("12.00")
    ingredient.price_quantity = 1.0
    ingredient.price_unit = Unit.KILOGRAM
    ingredient.price_source = PriceSource.MANUAL
    db.add(ingredient)
    db.commit()

    with patch.object(llm_module, "get_llm") as get_llm:
        estimate_prices_batch([ingredient.id])
        # Nothing was eligible, so the model is never even consulted.
        get_llm.assert_not_called()

    db.refresh(ingredient)
    assert ingredient.price_amount == Decimal("12.00")
    assert ingredient.price_source is PriceSource.MANUAL


def test_batch_survives_a_failing_model_call(db: Session) -> None:
    """A pricing estimate is a convenience and must never raise at the caller."""
    ingredient = crud.create_ingredient(
        session=db,
        ingredient_in=IngredientCreate(name=f"sorrel-{random_lower_string()}"),
    )
    with patch.object(llm_module, "get_llm", side_effect=RuntimeError("no key")):
        estimate_prices_batch([ingredient.id])

    db.refresh(ingredient)
    assert ingredient.price_amount is None


def test_batch_with_no_ids_does_nothing() -> None:
    with patch.object(llm_module, "get_llm") as get_llm:
        estimate_prices_batch([])
        get_llm.assert_not_called()


def test_batch_ignores_ids_that_do_not_exist() -> None:
    with patch.object(llm_module, "get_llm") as get_llm:
        estimate_prices_batch([uuid.uuid4()])
        get_llm.assert_not_called()
