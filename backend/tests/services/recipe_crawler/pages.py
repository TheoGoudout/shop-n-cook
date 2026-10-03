"""HTML fixtures shaped like the crawled sites' pages."""

import json
from typing import Any


def recipe_page(
    name: str = "Blanquette de veau",
    *,
    rating: float | str | None = 4.8,
    count: int | str | None = 1200,
    count_key: str = "ratingCount",
    best: float | str | None = None,
    ingredients: int = 5,
    steps: int = 3,
    canonical: str | None = None,
    graph: bool = False,
) -> str:
    recipe: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "Recipe",
        "name": name,
        "recipeIngredient": [f"{i + 1} ingrédient" for i in range(ingredients)],
        "recipeInstructions": [
            {"@type": "HowToStep", "text": f"Étape {i + 1}"} for i in range(steps)
        ],
    }
    if rating is not None:
        recipe["aggregateRating"] = {"@type": "AggregateRating", "ratingValue": rating}
        if count is not None:
            recipe["aggregateRating"][count_key] = count
        if best is not None:
            recipe["aggregateRating"]["bestRating"] = best
    data: Any = (
        {"@context": "https://schema.org", "@graph": [recipe]} if graph else recipe
    )
    head = f'<link rel="canonical" href="{canonical}">' if canonical else ""
    return (
        f'<html><head>{head}<meta property="og:image" content="https://img/x.jpg">'
        f'<script type="application/ld+json">{json.dumps(data)}</script>'
        f"</head><body><h1>{name}</h1></body></html>"
    )


def listing_page(*hrefs: str) -> str:
    links = "".join(f'<a href="{href}">recette</a>' for href in hrefs)
    return f"<html><body>{links}</body></html>"
