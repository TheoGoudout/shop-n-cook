"""One crawler pass against a fake recipe site, on the real database.

What matters most here is the crawler's memory: a recipe imported once is
never imported again, and a page judged once is not re-read every day.
"""

import json
import re
import uuid
from collections.abc import Generator
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from sqlmodel import Session, select

from app.core.config import settings
from app.models import CrawledRecipe, CrawlStatus, Recipe, RecipeCrawlRun, User
from app.services.recipe_crawler import crawler
from app.services.recipe_crawler.sites import RecipeSite
from app.services.store_providers.errors import ProviderUnavailableError
from app.services.store_providers.families.http_client import FetchedPage
from tests.services.recipe_crawler.pages import listing_page, recipe_page

FETCH = "app.services.store_providers.families.http_client.fetch"
GET_LLM = "app.services.recipe_import.llm.get_llm"


def _site(slug: str | None = None) -> RecipeSite:
    """A site on its own random host, so tests never share URLs."""
    host = f"{slug or uuid.uuid4().hex[:10]}.example"
    return RecipeSite(
        slug=host.split(".")[0],
        name=host,
        language="fr",
        seed_urls=(f"https://{host}/top",),
        recipe_url=re.compile(rf"^https://{re.escape(host)}/recette/\d+$"),
        min_rating=4.5,
        min_rating_count=50,
    )


@dataclass
class FakeWeb:
    pages: dict[str, tuple[int, str]] = field(default_factory=dict)
    requested: list[str] = field(default_factory=list)
    down: set[str] = field(default_factory=set)

    def add_site(
        self, site: RecipeSite, recipes: dict[int, str], robots: str = ""
    ) -> None:
        self.pages[f"{site.origin}/robots.txt"] = (200, robots or "User-agent: *\n")
        self.pages[site.seed_urls[0]] = (
            200,
            listing_page(*(f"/recette/{n}" for n in recipes)),
        )
        for n, html in recipes.items():
            self.pages[f"{site.origin}/recette/{n}"] = (200, html)

    def fetch(self, url: str, **_: Any) -> FetchedPage:
        if any(url.startswith(origin) for origin in self.down):
            raise ProviderUnavailableError(f"{url} could not be reached")
        self.requested.append(url)
        status, text = self.pages.get(url, (404, "Not found"))
        return FetchedPage(status_code=status, text=text)

    def recipe_requests(self) -> list[str]:
        return [u for u in self.requested if "/recette/" in u]


def _llm_reply(title: str = "Blanquette de veau") -> MagicMock:
    llm = MagicMock()
    llm.invoke.return_value.content = json.dumps(
        {
            "title": title,
            "description": "Un classique.",
            "servings": 4,
            "ingredients": [
                {"name": "veau", "quantity": 800, "unit": "g", "category": "meat"},
                {"name": "carotte", "quantity": 2, "unit": "piece"},
                {"name": "sel", "quantity": 0, "unit": "pinch"},
            ],
            "steps": [
                {"instruction": "Couper le veau.", "ingredient_names": ["veau"]},
                {"instruction": "Saler.", "ingredient_names": ["sel"]},
            ],
        }
    )
    return llm


@pytest.fixture
def web() -> Generator[FakeWeb, None, None]:
    fake = FakeWeb()
    with patch(FETCH, side_effect=fake.fetch):
        yield fake


@pytest.fixture(autouse=True)
def llm() -> Generator[MagicMock, None, None]:
    """The model, answering with one valid recipe. Tests that need no model
    still get it, so none can reach a real provider."""
    reply = _llm_reply()
    with patch(GET_LLM, return_value=reply):
        yield reply


def _crawl(db: Session, *sites: RecipeSite, **kwargs: Any) -> crawler.CrawlReport:
    options: dict[str, Any] = {
        "max_imports": 10,
        "max_pages_per_site": 20,
        "delay_seconds": 0,
    }
    options.update(kwargs)
    return crawler.crawl(db, sites=sites, **options)


