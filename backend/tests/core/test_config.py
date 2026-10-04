import warnings
from typing import Any

import pytest
from pydantic import ValidationError

from app.core.config import Settings

REQUIRED: dict[str, Any] = {
    "PROJECT_NAME": "Shop n Cook",
    "POSTGRES_SERVER": "db",
    "POSTGRES_USER": "postgres",
    "POSTGRES_PASSWORD": "a-real-password",
    "FIRST_SUPERUSER": "admin@example.com",
    "FIRST_SUPERUSER_PASSWORD": "a-real-password",
    "SECRET_KEY": "a-real-key",
}


def _settings(**overrides: Any) -> Settings:
    # _env_file=None: only what the test passes, not the developer's .env
    return Settings(_env_file=None, **{**REQUIRED, **overrides})  # type: ignore[call-arg]


@pytest.mark.parametrize("environment", ["dev", "staging", "production"])
def test_placeholder_secret_is_refused_when_deployed(environment: str) -> None:
    """dev is deployed like staging and production, so it gets the same guard."""
    with pytest.raises(ValidationError, match='SECRET_KEY is "changethis"'):
        _settings(ENVIRONMENT=environment, SECRET_KEY="changethis")


@pytest.mark.parametrize("environment", ["dev", "staging", "production"])
def test_real_secrets_are_accepted_when_deployed(environment: str) -> None:
    assert _settings(ENVIRONMENT=environment).ENVIRONMENT == environment


def test_placeholder_secret_only_warns_locally() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        settings = _settings(ENVIRONMENT="local", SECRET_KEY="changethis")
    assert settings.ENVIRONMENT == "local"
    assert any("SECRET_KEY" in str(w.message) for w in caught)


def test_unknown_environment_is_refused() -> None:
    with pytest.raises(ValidationError, match="ENVIRONMENT"):
        _settings(ENVIRONMENT="qa")
