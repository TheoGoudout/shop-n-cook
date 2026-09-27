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
    Recipe,
    RecipeIngredient,
    ShoppingList,
    ShoppingListItem,
    User,
)
from tests.utils.user import authentication_token_from_email
from tests.utils.utils import get_superuser_token_headers


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


@pytest.fixture(scope="session", autouse=True)
def db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        init_db(session)
        yield session
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
