from collections.abc import Generator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, delete

from app.core.config import settings
from app.core.db import engine, init_db
from app.core.limiter import limiter
from app.main import app
from app.models import (
    CrawledRecipe,
    Recipe,
    RecipeCrawlRun,
    RecipeIngredient,
    ShoppingList,
    ShoppingListItem,
    User,
)
from app.services.store_providers.families import (
    openprices,
    openprices_snapshot,
    robots,
)
from tests.utils.user import authentication_token_from_email
from tests.utils.utils import get_superuser_token_headers

# No background price refresh: it would reach real retailers from a thread no
# test controls. Set before any ``TestClient`` runs the app's lifespan.
settings.STORE_PRICE_REFRESH_HOURS = 0


@pytest.fixture(scope="session", autouse=True)
def disable_rate_limiting() -> Generator[None, None, None]:
    """Disable slowapi rate limiting during tests.

    TestClient routes all requests from a single synthetic IP, so rate limits
    would trip almost immediately across the test suite.
    """
    limiter._enabled = False
    yield
    limiter._enabled = True


@pytest.fixture(autouse=True)
def no_network() -> Generator[None, None, None]:
    """Fail any test that would really reach the internet.

    Retailers and Open Prices are real services: a test that forgets a mock
    would hammer them from CI, and pass or fail on their uptime. A test that
    patches ``httpx.get`` itself still wins, since its patch is the inner one.
    """

    def refuse(url: object, *_args: object, **_kwargs: object) -> None:
        raise AssertionError(f"test tried to reach the network: {url}")

    with (
        patch("httpx.get", side_effect=refuse),
        patch("httpx.post", side_effect=refuse),
    ):
        yield


@pytest.fixture(autouse=True)
def fresh_provider_caches() -> Generator[None, None, None]:
    """Store providers cache across calls on purpose; tests must not share."""
    openprices.clear_caches()
    openprices_snapshot.clear_cache()
    robots.clear_cache()
    yield


@pytest.fixture(scope="session", autouse=True)
def db() -> Generator[Session, None, None]:
    """The session tests build their fixtures with.

    CRUD functions only flush; the app commits once per request. Tests call
    CRUD directly and then go through the API, which reads on another
    connection, so this session autocommits every statement it flushes.
    """
    autocommit = engine.execution_options(isolation_level="AUTOCOMMIT")
    with Session(autocommit) as session:
        init_db(session)
        yield session
        session.execute(delete(CrawledRecipe))
        session.execute(delete(RecipeCrawlRun))
        session.execute(delete(ShoppingListItem))
        session.execute(delete(ShoppingList))
        session.execute(delete(RecipeIngredient))
        session.execute(delete(Recipe))
        session.execute(delete(User))
        session.commit()


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def superuser_token_headers(client: TestClient) -> dict[str, str]:
    return get_superuser_token_headers(client)


@pytest.fixture(scope="module")
def normal_user_token_headers(client: TestClient, db: Session) -> dict[str, str]:
    return authentication_token_from_email(
        client=client, email=settings.EMAIL_TEST_USER, db=db
    )
