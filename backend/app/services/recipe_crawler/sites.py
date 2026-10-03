"""The recipe sites the crawler reads, and why each one is (or is not) here.

A site earns a place by meeting all of these, each checked against the live
site when it was added:

1. **robots.txt lets us in.** Every URL still goes through ``robots`` at crawl
   time; this is about the site not fencing off its recipes in the first place.
2. **No published refusal.** A site whose robots.txt, terms or reuse policy
   explicitly forbids scraping, LLM processing or reproducing its recipes is
   left out, even where robots.txt would technically allow the fetch. This is
   a reading of what each site publishes, not legal advice: every site here
   still owns its text and photos (see "Republishing" in ``crawler.py``).
3. **Free to read.** No paywalled or subscriber-only recipes.
4. **A popularity signal we may read.** A page the site itself publishes that
   ranks or features its recipes, and enough ratings per recipe that the count
   itself says how many people cooked it. Never its on-site search: those are
   robots-disallowed everywhere.
5. **schema.org ``aggregateRating`` in the recipe's JSON-LD.** That rating is
   the quality gate (see ``quality.py``); a site without one cannot be judged,
   so it is not crawled.

Left out, and why (as of 2026-10):

- Allrecipes, Serious Eats, Simply Recipes (People Inc.): their robots.txt
  states that scraping, text-and-data mining and any LLM use are prohibited
  without written permission.
- RecipeTin Eats: its "Use of Recipes & Images" policy refuses permission to
  republish ingredients together with directions.
- Food.com: its visitor agreement forbids reproducing its materials without
  written consent.
- Taste of Home: its terms forbid "data mining, robots or similar data
  gathering or extraction methods".
- BBC Good Food: no ``aggregateRating`` in its recipe JSON-LD (the rating only
  lives in page scripts), and it signals ``ai-train=no``.
- Ricardo: its "le meilleur" collection, the one page that curates its best,
  is subscriber-only magazine content.
- CuisineAZ: no page ranks its recipes, and most ratings rest on one or two
  votes, which cannot tell a good recipe from a lucky one.

No English-language site among those checked met all five; the list is meant to
grow as sites are vetted the same way.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class RecipeSite:
    slug: str
    name: str
    #: Language the site writes in; the import keeps it.
    language: str
    #: Pages listing the site's most popular or best recipes, in rank order.
    seed_urls: tuple[str, ...]
    #: Matches the absolute URL of one of the site's recipe pages, and nothing
    #: else it links to (articles, slideshows, categories).
    recipe_url: re.Pattern[str]
    #: Below this average (on a 0–5 scale) a recipe is not imported.
    min_rating: float
    #: Below this many ratings the average is not trusted. Also the weight of
    #: the prior when ranking (see ``quality.score``), so it should sit near
    #: what a well-liked recipe on this site typically collects.
    min_rating_count: int

    @property
    def origin(self) -> str:
        scheme, _, rest = self.seed_urls[0].partition("://")
        return f"{scheme}://{rest.split('/', 1)[0]}"


SITES: tuple[RecipeSite, ...] = (
    # The largest French recipe site. "Top des internautes" is its readers'
    # ranking, about a hundred recipes each rated by thousands.
    RecipeSite(
        slug="marmiton",
        name="Marmiton",
        language="fr",
        seed_urls=("https://www.marmiton.org/recettes/top-internautes.aspx",),
        recipe_url=re.compile(
            r"^https://www\.marmiton\.org/recettes/recette_[\w-]+_\d+\.aspx$"
        ),
        min_rating=4.5,
        min_rating_count=200,
    ),
    # Journal des Femmes Cuisine. Its "all recipes" hub features the site's
    # headline recipes, most of them its "la meilleure recette" references,
    # rated by hundreds of readers.
    RecipeSite(
        slug="journaldesfemmes",
        name="Journal des Femmes Cuisine",
        language="fr",
        seed_urls=("https://cuisine.journaldesfemmes.fr/toutes-les-recettes/",),
        recipe_url=re.compile(
            r"^https://cuisine\.journaldesfemmes\.fr/recette/\d+-[\w-]+$"
        ),
        min_rating=4.5,
        min_rating_count=50,
    ),
    # 750g. No page ranks its recipes, so its course pages are the way in and
    # the rating count is the popularity signal: most recipes there gather a
    # few dozen votes, and only those past fifty are taken.
    RecipeSite(
        slug="750g",
        name="750g",
        language="fr",
        seed_urls=(
            "https://www.750g.com/recettes-plats/",
            "https://www.750g.com/recettes-desserts/",
            "https://www.750g.com/recettes-entrees/",
        ),
        recipe_url=re.compile(r"^https://www\.750g\.com/[\w-]+-r\d+\.htm$"),
        min_rating=4.5,
        min_rating_count=50,
    ),
)
