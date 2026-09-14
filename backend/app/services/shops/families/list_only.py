"""Shops with no digital presence: a farmers' market, a village grocer.

The capability model earns its keep here. This provider declares exactly one
thing — ``LIST_EXPORT`` — and every other part of the stack already knows what
to do with that: the picker shows it alongside Carrefour, the UI hides pricing
and basket controls because the capabilities are absent, and no code anywhere
special-cases "the offline one".

What it does is the part of the job that was always shop-independent: merge
duplicate lines, scale quantities to something a person would write down, and
group by aisle so the list can be read off a phone while walking a market.

Aisle order is configuration, because it is not universal: a market is walked
produce-first, a supermarket is walked the way the supermarket is laid out.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from app.models.ingredient import IngredientCategory, Unit
from app.services.shops.base import ShopProvider
from app.services.shops.matching import merge_lines, prettify_quantity
from app.services.shops.models import (
    Capability,
    ExportedList,
    ExportedListGroup,
    ExportedListItem,
    ListExportFormat,
    ListLine,
    Transport,
)

#: A supermarket walked front to back: fresh, then chilled, then shelves.
SUPERMARKET_AISLES: tuple[IngredientCategory, ...] = (
    IngredientCategory.PRODUCE,
    IngredientCategory.BAKERY,
    IngredientCategory.MEAT,
    IngredientCategory.SEAFOOD,
    IngredientCategory.DAIRY,
    IngredientCategory.FROZEN,
    IngredientCategory.GRAINS,
    IngredientCategory.PANTRY,
    IngredientCategory.SPICES,
    IngredientCategory.BEVERAGES,
    IngredientCategory.OTHER,
)

#: A market is mostly stalls of fresh produce; everything else is an errand
#: afterwards, so the order that saves walking is different.
MARKET_AISLES: tuple[IngredientCategory, ...] = (
    IngredientCategory.PRODUCE,
    IngredientCategory.MEAT,
    IngredientCategory.SEAFOOD,
    IngredientCategory.DAIRY,
    IngredientCategory.BAKERY,
    IngredientCategory.PANTRY,
    IngredientCategory.SPICES,
    IngredientCategory.GRAINS,
    IngredientCategory.BEVERAGES,
    IngredientCategory.FROZEN,
    IngredientCategory.OTHER,
)


@dataclass(frozen=True)
class ListOnlyConfig:
    aisle_order: tuple[IngredientCategory, ...] = field(default=SUPERMARKET_AISLES)
    group_by_aisle: bool = True
    """A single flat list, for somewhere with no aisles worth the name."""


def _format_quantity(quantity: float, unit: Unit) -> str:
    """Render an amount the way a person would write it on paper.

    ``{:g}`` drops a trailing ``.0`` — nobody writes "2.0 onions". ``PIECE`` is
    dropped entirely for the same reason: "2 baguettes", not "2 piece
    baguettes". Every other count unit stays, because "2 bunches" and "1 pinch"
    do carry meaning.
    """
    text = f"{quantity:g}"
    if unit is Unit.PIECE:
        return text
    return f"{text} {unit.value}"


class ListOnlyProvider(ShopProvider):
    """Produces a list to shop from by hand. Contacts nobody."""

    transport = Transport.OFFLINE
    capabilities = frozenset({Capability.LIST_EXPORT})
    requires_store = False

    def __init__(
        self,
        *,
        slug: str,
        display_name: str,
        config: ListOnlyConfig | None = None,
        country: str = "*",
    ) -> None:
        super().__init__(slug=slug, display_name=display_name, country=country)
        self.config = config or ListOnlyConfig()

    def export_list(
        self,
        lines: Sequence[ListLine],
        *,
        export_format: ListExportFormat = ListExportFormat.TEXT,
        category_labels: Mapping[str, str] | None = None,
    ) -> ExportedList:
        merged = merge_lines(lines)
        groups = self._group(merged)
        return ExportedList(
            shop_slug=self.slug,
            shop_name=self.display_name,
            format=export_format,
            groups=groups,
            content=self._render(groups, export_format, category_labels or {}),
            item_count=sum(len(group.items) for group in groups),
            merged_line_count=sum(1 for _, count in merged if count > 1),
        )

    # ----------------------------------------------------------------- #

    def _group(self, merged: Sequence[tuple[ListLine, int]]) -> list[ExportedListGroup]:
        buckets: dict[IngredientCategory, list[ExportedListItem]] = {}
        for line, count in merged:
            quantity, unit = prettify_quantity(line.quantity, line.unit)
            category = (
                (line.category or IngredientCategory.OTHER)
                if self.config.group_by_aisle
                else IngredientCategory.OTHER
            )
            buckets.setdefault(category, []).append(
                ExportedListItem(
                    name=line.name,
                    quantity=quantity,
                    unit=unit,
                    note=line.note,
                    merged_from=count,
                )
            )

        ordered: list[ExportedListGroup] = []
        # Configured aisles first, in walking order; anything the catalogue
        # grew since this list was written still comes out, just at the end.
        seen: set[IngredientCategory] = set()
        for category in self.config.aisle_order:
            if category in buckets:
                seen.add(category)
                ordered.append(
                    ExportedListGroup(
                        category=category,
                        items=sorted(buckets[category], key=lambda i: i.name.lower()),
                    )
                )
        for category in buckets:
            if category not in seen:
                ordered.append(
                    ExportedListGroup(
                        category=category,
                        items=sorted(buckets[category], key=lambda i: i.name.lower()),
                    )
                )
        return ordered

    def _render(
        self,
        groups: Sequence[ExportedListGroup],
        export_format: ListExportFormat,
        labels: Mapping[str, str],
    ) -> str:
        def label(group: ExportedListGroup) -> str:
            return labels.get(group.category.value, group.category.value)

        if export_format is ListExportFormat.CSV:
            buffer = io.StringIO()
            writer = csv.writer(buffer)
            writer.writerow(["category", "item", "quantity", "unit", "note"])
            for group in groups:
                for item in group.items:
                    writer.writerow(
                        [
                            label(group),
                            item.name,
                            f"{item.quantity:g}",
                            item.unit.value,
                            item.note or "",
                        ]
                    )
            return buffer.getvalue()

        bullet = "-" if export_format is ListExportFormat.MARKDOWN else "•"
        lines: list[str] = []
        for group in groups:
            heading = label(group)
            lines.append(
                f"## {heading}"
                if export_format is ListExportFormat.MARKDOWN
                else heading.upper()
            )
            for item in group.items:
                quantity = _format_quantity(item.quantity, item.unit)
                suffix = f" ({item.note})" if item.note else ""
                lines.append(f"{bullet} {quantity} {item.name}{suffix}")
            lines.append("")
        return "\n".join(lines).strip() + "\n" if lines else ""
