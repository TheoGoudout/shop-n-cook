"""The shared resolution layer. Every shop depends on this being right."""

from decimal import Decimal

import pytest

from app.core.units import UnitDimension, convert, dimension, is_discrete
from app.models.ingredient import Unit
from app.services.shops.matching import (
    MAX_PACK_COUNT,
    compute_pack_count,
    parse_quantity,
    rank_candidates,
    resolve_item,
    score_name,
)
from app.services.shops.models import (
    MatchStatus,
    PackStatus,
    PriceStatus,
    ShopProduct,
)


def test_every_unit_survives_the_pack_maths() -> None:
    """A new ``Unit`` member must not crash pack counting or fall through to a
    silent wrong answer. Conversion itself is ``app.core.units``' job and is
    tested there; this pins that every member reaches this layer intact."""
    for unit in Unit:
        assert convert(1, unit, unit) == 1
        count, status = compute_pack_count(
            required_quantity=2,
            required_unit=unit,
            pack_quantity=1,
            pack_unit=unit,
        )
        assert count == 2
        assert status is PackStatus.EXACT


@pytest.mark.parametrize(
    ("quantity", "source", "target", "expected"),
    [
        (1, Unit.KILOGRAM, Unit.GRAM, 1000.0),
        (500, Unit.GRAM, Unit.KILOGRAM, 0.5),
        (1, Unit.LITER, Unit.MILLILITER, 1000.0),
        (75, Unit.CENTILITER, Unit.MILLILITER, 750.0),
        # US customary, per app.core.units — not the 15 ml round number.
        (2, Unit.TABLESPOON, Unit.MILLILITER, 29.5735295625),
        (1, Unit.POUND, Unit.GRAM, 453.59237),
        (3, Unit.PIECE, Unit.PIECE, 3.0),
    ],
)
def test_convert_within_dimension(
    quantity: float, source: Unit, target: Unit, expected: float
) -> None:
    result = convert(quantity, source, target)
    assert result is not None
    assert result == pytest.approx(expected)


@pytest.mark.parametrize(
    ("source", "target"),
    [
        (Unit.GRAM, Unit.MILLILITER),  # no density table, so no guessing
        (Unit.LITER, Unit.PIECE),
        (Unit.CLOVE, Unit.PIECE),  # a clove is part of a purchasable item
        (Unit.SLICE, Unit.GRAM),
        (Unit.PINCH, Unit.TEASPOON),
        # Every discrete unit stands alone: a bunch of parsley is not "a piece".
        (Unit.BUNCH, Unit.PIECE),
        (Unit.CAN, Unit.PACKAGE),
    ],
)
def test_convert_across_dimensions_returns_none(source: Unit, target: Unit) -> None:
    assert convert(1, source, target) is None


def test_countable_units_are_discrete() -> None:
    for unit in (Unit.CLOVE, Unit.SLICE, Unit.PINCH, Unit.BUNCH, Unit.CAN):
        assert is_discrete(unit)
        assert dimension(unit) is UnitDimension.DISCRETE


class TestPackCount:
    def test_exact_multiple(self) -> None:
        count, status = compute_pack_count(
            required_quantity=500,
            required_unit=Unit.GRAM,
            pack_quantity=250,
            pack_unit=Unit.GRAM,
        )
        assert (count, status) == (2, PackStatus.EXACT)

    def test_rounds_up_partial_packs(self) -> None:
        count, status = compute_pack_count(
            required_quantity=300,
            required_unit=Unit.GRAM,
            pack_quantity=250,
            pack_unit=Unit.GRAM,
        )
        assert (count, status) == (2, PackStatus.ROUNDED_UP)

    def test_small_amount_still_buys_one(self) -> None:
        count, status = compute_pack_count(
            required_quantity=2,
            required_unit=Unit.TABLESPOON,
            pack_quantity=1,
            pack_unit=Unit.LITER,
        )
        assert (count, status) == (1, PackStatus.ROUNDED_UP)

    def test_cloves_never_multiply_the_basket(self) -> None:
        """3 cloves of garlic must not become 3 heads of garlic."""
        count, status = compute_pack_count(
            required_quantity=3,
            required_unit=Unit.CLOVE,
            pack_quantity=1,
            pack_unit=Unit.PIECE,
        )
        assert (count, status) == (1, PackStatus.ASSUMED_SINGLE)

    def test_incompatible_dimensions_assume_single(self) -> None:
        count, status = compute_pack_count(
            required_quantity=200,
            required_unit=Unit.GRAM,
            pack_quantity=500,
            pack_unit=Unit.MILLILITER,
        )
        assert (count, status) == (1, PackStatus.ASSUMED_SINGLE)

    def test_unknown_pack_size(self) -> None:
        count, status = compute_pack_count(
            required_quantity=200,
            required_unit=Unit.GRAM,
            pack_quantity=None,
            pack_unit=None,
        )
        assert (count, status) == (1, PackStatus.UNKNOWN_PACK_SIZE)

    def test_pack_maths_uses_the_shared_unit_table(self) -> None:
        """67 tbsp is 990 ml by US customary measure, so one 1 L bottle is
        enough. The old local table rounded a tablespoon to 15 ml and would
        have sent the shopper back for a second one."""
        count, _ = compute_pack_count(
            required_quantity=67,
            required_unit=Unit.TABLESPOON,
            pack_quantity=1,
            pack_unit=Unit.LITER,
        )
        assert count == 1

    def test_absurd_ratio_is_capped(self) -> None:
        count, status = compute_pack_count(
            required_quantity=10,
            required_unit=Unit.KILOGRAM,
            pack_quantity=1,
            pack_unit=Unit.GRAM,
        )
        assert (count, status) == (MAX_PACK_COUNT, PackStatus.UNKNOWN_PACK_SIZE)


