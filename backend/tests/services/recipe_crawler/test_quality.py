import re

import pytest

from app.services.recipe_crawler import quality
from app.services.recipe_crawler.sites import SITES, RecipeSite
from tests.services.recipe_crawler.pages import recipe_page

SITE = RecipeSite(
    slug="test",
    name="Test",
    language="fr",
    seed_urls=("https://recipes.example/top",),
    recipe_url=re.compile(r"^https://recipes\.example/recette/\d+$"),
    min_rating=4.5,
    min_rating_count=50,
)


def test_parse_rating_reads_strings_and_scales_to_five() -> None:
    rating = quality.parse_rating(
        {
            "aggregateRating": {
                "ratingValue": "9,2",
                "ratingCount": "80",
                "bestRating": 10,
            }
        }
    )
    assert rating == quality.Rating(value=4.6, count=80)


def test_parse_rating_falls_back_to_review_count() -> None:
    rating = quality.parse_rating(
        {"aggregateRating": {"ratingValue": 4.5, "reviewCount": "258"}}
    )
    assert rating == quality.Rating(value=4.5, count=258)


@pytest.mark.parametrize(
    "raw",
    [
        None,
        {"ratingValue": 4.5},  # nobody voted, or the count is missing
        {"ratingValue": "great", "ratingCount": 10},
        {"ratingValue": 4.5, "ratingCount": 10, "bestRating": 0},
    ],
)
def test_parse_rating_refuses_what_it_cannot_trust(raw: object) -> None:
    assert quality.parse_rating({"aggregateRating": raw}) is None


def test_assess_accepts_a_popular_well_rated_recipe() -> None:
    assessment = quality.assess(recipe_page(rating=4.8, count=1200), SITE)
    assert assessment.qualifies
    assert assessment.title == "Blanquette de veau"
    assert assessment.rating == quality.Rating(value=4.8, count=1200)


def test_assess_finds_the_recipe_inside_a_graph() -> None:
    assert quality.assess(recipe_page(graph=True), SITE).qualifies


@pytest.mark.parametrize(
    ("html", "reason"),
    [
        ("<html><body>No recipe here</body></html>", "no recipe JSON-LD"),
        (recipe_page(ingredients=1), "too few ingredients"),
        (recipe_page(steps=0), "no instructions"),
        (recipe_page(rating=None), "no rating"),
        (recipe_page(count=12), "12 ratings, below 50"),
        (recipe_page(rating=4.2), "rated 4.2, below 4.5"),
    ],
)
def test_assess_rejects_with_a_reason(html: str, reason: str) -> None:
    assessment = quality.assess(html, SITE)
    assert not assessment.qualifies
    assert assessment.rejection == reason


def test_assess_counts_steps_inside_sections() -> None:
    html = recipe_page(steps=0).replace(
        '"recipeInstructions": []',
        '"recipeInstructions": [{"@type": "HowToSection", "itemListElement":'
        ' [{"@type": "HowToStep", "text": "Mix"}]}]',
    )
    assert quality.assess(html, SITE).qualifies


def test_score_prefers_many_votes_over_a_lucky_few() -> None:
    crowd = quality.score(quality.Rating(value=4.8, count=2000), SITE)
    lucky = quality.score(quality.Rating(value=5.0, count=3), SITE)
    assert crowd > lucky


def test_every_site_sets_a_bar_above_the_prior() -> None:
    """A prior above the bar would let few votes lift a recipe's score."""
    for site in SITES:
        assert site.min_rating > quality.PRIOR_RATING, site.slug
        assert site.min_rating_count > 0, site.slug
