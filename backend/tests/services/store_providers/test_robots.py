"""robots.txt: the rules a retailer publishes, read the way RFC 9309 says.

The fixtures are trimmed from the files the retailers actually serve, because
the cases that matter are theirs: a wildcard in front of the path (Picard), a
wildcard inside the query (Lidl), and a rule with no leading slash (Monoprix).
"""

from collections.abc import Iterator
from unittest.mock import patch

import pytest

from app.services.store_providers.errors import ProviderUnavailableError
from app.services.store_providers.families import robots
from app.services.store_providers.families.http_client import FetchedPage
from app.services.store_providers.families.robots import RobotsPolicy

PICARD = """
# All spiders are disallowed to access all static resources
User-agent: *
Disallow: */Search-Show*
Disallow: *viewAll=
Disallow: */recherche
Disallow: /on/demandware.store/
Allow: */fr_FR/Search-ShowInspiration?step=ingredient
Sitemap: https://www.picard.fr/sitemap_0.xml
"""

MONOPRIX = """
User-agent: Googlebot-image
Disallow:

User-agent: *
Disallow: /search?q=*
Disallow: ?sublocationId=
Disallow: /api/
"""

LIDL = """
User-agent: *
Disallow: *search?q=*
Disallow: /user-api/*
"""


def _policy(text: str) -> RobotsPolicy:
    return RobotsPolicy.parse(text, user_agent="shop-n-cook")


@pytest.fixture(autouse=True)
def _fresh_cache() -> Iterator[None]:
    robots.clear_cache()
    yield
    robots.clear_cache()


class TestRules:
    @pytest.mark.parametrize(
        ("url", "allowed"),
        [
            ("https://www.picard.fr/recherche?q=beurre", False),
            ("https://www.picard.fr/produits/frites-000000000000012345.html", True),
            ("https://www.picard.fr/sitemap_0.xml", True),
            ("https://www.picard.fr/on/demandware.store/Sites-picard-Site/x", False),
            ("https://www.picard.fr/rayons/legumes?start=40&sz=40", True),
            ("https://www.picard.fr/rayons/legumes?viewAll=true", False),
        ],
    )
    def test_picard(self, url: str, allowed: bool) -> None:
        assert _policy(PICARD).allows(url) is allowed

    @pytest.mark.parametrize(
        ("url", "allowed"),
        [
            ("https://courses.monoprix.fr/search?q=beurre", False),
            ("https://courses.monoprix.fr/api/v5/products", False),
            (
                "https://courses.monoprix.fr/products/monoprix-beurre-doux-125g/MPX_1",
                True,
            ),
            # "?sublocationId=" has no leading slash; read as matching anywhere.
            ("https://courses.monoprix.fr/categories/x?sublocationId=3", False),
        ],
    )
    def test_monoprix(self, url: str, allowed: bool) -> None:
        assert _policy(MONOPRIX).allows(url) is allowed

    def test_lidl_wildcard_inside_the_query(self) -> None:
        policy = _policy(LIDL)
        assert not policy.allows("https://www.lidl.fr/q/search?q=beurre")
        assert policy.allows("https://www.lidl.fr/h/fromages/h10095761")

    def test_longest_match_wins_and_allow_wins_a_tie(self) -> None:
        policy = _policy(
            "User-agent: *\nDisallow: /p\nAllow: /products/\n"
            "Disallow: /same\nAllow: /same\n"
        )
        assert policy.allows("https://s.test/products/1")
        assert not policy.allows("https://s.test/pages")
        assert policy.allows("https://s.test/same")

    def test_dollar_anchors_the_end(self) -> None:
        policy = _policy("User-agent: *\nDisallow: /*.pdf$\n")
        assert not policy.allows("https://s.test/a/leaflet.pdf")
        assert policy.allows("https://s.test/a/leaflet.pdf?page=2")

    def test_a_group_naming_us_replaces_the_star_group(self) -> None:
        policy = _policy(
            "User-agent: *\nDisallow: /\n\n"
            "User-agent: other-bot\nUser-agent: shop-n-cook\nDisallow: /private\n"
        )
        assert policy.allows("https://s.test/products/1")
        assert not policy.allows("https://s.test/private/x")

    def test_a_group_naming_us_with_no_rules_allows_everything(self) -> None:
        policy = _policy("User-agent: *\nDisallow: /\n\nUser-agent: shop-n-cook\n")
        assert policy.allows("https://s.test/anything")

    def test_empty_disallow_and_no_rules_allow_everything(self) -> None:
        assert _policy("User-agent: *\nDisallow:\n").allows("https://s.test/x")
        assert _policy("").allows("https://s.test/x")

    def test_percent_encoding_does_not_dodge_a_rule(self) -> None:
        policy = _policy("User-agent: *\nDisallow: /recherche\n")
        assert not policy.allows("https://s.test/%72echerche?q=x")


class TestFetching:
    def _fetch(self, status: int, text: str = "") -> object:
        return patch(
            "app.services.store_providers.families.http_client.fetch",
            return_value=FetchedPage(status_code=status, text=text),
        )

    def test_rules_are_read_and_cached_per_origin(self) -> None:
        with self._fetch(200, PICARD) as fetch:
            robots.ensure_allowed("https://www.picard.fr/produits/x-1.html")
            with pytest.raises(ProviderUnavailableError, match="robots.txt"):
                robots.ensure_allowed("https://www.picard.fr/recherche?q=x")
        fetch.assert_called_once_with("https://www.picard.fr/robots.txt")

    def test_a_missing_robots_txt_means_no_rules(self) -> None:
        with self._fetch(404):
            robots.ensure_allowed("https://s.test/recherche?q=x")

    def test_a_failing_robots_txt_means_nothing_is_allowed(self) -> None:
        with self._fetch(503):
            with pytest.raises(ProviderUnavailableError):
                robots.ensure_allowed("https://s.test/products/1")

    def test_an_unreachable_robots_txt_is_unavailable(self) -> None:
        with patch(
            "app.services.store_providers.families.http_client.fetch",
            side_effect=ProviderUnavailableError("timed out"),
        ):
            with pytest.raises(ProviderUnavailableError):
                robots.ensure_allowed("https://s.test/products/1")

    def test_the_cache_expires(self) -> None:
        with (
            self._fetch(404) as fetch,
            patch(
                "app.services.store_providers.families.robots.time.monotonic",
                side_effect=[0.0, robots.CACHE_SECONDS + 1],
            ),
        ):
            robots.policy_for("https://s.test")
            robots.policy_for("https://s.test")
        assert fetch.call_count == 2