def _row(db: Session, url: str) -> CrawledRecipe | None:
    db.expire_all()
    return db.exec(select(CrawledRecipe).where(CrawledRecipe.url == url)).first()


def test_imports_a_good_recipe_as_a_public_recipe_of_the_crawler(
    db: Session, web: FakeWeb, llm: MagicMock
) -> None:
    site = _site()
    web.add_site(site, {1: recipe_page(rating=4.8, count=900)})
    url = f"{site.origin}/recette/1"

    report = _crawl(db, site)

    assert [o.url for o in report.with_status(CrawlStatus.IMPORTED)] == [url]
    row = _row(db, url)
    assert row is not None
    assert row.status == CrawlStatus.IMPORTED
    assert (row.rating_value, row.rating_count) == (4.8, 900)
    recipe = db.get(Recipe, row.recipe_id)
    assert recipe is not None
    assert recipe.is_public
    assert recipe.source_url == url
    assert recipe.image_url == "https://img/x.jpg"
    # The zero-quantity "sel" is dropped rather than failing the import.
    assert [ri.ingredient_name for ri in recipe.recipe_ingredients] == [
        "veau",
        "carotte",
    ]
    owner = db.get(User, recipe.owner_id)
    assert owner is not None
    assert owner.email == settings.RECIPE_CRAWL_OWNER_EMAIL
    assert not owner.is_active, "the crawler's account must never log in"
    # The page was read in the language of the site.
    system_prompt = llm.invoke.call_args.args[0][0].content
    assert "French" in system_prompt
    assert recipe.import_language == "fr", "recorded for a reimport"


def test_never_imports_the_same_recipe_twice(
    db: Session, web: FakeWeb, llm: MagicMock
) -> None:
    site = _site()
    web.add_site(site, {1: recipe_page()})
    _crawl(db, site)
    web.requested.clear()
    llm.invoke.reset_mock()

    report = _crawl(db, site)

    assert report.outcomes == []
    assert web.recipe_requests() == [], "an imported page is not even re-read"
    llm.invoke.assert_not_called()
    count = len(
        db.exec(
            select(Recipe).where(Recipe.source_url == f"{site.origin}/recette/1")
        ).all()
    )
    assert count == 1


def test_still_does_not_reimport_after_the_recipe_was_deleted(
    db: Session, web: FakeWeb, llm: MagicMock
) -> None:
    site = _site()
    web.add_site(site, {1: recipe_page()})
    _crawl(db, site)
    row = _row(db, f"{site.origin}/recette/1")
    assert row is not None
    recipe = db.get(Recipe, row.recipe_id)
    db.delete(recipe)
    db.commit()
    llm.invoke.reset_mock()

    _crawl(db, site)

    llm.invoke.assert_not_called()
    row = _row(db, f"{site.origin}/recette/1")
    assert row is not None
    assert row.recipe_id is None
    assert row.status == CrawlStatus.IMPORTED


def test_skips_a_page_a_public_recipe_already_cites(
    db: Session, web: FakeWeb, llm: MagicMock
) -> None:
    site = _site()
    web.add_site(site, {1: recipe_page()})
    owner = crawler.crawler_owner(db)
    db.add(
        Recipe(
            title="Imported by hand",
            source_url=f"{site.origin}/recette/1",
            is_public=True,
            owner_id=owner.id,
        )
    )
    db.commit()

    _crawl(db, site)

    assert web.recipe_requests() == []
    llm.invoke.assert_not_called()


