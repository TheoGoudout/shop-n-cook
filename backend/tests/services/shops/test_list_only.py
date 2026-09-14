"""The shop that contacts nobody.

Worth testing hard because it is the fallback every other shop degrades
towards: whatever else fails, the user should still get a list they can carry.
"""

import pytest

from app.models.ingredient import IngredientCategory, Unit
from app.services.shops.errors import CapabilityNotSupportedError
from app.services.shops.families.list_only import (
    MARKET_AISLES,
    SUPERMARKET_AISLES,
    ListOnlyConfig,
    ListOnlyProvider,
)
from app.services.shops.matching import merge_lines, prettify_quantity
from app.services.shops.models import (
    Capability,
    ListExportFormat,
    ListLine,
    Transport,
)
from app.services.shops.orchestrator import export_shopping_list
from app.services.shops.registry import ANY_COUNTRY, get_provider, iter_providers

LINES = [
    ListLine(
        name="Oignons", quantity=200, unit=Unit.GRAM, category=IngredientCategory.PRODUCE
    ),
    ListLine(
        name="oignon",
        quantity=1.3,
        unit=Unit.KILOGRAM,
        category=IngredientCategory.PRODUCE,
    ),
    ListLine(
        name="Bavette",
        quantity=600,
        unit=Unit.GRAM,
        category=IngredientCategory.MEAT,
        note="chez Marcel",
    ),
    ListLine(
        name="Baguette",
        quantity=2,
        unit=Unit.PIECE,
        category=IngredientCategory.BAKERY,
    ),
    ListLine(name="Herbes", quantity=1, unit=Unit.PINCH),
]


def _market() -> ListOnlyProvider:
    return ListOnlyProvider(
        slug="market",
        display_name="Market",
        config=ListOnlyConfig(aisle_order=MARKET_AISLES),
    )


class TestMerging:
    def test_plurals_of_the_same_ingredient_collapse(self) -> None:
        merged = merge_lines(LINES)
        onions = [line for line, _ in merged if line.name.lower().startswith("oignon")]
        assert len(onions) == 1
        assert onions[0].quantity == pytest.approx(1500)

    def test_merge_count_is_reported(self) -> None:
        counts = {line.name: count for line, count in merge_lines(LINES)}
        assert counts["Oignons"] == 2
        assert counts["Bavette"] == 1

    def test_incompatible_units_stay_separate(self) -> None:
        """"2 cloves" and "1 bulb" are both true; adding them is not."""
        merged = merge_lines(
            [
                ListLine(name="ail", quantity=2, unit=Unit.CLOVE),
                ListLine(name="ail", quantity=1, unit=Unit.PIECE),
            ]
        )
        assert len(merged) == 2

    def test_a_category_from_either_side_survives(self) -> None:
        merged = merge_lines(
            [
                ListLine(name="poireaux", quantity=1, unit=Unit.KILOGRAM),
                ListLine(
                    name="poireau",
                    quantity=500,
                    unit=Unit.GRAM,
                    category=IngredientCategory.PRODUCE,
                ),
            ]
        )
        assert merged[0][0].category is IngredientCategory.PRODUCE

    def test_names_made_only_of_stopwords_do_not_all_collide(self) -> None:
        merged = merge_lines(
            [
                ListLine(name="de", quantity=1, unit=Unit.PIECE),
                ListLine(name="la", quantity=1, unit=Unit.PIECE),
            ]
        )
        assert len(merged) == 2


@pytest.mark.parametrize(
    ("quantity", "unit", "expected"),
    [
        (1500, Unit.GRAM, (1.5, Unit.KILOGRAM)),
        (999, Unit.GRAM, (999.0, Unit.GRAM)),
        (2000, Unit.MILLILITER, (2.0, Unit.LITER)),
        (250, Unit.CENTILITER, (2.5, Unit.LITER)),
        (3, Unit.PIECE, (3.0, Unit.PIECE)),
    ],
)
def test_prettify_quantity(
    quantity: float, unit: Unit, expected: tuple[float, Unit]
) -> None:
    assert prettify_quantity(quantity, unit) == expected


