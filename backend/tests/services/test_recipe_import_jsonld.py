import json

from bs4 import BeautifulSoup

from app.services.recipe_import import jsonld
from app.services.recipe_import.scraper import extract_page


def _soup(*blocks: object, raw: str = "") -> BeautifulSoup:
    scripts = "".join(
        f'<script type="application/ld+json">{json.dumps(b)}</script>' for b in blocks
    )
    return BeautifulSoup(f"<html><head>{scripts}{raw}</head></html>", "html.parser")


def test_finds_a_recipe_inside_a_graph() -> None:
    soup = _soup(
        {
            "@graph": [
                {"@type": "WebPage"},
                {
                    "@type": ["Recipe", "NewsArticle"],
                    "name": "Tarte",
                    "recipeIngredient": ["x"],
                },
            ]
        }
    )
    recipe = jsonld.find_recipe(soup)
    assert recipe is not None
    assert recipe["name"] == "Tarte"


def test_prefers_a_recipe_with_ingredients_over_a_decoy() -> None:
    soup = _soup(
        {"@type": "Recipe", "name": "Best rated recipes"},
        {"@type": "Recipe", "name": "Brownies", "recipeIngredient": ["chocolate"]},
    )
    recipe = jsonld.find_recipe(soup)
    assert recipe is not None
    assert recipe["name"] == "Brownies"


def test_tolerates_raw_control_characters_and_skips_broken_blocks() -> None:
    raw = (
        '<script type="application/ld+json">{not json</script>'
        '<script type="application/ld+json">'
        '{"@type": "Recipe", "name": "Tatin", "description": "ligne 1\nligne 2",'
        ' "recipeIngredient": ["pommes"]}</script>'
    )
    recipe = jsonld.find_recipe(_soup(raw=raw))
    assert recipe is not None
    assert recipe["description"] == "ligne 1\nligne 2"


def test_extract_page_reads_a_graph_recipe() -> None:
    html = str(
        _soup(
            {
                "@graph": [
                    {
                        "@type": "Recipe",
                        "name": "Tatin",
                        "recipeIngredient": ["pommes"],
                        "recipeInstructions": ["Cuire"],
                    }
                ]
            },
            raw='<meta property="og:image" content="https://img/tatin.jpg">',
        )
    )
    text, image = extract_page(html)
    assert json.loads(text)["title"] == "Tatin"
    assert image == "https://img/tatin.jpg"