def test_records_rejections_and_rechecks_them_only_after_a_while(
    db: Session, web: FakeWeb, llm: MagicMock
) -> None:
    site = _site()
    web.add_site(site, {1: recipe_page(rating=4.1), 2: recipe_page(count=3)})

    report = _crawl(db, site)

    assert {o.reason for o in report.with_status(CrawlStatus.REJECTED)} == {
        "rated 4.1, below 4.5",
        "3 ratings, below 50",
    }
    llm.invoke.assert_not_called()

    web.requested.clear()
    _crawl(db, site)
    assert web.recipe_requests() == [], "a fresh verdict stands"

    row = _row(db, f"{site.origin}/recette/1")
    assert row is not None
    row.last_attempt_at -= crawler.REJECTED_RECHECK_AFTER + timedelta(days=1)
    db.add(row)
    db.commit()
    web.pages[f"{site.origin}/recette/1"] = (200, recipe_page(rating=4.7))

    report = _crawl(db, site)

    assert [o.url for o in report.with_status(CrawlStatus.IMPORTED)] == [
        f"{site.origin}/recette/1"
    ]
    row = _row(db, f"{site.origin}/recette/1")
    assert row is not None
    assert (row.status, row.attempts) == (CrawlStatus.IMPORTED, 1)


def test_imports_the_best_first_and_stops_at_the_limit(
    db: Session, web: FakeWeb
) -> None:
    site = _site()
    web.add_site(
        site,
        {
            1: recipe_page("Bien", rating=4.6, count=60),
            2: recipe_page("Excellent", rating=4.9, count=5000),
            3: recipe_page("Très bien", rating=4.7, count=800),
        },
    )

    report = _crawl(db, site, max_imports=2)

    imported = [o.title for o in report.with_status(CrawlStatus.IMPORTED)]
    assert len(imported) == 2
    assert [o.url for o in report.with_status(CrawlStatus.IMPORTED)] == [
        f"{site.origin}/recette/2",
        f"{site.origin}/recette/3",
    ]
    # The good one left over waits in the backlog...
    row = _row(db, f"{site.origin}/recette/1")
    assert row is not None
    assert row.status == CrawlStatus.QUALIFIED

    # ...and is the next run's import, without being judged again.
    web.requested.clear()
    report = _crawl(db, site, max_imports=2)
    assert [o.url for o in report.with_status(CrawlStatus.IMPORTED)] == [
        f"{site.origin}/recette/1"
    ]
    assert report.with_status(CrawlStatus.QUALIFIED) == []
    assert web.recipe_requests() == [f"{site.origin}/recette/1"]


def test_takes_turns_between_sites(db: Session, web: FakeWeb) -> None:
    big, small = _site(), _site()
    web.add_site(big, {n: recipe_page(rating=4.9, count=9000) for n in (1, 2, 3)})
    web.add_site(small, {1: recipe_page(rating=4.6, count=60)})

    report = _crawl(db, big, small, max_imports=2)

    sites = sorted(o.site for o in report.with_status(CrawlStatus.IMPORTED))
    assert sites == sorted([big.slug, small.slug])


def test_reads_at_most_max_pages_per_site(db: Session, web: FakeWeb) -> None:
    site = _site()
    web.add_site(site, {n: recipe_page(rating=3.0) for n in range(1, 6)})

    _crawl(db, site, max_pages_per_site=2)

    assert web.recipe_requests() == [
        f"{site.origin}/recette/1",
        f"{site.origin}/recette/2",
    ]

    web.requested.clear()
    _crawl(db, site, max_pages_per_site=2)
    assert web.recipe_requests() == [
        f"{site.origin}/recette/3",
        f"{site.origin}/recette/4",
    ], "the next run carries on down the list"


def test_honours_robots_txt(db: Session, web: FakeWeb) -> None:
    site = _site()
    web.add_site(
        site,
        {1: recipe_page(), 2: recipe_page()},
        robots="User-agent: *\nDisallow: /recette/1$\n",
    )

    report = _crawl(db, site)

    assert f"{site.origin}/recette/1" not in web.requested
    rejected = report.with_status(CrawlStatus.REJECTED)
    assert [(o.url, o.reason) for o in rejected] == [
        (f"{site.origin}/recette/1", "robots.txt disallows")
    ]
    assert len(report.with_status(CrawlStatus.IMPORTED)) == 1


def test_a_site_that_is_down_is_skipped_without_blaming_its_recipes(
    db: Session, web: FakeWeb
) -> None:
    down, up = _site(), _site()
    web.add_site(down, {1: recipe_page()})
    web.add_site(up, {1: recipe_page()})
    web.pages[f"{down.origin}/recette/1"] = (503, "Service unavailable")

    report = _crawl(db, down, up)

    assert _row(db, f"{down.origin}/recette/1") is None
    assert [o.site for o in report.with_status(CrawlStatus.IMPORTED)] == [up.slug]