class TestExport:
    def test_declares_only_list_export(self) -> None:
        provider = _market()
        assert provider.capabilities == frozenset({Capability.LIST_EXPORT})
        assert provider.transport is Transport.OFFLINE
        assert not provider.supports(Capability.SEARCH)
        assert not provider.supports(Capability.PRICES)

    def test_groups_follow_the_configured_walking_order(self) -> None:
        exported = _market().export_list(LINES)
        categories = [group.category for group in exported.groups]
        assert categories.index(IngredientCategory.MEAT) < categories.index(
            IngredientCategory.BAKERY
        ), "a market is walked meat-before-bakery"

    def test_supermarket_order_differs(self) -> None:
        provider = ListOnlyProvider(
            slug="p",
            display_name="P",
            config=ListOnlyConfig(aisle_order=SUPERMARKET_AISLES),
        )
        categories = [group.category for group in provider.export_list(LINES).groups]
        assert categories.index(IngredientCategory.BAKERY) < categories.index(
            IngredientCategory.MEAT
        )

    def test_uncategorised_items_land_in_other(self) -> None:
        exported = _market().export_list(LINES)
        other = next(
            g for g in exported.groups if g.category is IngredientCategory.OTHER
        )
        assert [item.name for item in other.items] == ["Herbes"]

    def test_counts_reflect_the_merge(self) -> None:
        exported = _market().export_list(LINES)
        assert exported.item_count == 4, "five lines, two of them the same onion"
        assert exported.merged_line_count == 1

    def test_notes_reach_the_printed_list(self) -> None:
        exported = _market().export_list(LINES)
        assert "chez Marcel" in exported.content

    def test_piece_is_not_spelled_out(self) -> None:
        content = _market().export_list(LINES).content
        assert "2 Baguette" in content
        assert "2 piece" not in content

    def test_quantities_are_scaled_for_reading(self) -> None:
        assert "1.5 kg Oignons" in _market().export_list(LINES).content

    def test_markdown_uses_headings_and_dashes(self) -> None:
        content = _market().export_list(
            LINES, export_format=ListExportFormat.MARKDOWN
        ).content
        assert content.startswith("## ")
        assert "- 1.5 kg Oignons" in content

    def test_csv_is_parseable_with_a_header(self) -> None:
        import csv
        import io

        content = _market().export_list(
            LINES, export_format=ListExportFormat.CSV
        ).content
        rows = list(csv.reader(io.StringIO(content)))
        assert rows[0] == ["category", "item", "quantity", "unit", "note"]
        assert len(rows) == 5
        assert any(row[4] == "chez Marcel" for row in rows[1:])

    def test_labels_translate_the_rendered_headings(self) -> None:
        exported = _market().export_list(
            LINES, category_labels={"produce": "Primeur", "meat": "Boucher"}
        )
        assert "PRIMEUR" in exported.content
        assert "BOUCHER" in exported.content
        # The structured form stays untranslated so the client can localise it.
        assert exported.groups[0].category is IngredientCategory.PRODUCE

    def test_flat_mode_skips_grouping(self) -> None:
        provider = ListOnlyProvider(
            slug="flat",
            display_name="Flat",
            config=ListOnlyConfig(group_by_aisle=False),
        )
        exported = provider.export_list(LINES)
        assert len(exported.groups) == 1
        assert exported.groups[0].category is IngredientCategory.OTHER

    def test_empty_list_renders_empty(self) -> None:
        exported = _market().export_list([])
        assert exported.groups == []
        assert exported.content == ""
        assert exported.item_count == 0


class TestRegistration:
    def test_list_only_shops_serve_every_country(self) -> None:
        """A list you carry needs no local presence, so it must not be
        filtered out of any country's picker."""
        for slug in ("market", "printable"):
            assert get_provider(slug).country == ANY_COUNTRY
        for country in ("FR", "BE", "ZZ"):
            slugs = {p.slug for p in iter_providers(country=country)}
            assert {"market", "printable"} <= slugs

    def test_export_on_a_shop_that_cannot_is_refused(self) -> None:
        with pytest.raises(CapabilityNotSupportedError):
            export_shopping_list(provider=get_provider("carrefour"), lines=LINES)

    def test_orchestrator_passes_format_and_labels_through(self) -> None:
        exported = export_shopping_list(
            provider=get_provider("market"),
            lines=LINES,
            export_format=ListExportFormat.CSV,
            category_labels={"meat": "Boucher"},
        )
        assert exported.format is ListExportFormat.CSV
        assert "Boucher" in exported.content
