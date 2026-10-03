import json

from app.services.recipe_crawler import discovery
from tests.services.recipe_crawler.test_quality import SITE


def test_recipe_links_keep_page_order_and_drop_everything_else() -> None:
    html = (
        '<a href="/recette/3?utm_source=x#avis">a</a>'
        '<a href="https://recipes.example/article/1">article</a>'
        '<a href="https://RECIPES.example/recette/1">b</a>'
        '<a href="/recette/3">duplicate</a>'
        '<a href="https://elsewhere.example/recette/2">other site</a>'
        "<a>no href</a>"
    )
    links = discovery.recipe_links(
        html, page_url="https://recipes.example/top", site=SITE
    )
    assert links == [
        "https://recipes.example/recette/3",
        "https://recipes.example/recette/1",
    ]


def test_recipe_links_put_an_item_list_ranking_first() -> None:
    item_list = {
        "@type": "ItemList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": 1,
                "url": "https://recipes.example/recette/9",
            },
            {"@type": "ListItem", "position": 2, "item": {"@id": "/recette/8"}},
        ],
    }
    html = (
        '<a href="/recette/1">first link</a>'
        f'<script type="application/ld+json">{json.dumps(item_list)}</script>'
    )
    links = discovery.recipe_links(
        html, page_url="https://recipes.example/top", site=SITE
    )
    assert links == [
        "https://recipes.example/recette/9",
        "https://recipes.example/recette/8",
        "https://recipes.example/recette/1",
    ]


def test_canonical_url_uses_the_page_canonical_on_the_same_site() -> None:
    html = '<link rel="canonical" href="https://recipes.example/recette/7?x=1">'
    assert (
        discovery.canonical_url(
            html, fetched_url="https://recipes.example/recette/70", site=SITE
        )
        == "https://recipes.example/recette/7"
    )


def test_canonical_url_ignores_a_canonical_that_is_not_a_recipe_page() -> None:
    html = '<link rel="canonical" href="https://recipes.example/">'
    assert (
        discovery.canonical_url(
            html, fetched_url="https://recipes.example/recette/7#top", site=SITE
        )
        == "https://recipes.example/recette/7"
    )