class TestScoring:
    def test_plural_and_accents_do_not_matter(self) -> None:
        assert score_name("tomates", "Tomate grappe") > 0.5
        assert score_name("crème fraîche", "Creme fraiche epaisse") > 0.5

    def test_extra_packaging_words_do_not_sink_a_match(self) -> None:
        assert (
            score_name("tomates cerises", "Tomates cerises rouges barquette 250g") > 0.6
        )

    def test_unrelated_product_scores_low(self) -> None:
        assert score_name("tomates cerises", "Lessive liquide 3L") < 0.3

    def test_out_of_stock_loses_ties(self) -> None:
        available = ShopProduct(sku="a", name="Lait demi-écrémé 1L", in_stock=True)
        sold_out = ShopProduct(sku="b", name="Lait demi-écrémé 1L", in_stock=False)
        ranked = rank_candidates("lait demi-écrémé", [sold_out, available])
        assert ranked[0][0].sku == "a"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Tomates cerises prix bas 250g", (250.0, Unit.GRAM)),
        ("Mélange de tomates anciennes 1,5kg", (1.5, Unit.KILOGRAM)),
        ("Lait demi-écrémé 1 L", (1.0, Unit.LITER)),
        ("Yaourt nature 6 x 125 g", (750.0, Unit.GRAM)),
        ("Huile d'olive vierge extra 75 cl", (75.0, Unit.CENTILITER)),
        ("Tomates rondes en grappe environ 3-4 fruits", None),
        ("Filières Responsables Auchan", None),
    ],
)
def test_parse_quantity(text: str, expected: tuple[float, Unit] | None) -> None:
    assert parse_quantity(text) == expected


class TestResolveItem:
    def test_matches_and_prices(self) -> None:
        product = ShopProduct(
            sku="A1",
            name="Tomates cerises rouges 250g",
            price=Decimal("2.49"),
            pack_quantity=250,
            pack_unit=Unit.GRAM,
        )
        resolved = resolve_item(
            item_name="tomates cerises",
            quantity=500,
            unit=Unit.GRAM,
            candidates=[product],
        )
        assert resolved.match_status is MatchStatus.MATCHED
        assert resolved.pack_count == 2
        assert resolved.price_status is PriceStatus.PRICED
        assert resolved.line_total == Decimal("4.98")

    def test_no_candidates(self) -> None:
        resolved = resolve_item(
            item_name="zeste de yuzu", quantity=1, unit=Unit.PIECE, candidates=[]
        )
        assert resolved.match_status is MatchStatus.NO_CANDIDATES
        assert resolved.product is None

    def test_irrelevant_candidates_are_not_forced_into_a_match(self) -> None:
        resolved = resolve_item(
            item_name="zeste de yuzu",
            quantity=1,
            unit=Unit.PIECE,
            candidates=[ShopProduct(sku="x", name="Lessive liquide 3L")],
        )
        assert resolved.match_status is MatchStatus.NO_CANDIDATES
        assert resolved.product is None
        assert resolved.alternatives  # still offered, just not chosen

    def test_unpriced_reason_is_carried_through(self) -> None:
        resolved = resolve_item(
            item_name="tomates",
            quantity=1,
            unit=Unit.KILOGRAM,
            candidates=[ShopProduct(sku="A1", name="Tomates grappe 1kg")],
            unpriced_reason=PriceStatus.REQUIRES_STORE,
        )
        assert resolved.price_status is PriceStatus.REQUIRES_STORE
        assert resolved.line_total is None
