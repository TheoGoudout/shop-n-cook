from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings


def test_read_user_settings_creates_defaults(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/users/me/settings",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["household_size"] == 2
    assert data["shopping_frequency"] == "weekly"
    assert "id" in data
    assert "user_id" in data


def test_read_user_settings_twice_returns_same(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    r1 = client.get(
        f"{settings.API_V1_STR}/users/me/settings",
        headers=normal_user_token_headers,
    )
    r2 = client.get(
        f"{settings.API_V1_STR}/users/me/settings",
        headers=normal_user_token_headers,
    )
    assert r1.json()["id"] == r2.json()["id"]


def test_update_user_settings(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = client.put(
        f"{settings.API_V1_STR}/users/me/settings",
        headers=normal_user_token_headers,
        json={"household_size": 4, "shopping_frequency": "biweekly"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["household_size"] == 4
    assert data["shopping_frequency"] == "biweekly"


def test_update_user_settings_partial(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    client.put(
        f"{settings.API_V1_STR}/users/me/settings",
        headers=normal_user_token_headers,
        json={"household_size": 3},
    )
    response = client.put(
        f"{settings.API_V1_STR}/users/me/settings",
        headers=normal_user_token_headers,
        json={"shopping_frequency": "monthly"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["household_size"] == 3
    assert data["shopping_frequency"] == "monthly"


def test_user_settings_requires_auth(client: TestClient) -> None:
    response = client.get(f"{settings.API_V1_STR}/users/me/settings")
    assert response.status_code == 401
