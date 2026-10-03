"""Find recipe URLs on a site's popularity pages, and name each page canonically."""

from __future__ import annotations

from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from app.services.recipe_crawler.sites import RecipeSite
from app.services.recipe_import import jsonld


def normalize_url(url: str) -> str:
    """Scheme and host lower-cased; query string and fragment dropped.

    Recipe sites hang tracking parameters and anchors off the same page
    (``?utm_source=…``, ``#comments``); none of the four sites uses the query
    string to tell one recipe from another.
    """
    parts = urlsplit(url.strip())
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), parts.path or "/", "", "")
    )


def recipe_links(html: str, *, page_url: str, site: RecipeSite) -> list[str]:
    """Recipe URLs a listing page links to, in page order, each once.

    Page order matters: these pages rank their recipes, and the crawler reads
    them top-down. A JSON-LD ``ItemList`` (Ricardo publishes one) states that
    ranking explicitly, so its entries come first.
    """
    soup = BeautifulSoup(html, "html.parser")
    hrefs: list[str] = []
    for node in jsonld.iter_jsonld_nodes(soup):
        if jsonld.has_type(node, "ListItem"):
            url = node.get("url") or node.get("item")
            if isinstance(url, dict):
                url = url.get("@id") or url.get("url")
            if isinstance(url, str):
                hrefs.append(url)
    hrefs.extend(str(a.get("href") or "") for a in soup.find_all("a"))

    seen: set[str] = set()
    links: list[str] = []
    for href in hrefs:
        if not href:
            continue
        url = normalize_url(urljoin(page_url, href))
        if url in seen or not site.recipe_url.match(url):
            continue
        seen.add(url)
        links.append(url)
    return links


def canonical_url(html: str, *, fetched_url: str, site: RecipeSite) -> str:
    """The page's ``rel=canonical``, when it is one of this site's recipe URLs.

    The same recipe is often reachable under several URLs (a renamed slug that
    still resolves, a print view); the canonical one is what the site considers
    *the* page, so it is the key the crawler remembers it by.
    """
    soup = BeautifulSoup(html, "html.parser")
    for link in soup.find_all("link"):
        rel = link.get("rel")
        rels: list[str] = (
            [str(r) for r in rel] if isinstance(rel, list) else str(rel or "").split()
        )
        if "canonical" not in [r.lower() for r in rels]:
            continue
        href = str(link.get("href") or "")
        if href:
            url = normalize_url(urljoin(fetched_url, href))
            if site.recipe_url.match(url):
                return url
    return normalize_url(fetched_url)
