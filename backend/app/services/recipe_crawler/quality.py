"""Decide whether a recipe page is good enough to import, and rank the ones that are.

"Good" is read from what the site's own readers said: the schema.org
``aggregateRating`` in the recipe's JSON-LD. A recipe must clear the site's
minimum average *and* minimum number of ratings, and must be complete enough to
cook from. The ones that pass are ranked by a Bayesian average, so that 4.9
from three votes does not outrank 4.8 from two thousand.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from bs4 import BeautifulSoup

from app.services.recipe_crawler.sites import RecipeSite
from app.services.recipe_import import jsonld

#: The average a recipe is assumed to have before any rating is counted. Below
#: every site's ``min_rating``, so few votes pull a score down, not up.
PRIOR_RATING = 4.0
#: Fewer ingredients than this is a stub or a page whose JSON-LD is broken. Two
#: is enough for a real recipe: Marmiton's top-rated meringue is egg whites and
#: sugar.
MIN_INGREDIENTS = 2


@dataclass(frozen=True)
class Rating:
    #: Normalised to a 0–5 scale whatever the site's ``bestRating``.
    value: float
    count: int


@dataclass(frozen=True)
class Assessment:
    title: str | None
    rating: Rating | None
    #: ``None`` when the recipe qualifies; otherwise why it does not.
    rejection: str | None

    @property
    def qualifies(self) -> bool:
        return self.rejection is None


def _number(raw: Any) -> float | None:
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int | float):
        return float(raw)
    if isinstance(raw, str):
        try:
            return float(raw.strip().replace(",", "."))
        except ValueError:
            return None
    return None


def parse_rating(recipe: dict[str, Any]) -> Rating | None:
    raw = recipe.get("aggregateRating")
    if isinstance(raw, list):
        raw = raw[0] if raw else None
    if not isinstance(raw, dict):
        return None
    value = _number(raw.get("ratingValue"))
    count = _number(raw.get("ratingCount"))
    if count is None:
        count = _number(raw.get("reviewCount"))
    if value is None or count is None:
        return None
    best = _number(raw.get("bestRating"))
    if best is None:
        best = 5.0
    if best <= 0:
        return None
    return Rating(value=round(value / best * 5.0, 2), count=int(count))


def _step_count(instructions: Any) -> int:
    if isinstance(instructions, str):
        return 1 if instructions.strip() else 0
    if isinstance(instructions, list):
        return sum(
            # A HowToSection groups its own steps.
            _step_count(item.get("itemListElement"))
            if isinstance(item, dict) and "itemListElement" in item
            else 1
            for item in instructions
        )
    return 0


def assess(html: str, site: RecipeSite) -> Assessment:
    recipe = jsonld.find_recipe(BeautifulSoup(html, "html.parser"))
    if recipe is None:
        return Assessment(title=None, rating=None, rejection="no recipe JSON-LD")

    name = recipe.get("name")
    title = name.strip()[:255] if isinstance(name, str) else None
    rating = parse_rating(recipe)

    def reject(reason: str) -> Assessment:
        return Assessment(title=title, rating=rating, rejection=reason)

    ingredients = recipe.get("recipeIngredient") or []
    if not isinstance(ingredients, list) or len(ingredients) < MIN_INGREDIENTS:
        return reject("too few ingredients")
    if _step_count(recipe.get("recipeInstructions")) == 0:
        return reject("no instructions")
    if rating is None:
        return reject("no rating")
    if rating.count < site.min_rating_count:
        return reject(f"{rating.count} ratings, below {site.min_rating_count}")
    if rating.value < site.min_rating:
        return reject(f"rated {rating.value:g}, below {site.min_rating:g}")
    return Assessment(title=title, rating=rating, rejection=None)


def score(rating: Rating, site: RecipeSite) -> float:
    """Bayesian average: the rating, shrunk towards ``PRIOR_RATING`` by as many
    phantom votes as the site's ``min_rating_count``."""
    weight = site.min_rating_count
    return (PRIOR_RATING * weight + rating.value * rating.count) / (
        weight + rating.count
    )
