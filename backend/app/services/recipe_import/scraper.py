"""HTTP fetch + HTML/JSON-LD extraction of recipe content from a URL."""

from __future__ import annotations

import ipaddress
import json
import socket
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup


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
    soup = BeautifulSoup(response.text, "html.parser")

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
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except Exception:
            continue

        # Handle list or single object
        items = data if isinstance(data, list) else [data]

        for item in items:
            if not isinstance(item, dict):
                continue

            if item.get("@type") in ("Recipe", ["Recipe"]):
                # Extract only relevant fields
                extracted = {
                    "title": item.get("name"),
                    "description": item.get("description"),
                    "ingredients": item.get("recipeIngredient"),
                    "instructions": item.get("recipeInstructions"),
                }
                return json.dumps(extracted), image_url

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
