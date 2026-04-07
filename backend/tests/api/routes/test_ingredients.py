import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from tests.utils.ingredient import create_random_ingredient


def test_create_ingredient(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    data = {"name": "fresh basil", "category": "produce", "default_unit": "bunch"}
    response = client.post(
        f"{settings.API_V1_STR}/ingredients/",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == data["name"]
    assert content["category"] == data["category"]
    assert content["default_unit"] == data["default_unit"]
    assert "id" in content


def test_create_ingredient_duplicate_name(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    ingredient = create_random_ingredient(db)
    data = {
        "name": ingredient.name,
        "category": "other",
        "default_unit": "piece",
    }
    response = client.post(
        f"{settings.API_V1_STR}/ingredients/",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_create_ingredient_requires_auth(client: TestClient) -> None:
    data = {"name": "no-auth herb", "category": "produce", "default_unit": "bunch"}
    response = client.post(f"{settings.API_V1_STR}/ingredients/", json=data)
    assert response.status_code == 401


def test_read_ingredient(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    ingredient = create_random_ingredient(db)
    response = client.get(
        f"{settings.API_V1_STR}/ingredients/{ingredient.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["id"] == str(ingredient.id)
    assert content["name"] == ingredient.name


def test_read_ingredient_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/ingredients/{uuid.uuid4()}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Ingredient not found"


def test_read_ingredients(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    create_random_ingredient(db)
    create_random_ingredient(db)
    response = client.get(
        f"{settings.API_V1_STR}/ingredients/",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["count"] >= 2
    assert len(content["data"]) >= 2


def test_read_ingredients_search(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    ingredient = create_random_ingredient(db)
    # Search by exact name substring
    response = client.get(
        f"{settings.API_V1_STR}/ingredients/",
        headers=superuser_token_headers,
        params={"search": ingredient.name},
    )
    assert response.status_code == 200
    ids = [i["id"] for i in response.json()["data"]]
    assert str(ingredient.id) in ids


def test_read_ingredients_filter_by_category(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    from app.models import IngredientCategory, Unit

    ingredient = create_random_ingredient(
        db, category=IngredientCategory.DAIRY, default_unit=Unit.MILLILITER
    )
    response = client.get(
        f"{settings.API_V1_STR}/ingredients/",
        headers=superuser_token_headers,
        params={"category": IngredientCategory.DAIRY.value},
    )
    assert response.status_code == 200
    ids = [i["id"] for i in response.json()["data"]]
    assert str(ingredient.id) in ids
    # All returned items should be dairy
    for item in response.json()["data"]:
        assert item["category"] == IngredientCategory.DAIRY.value


def test_update_ingredient(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    ingredient = create_random_ingredient(db)
    data = {"name": f"updated-{ingredient.name}"}
    response = client.put(
        f"{settings.API_V1_STR}/ingredients/{ingredient.id}",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    assert response.json()["name"] == data["name"]


def test_update_ingredient_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.put(
        f"{settings.API_V1_STR}/ingredients/{uuid.uuid4()}",
        headers=superuser_token_headers,
        json={"name": "ghost"},
    )
    assert response.status_code == 404


def test_update_ingredient_not_enough_permissions(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    ingredient = create_random_ingredient(db)
    response = client.put(
        f"{settings.API_V1_STR}/ingredients/{ingredient.id}",
        headers=normal_user_token_headers,
        json={"name": "hacked"},
    )
    assert response.status_code == 403


def test_delete_ingredient(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    ingredient = create_random_ingredient(db)
    response = client.delete(
        f"{settings.API_V1_STR}/ingredients/{ingredient.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Ingredient deleted successfully"


def test_delete_ingredient_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.delete(
        f"{settings.API_V1_STR}/ingredients/{uuid.uuid4()}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404


def test_delete_ingredient_not_enough_permissions(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    ingredient = create_random_ingredient(db)
    response = client.delete(
        f"{settings.API_V1_STR}/ingredients/{ingredient.id}",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 403
