"""HTTP fetch + HTML/JSON-LD extraction of recipe content from a URL."""

from __future__ import annotations

import ipaddress
import json
import socket
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.services.recipe_import import jsonld


def _validate_url_is_public(url: str) -> None:
    """Raise ValueError if the URL resolves to a private/internal address (SSRF guard)."""
    hostname = urlparse(url).hostname
    if not hostname:
        raise ValueError("Invalid URL: missing hostname")
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise ValueError(f"Could not resolve hostname '{hostname}'") from exc
    for info in infos:
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
        ):
            raise ValueError(
                "Requests to private or reserved addresses are not allowed"
            )


#: What the model is handed from a JSON-LD ``Recipe``: our key → schema.org key.
#: Everything the page states is passed on, so the model reads servings, times
#: and the rest instead of guessing them, and reads them the same way each time.
_JSONLD_FIELDS = {
    "title": "name",
    "description": "description",
    "yield": "recipeYield",
    "prep_time": "prepTime",
    "cook_time": "cookTime",
    "total_time": "totalTime",
    "category": "recipeCategory",
    "cuisine": "recipeCuisine",
    "keywords": "keywords",
    "suitable_for_diet": "suitableForDiet",
    "ingredients": "recipeIngredient",
    "instructions": "recipeInstructions",
}


def _jsonld_fields(recipe: dict[str, Any]) -> dict[str, Any]:
    """The parts of a JSON-LD ``Recipe`` the model needs, without empty ones."""
    extracted = {key: recipe.get(source) for key, source in _JSONLD_FIELDS.items()}
    nutrition = recipe.get("nutrition")
    if isinstance(nutrition, dict):
        extracted["calories"] = nutrition.get("calories")
    return {
        key: value for key, value in extracted.items() if value not in (None, "", [])
    }


def fetch_page(url: str) -> tuple[str, str | None]:
    """Fetch a URL and return (focused recipe text, og:image URL or None)."""
    _validate_url_is_public(url)
    response = httpx.get(
        url,
        timeout=15,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0 (compatible; recipe-importer/1.0)"},
    )
    response.raise_for_status()
    return extract_page(response.text)


def extract_page(html: str) -> tuple[str, str | None]:
    """Reduce a recipe page's HTML to (focused recipe text, og:image URL or None).

    Split from ``fetch_page`` so a caller that already holds the page — the
    recipe crawler reads it first to judge its rating — need not fetch it twice.
    """
    soup = BeautifulSoup(html, "html.parser")

    # --- Extract image ---
    image_url: str | None = None
    for meta in soup.find_all("meta"):
        prop = meta.get("property", "") or meta.get("name", "")
        if prop in ("og:image", "twitter:image"):
            content = str(meta.get("content") or "").strip()
            if content:
                image_url = content
                break

    # --- 1. Try JSON-LD (best quality, lowest tokens) ---
    recipe = jsonld.find_recipe(soup)
    if recipe is not None:
        return json.dumps(_jsonld_fields(recipe), ensure_ascii=False), image_url

    # --- 2. Targeted HTML extraction ---
    def find_section(keywords: list[str]) -> str:
        for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5"]):
            text = tag.get_text(strip=True).lower()
            if any(k in text for k in keywords):
                content = []
                for sib in tag.find_next_siblings():
                    if sib.name and sib.name.startswith("h"):
                        break
                    content.append(sib.get_text(" ", strip=True))
                return "\n".join(content)
        return ""

    ingredients_text = find_section(["ingredient"])
    instructions_text = find_section(["instruction", "direction", "method"])

    combined = f"""
TITLE:
{soup.title.string if soup.title else ""}

INGREDIENTS:
{ingredients_text}

INSTRUCTIONS:
{instructions_text}
    """.strip()

    if len(combined) > 300:
        return combined[:5000], image_url

    # --- 3. Fallback (clean + trimmed full text) ---
    for tag in soup(
        ["script", "style", "nav", "footer", "aside", "header", "noscript"]
    ):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)

    return text[:4000], image_url
