"""Find the schema.org ``Recipe`` a page publishes as JSON-LD.

Recipe sites all publish one, because search engines reward it, but each nests
it differently: a bare object, a list, an ``@graph`` (Yoast-style), or the
``mainEntity`` of a ``WebPage``. Some also emit raw control characters inside
strings (750g puts literal newlines in its descriptions), which strict JSON
rejects, so parsing is lenient.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

from bs4 import BeautifulSoup

#: Keys under which a node nests further nodes worth visiting.
_NESTING_KEYS = ("@graph", "mainEntity", "itemListElement")


def iter_jsonld_nodes(soup: BeautifulSoup) -> Iterator[dict[str, Any]]:
    """Every JSON-LD object on the page, nested ones included."""
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "", strict=False)
        except ValueError:
            continue
        yield from _walk(data)


def _walk(node: Any) -> Iterator[dict[str, Any]]:
    if isinstance(node, list):
        for item in node:
            yield from _walk(item)
    elif isinstance(node, dict):
        yield node
        for key in _NESTING_KEYS:
            if key in node:
                yield from _walk(node[key])


def has_type(node: dict[str, Any], type_name: str) -> bool:
    """``@type`` may be a string or a list of strings."""
    declared = node.get("@type")
    if isinstance(declared, list):
        return type_name in declared
    return declared == type_name


def find_recipe(soup: BeautifulSoup) -> dict[str, Any] | None:
    """The first JSON-LD ``Recipe`` that lists ingredients, or ``None``.

    Requiring ingredients skips the decoy ``Recipe`` some collection pages
    declare for themselves (BBC Good Food types its "most popular" listing as
    one).
    """
    fallback: dict[str, Any] | None = None
    for node in iter_jsonld_nodes(soup):
        if not has_type(node, "Recipe"):
            continue
        if node.get("recipeIngredient"):
            return node
        fallback = fallback or node
    return fallback
