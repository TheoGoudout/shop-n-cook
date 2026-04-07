import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app import crud
from app.models import IngredientCreate, IngredientCategory, RecipeIngredientCreate, Unit
from tests.utils.recipe import create_random_recipe
from tests.utils.user import create_random_user


def test_create_recipe(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    data = {"title": "Pasta Bolognese", "servings": 4}
    response = client.post(
        f"{settings.API_V1_STR}/recipes/",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["title"] == data["title"]
    assert content["servings"] == data["servings"]
    assert "id" in content
    assert content["ingredients"] == []


def test_create_recipe_with_ingredients(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    ingredient = crud.create_ingredient(
        session=db,
        ingredient_in=IngredientCreate(
            name="garlic-test",
            category=IngredientCategory.PRODUCE,
            default_unit=Unit.CLOVE,
        ),
    )
    data = {
        "title": "Garlic Bread",
        "ingredients": [
            {
                "ingredient_id": str(ingredient.id),
                "quantity": 3.0,
                "unit": Unit.CLOVE.value,
            }
        ],
    }
    response = client.post(
        f"{settings.API_V1_STR}/recipes/",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert len(content["ingredients"]) == 1
    assert content["ingredients"][0]["ingredient_name"] == "garlic-test"
    assert content["ingredients"][0]["quantity"] == 3.0


def test_create_recipe_requires_auth(client: TestClient) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/recipes/", json={"title": "Sneaky Recipe"}
    )
    assert response.status_code == 401


def test_read_recipe(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    superuser = crud.get_user_by_email(
        session=db, email=settings.FIRST_SUPERUSER
    )
    recipe = create_random_recipe(db, owner_id=superuser.id)  # type: ignore[union-attr]
    response = client.get(
        f"{settings.API_V1_STR}/recipes/{recipe.id}",  # type: ignore[attr-defined]
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    assert response.json()["id"] == str(recipe.id)  # type: ignore[attr-defined]


def test_read_recipe_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/recipes/{uuid.uuid4()}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404


def test_read_recipe_forbidden_for_other_user(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    other_user = create_random_user(db)
    recipe = create_random_recipe(db, owner_id=other_user.id)
    response = client.get(
        f"{settings.API_V1_STR}/recipes/{recipe.id}",  # type: ignore[attr-defined]
        headers=normal_user_token_headers,
    )
    assert response.status_code == 403


def test_read_recipes(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    superuser = crud.get_user_by_email(
        session=db, email=settings.FIRST_SUPERUSER
    )
    create_random_recipe(db, owner_id=superuser.id)  # type: ignore[union-attr]
    create_random_recipe(db, owner_id=superuser.id)  # type: ignore[union-attr]
    response = client.get(
        f"{settings.API_V1_STR}/recipes/",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["count"] >= 2


def test_update_recipe(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    superuser = crud.get_user_by_email(
        session=db, email=settings.FIRST_SUPERUSER
    )
    recipe = create_random_recipe(db, owner_id=superuser.id)  # type: ignore[union-attr]
    data = {"title": f"Updated-{recipe.title}", "servings": 2}  # type: ignore[attr-defined]
    response = client.put(
        f"{settings.API_V1_STR}/recipes/{recipe.id}",  # type: ignore[attr-defined]
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    assert response.json()["title"] == data["title"]
    assert response.json()["servings"] == 2


def test_update_recipe_replace_ingredients(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    superuser = crud.get_user_by_email(
        session=db, email=settings.FIRST_SUPERUSER
    )
    recipe = create_random_recipe(db, owner_id=superuser.id, with_ingredients=True)  # type: ignore[union-attr]
    assert len(recipe.recipe_ingredients) == 2  # type: ignore[attr-defined]

    # Replace with a single new ingredient
    ingredient = crud.create_ingredient(
        session=db,
        ingredient_in=IngredientCreate(
            name="replacement-ingredient",
            category=IngredientCategory.OTHER,
            default_unit=Unit.GRAM,
        ),
    )
    data = {
        "ingredients": [
            {
                "ingredient_id": str(ingredient.id),
                "quantity": 200.0,
                "unit": Unit.GRAM.value,
            }
        ]
    }
    response = client.put(
        f"{settings.API_V1_STR}/recipes/{recipe.id}",  # type: ignore[attr-defined]
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    assert len(response.json()["ingredients"]) == 1
    assert response.json()["ingredients"][0]["quantity"] == 200.0


def test_update_recipe_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.put(
        f"{settings.API_V1_STR}/recipes/{uuid.uuid4()}",
        headers=superuser_token_headers,
        json={"title": "Ghost"},
    )
    assert response.status_code == 404


def test_update_recipe_not_enough_permissions(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    other_user = create_random_user(db)
    recipe = create_random_recipe(db, owner_id=other_user.id)
    response = client.put(
        f"{settings.API_V1_STR}/recipes/{recipe.id}",  # type: ignore[attr-defined]
        headers=normal_user_token_headers,
        json={"title": "Hacked"},
    )
    assert response.status_code == 403


def test_delete_recipe(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    superuser = crud.get_user_by_email(
        session=db, email=settings.FIRST_SUPERUSER
    )
    recipe = create_random_recipe(db, owner_id=superuser.id)  # type: ignore[union-attr]
    response = client.delete(
        f"{settings.API_V1_STR}/recipes/{recipe.id}",  # type: ignore[attr-defined]
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Recipe deleted successfully"


def test_delete_recipe_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.delete(
        f"{settings.API_V1_STR}/recipes/{uuid.uuid4()}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404


def test_delete_recipe_not_enough_permissions(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    other_user = create_random_user(db)
    recipe = create_random_recipe(db, owner_id=other_user.id)
    response = client.delete(
        f"{settings.API_V1_STR}/recipes/{recipe.id}",  # type: ignore[attr-defined]
        headers=normal_user_token_headers,
    )
    assert response.status_code == 403