def test_an_unreachable_robots_txt_stops_the_site(db: Session, web: FakeWeb) -> None:
    site = _site()
    web.add_site(site, {1: recipe_page()})
    web.pages[f"{site.origin}/robots.txt"] = (500, "oops")

    report = _crawl(db, site)

    assert report.outcomes == []
    assert web.recipe_requests() == []


def test_a_transport_failure_stops_the_site(db: Session, web: FakeWeb) -> None:
    site = _site()
    web.add_site(site, {1: recipe_page()})
    web.down.add(site.origin)

    assert _crawl(db, site).outcomes == []


def test_a_failed_import_is_retried_then_given_up(
    db: Session, web: FakeWeb, llm: MagicMock
) -> None:
    site = _site()
    url = f"{site.origin}/recette/1"
    web.add_site(site, {1: recipe_page()})
    llm.invoke.side_effect = RuntimeError("model timed out")

    for attempt in range(1, crawler.MAX_FAILED_ATTEMPTS + 1):
        report = _crawl(db, site)
        assert [o.url for o in report.with_status(CrawlStatus.FAILED)] == [url]
        row = _row(db, url)
        assert row is not None
        assert (row.status, row.attempts) == (CrawlStatus.FAILED, attempt)
        assert row.reason == "RuntimeError: model timed out"
        # Not retried the same day...
        assert _crawl(db, site).outcomes == []
        row.last_attempt_at -= crawler.FAILED_RETRY_AFTER
        db.add(row)
        db.commit()

    # ...and not at all once it has failed MAX_FAILED_ATTEMPTS times.
    llm.invoke.reset_mock()
    assert _crawl(db, site).outcomes == []
    llm.invoke.assert_not_called()


def test_an_incomplete_model_answer_is_a_failure(
    db: Session, web: FakeWeb, llm: MagicMock
) -> None:
    site = _site()
    web.add_site(site, {1: recipe_page()})
    llm.invoke.return_value.content = json.dumps({"title": "Vide"})

    report = _crawl(db, site)

    failed = report.with_status(CrawlStatus.FAILED)
    assert [o.reason for o in failed] == [
        "ValueError: the model returned an incomplete recipe"
    ]
    assert db.exec(select(Recipe).where(Recipe.title == "Vide")).first() is None


def test_two_urls_for_one_page_import_it_once(
    db: Session, web: FakeWeb, llm: MagicMock
) -> None:
    site = _site()
    canonical = f"{site.origin}/recette/1"
    web.add_site(
        site,
        {1: recipe_page(canonical=canonical), 2: recipe_page(canonical=canonical)},
    )

    report = _crawl(db, site)

    assert [o.url for o in report.with_status(CrawlStatus.IMPORTED)] == [canonical]
    assert llm.invoke.call_count == 1


def test_dry_run_judges_but_neither_imports_nor_remembers(
    db: Session, web: FakeWeb, llm: MagicMock
) -> None:
    site = _site()
    web.add_site(site, {1: recipe_page(), 2: recipe_page(rating=3.0)})

    report = _crawl(db, site, dry_run=True)

    assert [o.url for o in report.with_status(CrawlStatus.QUALIFIED)] == [
        f"{site.origin}/recette/1"
    ]
    assert len(report.with_status(CrawlStatus.REJECTED)) == 1
    llm.invoke.assert_not_called()
    assert _row(db, f"{site.origin}/recette/1") is None
    assert _row(db, f"{site.origin}/recette/2") is None


def test_waits_between_requests_to_a_site(db: Session, web: FakeWeb) -> None:
    site = _site()
    web.add_site(site, {1: recipe_page(rating=3.0), 2: recipe_page(rating=3.0)})
    pauses: list[float] = []

    def pause(seconds: float) -> bool:
        pauses.append(seconds)
        return False

    _crawl(db, site, delay_seconds=30, pause=pause)

    # Listing, then two recipe pages: two waits, each close to the full delay.
    assert len(pauses) == 2
    assert all(25 < p <= 30 for p in pauses)


def test_a_stop_request_during_a_pause_ends_the_run(db: Session, web: FakeWeb) -> None:
    first, second = _site(), _site()
    web.add_site(first, {1: recipe_page()})
    web.add_site(second, {1: recipe_page()})

    report = _crawl(db, first, second, delay_seconds=30, pause=lambda _s: True)

    assert report.outcomes == []
    assert web.requested == [
        f"{first.origin}/robots.txt",
        first.seed_urls[0],
    ]


def test_run_crawl_logs_the_run(db: Session, web: FakeWeb) -> None:
    site = _site()
    web.add_site(site, {1: recipe_page(), 2: recipe_page(rating=3.0)})

    with (
        patch.object(crawler, "SITES", (site,)),
        patch.object(settings, "RECIPE_CRAWL_DELAY_SECONDS", 0),
    ):
        report = crawler.run_crawl(db)

    assert report is not None
    run = db.exec(
        select(RecipeCrawlRun).order_by(RecipeCrawlRun.started_at.desc())  # type: ignore[attr-defined]
    ).first()
    assert run is not None
    assert run.finished_at is not None
    assert (
        run.qualified_count,
        run.imported_count,
        run.rejected_count,
        run.failed_count,
    ) == (1, 1, 1, 0)
    assert run.pages_fetched == 3  # the listing and two recipes; not robots.txt


def test_run_crawl_does_nothing_without_an_ai_provider(
    db: Session, web: FakeWeb
) -> None:
    with patch(GET_LLM, side_effect=ValueError("ANTHROPIC_API_KEY is not configured")):
        assert crawler.run_crawl(db) is None
    assert web.requested == []


def test_run_crawl_does_nothing_when_no_imports_are_allowed(
    db: Session, web: FakeWeb
) -> None:
    with patch.object(settings, "RECIPE_CRAWL_MAX_IMPORTS", 0):
        assert crawler.run_crawl(db) is None
    assert web.requested == []


def _queue(db: Session, web: FakeWeb, site: RecipeSite) -> str:
    """Leave one qualified recipe of ``site`` waiting in the backlog."""
    web.add_site(site, {1: recipe_page()})
    _crawl(db, site, max_imports=0)
    url = f"{site.origin}/recette/1"
    row = _row(db, url)
    assert row is not None
    assert row.status == CrawlStatus.QUALIFIED
    return url


def test_a_backlog_page_that_has_gone_is_rejected(
    db: Session, web: FakeWeb, llm: MagicMock
) -> None:
    site = _site()
    url = _queue(db, web, site)
    web.pages[url] = (404, "Not found")

    report = _crawl(db, site)

    assert [(o.url, o.reason) for o in report.with_status(CrawlStatus.REJECTED)] == [
        (url, "HTTP 404")
    ]
    llm.invoke.assert_not_called()


def test_a_backlog_page_published_meanwhile_is_not_imported_again(
    db: Session, web: FakeWeb, llm: MagicMock
) -> None:
    site = _site()
    url = _queue(db, web, site)
    db.add(
        Recipe(
            title="Imported by hand",
            source_url=url,
            is_public=True,
            owner_id=crawler.crawler_owner(db).id,
        )
    )
    db.commit()

    report = _crawl(db, site)

    assert [o.reason for o in report.with_status(CrawlStatus.REJECTED)] == [
        "already a public recipe"
    ]
    llm.invoke.assert_not_called()


def test_the_backlog_of_a_site_that_is_down_waits(db: Session, web: FakeWeb) -> None:
    site = _site()
    url = _queue(db, web, site)
    web.down.add(site.origin)

    assert _crawl(db, site).outcomes == []
    row = _row(db, url)
    assert row is not None
    assert (row.status, row.attempts) == (CrawlStatus.QUALIFIED, 0)
