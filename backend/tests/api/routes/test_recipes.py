import uuid

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from tests.utils.recipe import create_random_recipe
from tests.utils.user import create_random_user, user_authentication_headers
from tests.utils.utils import random_lower_string


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_headers(client: TestClient, db: Session) -> dict[str, str]:
    """Create a fresh user and return auth headers for them."""
    user = create_random_user(db)
    from tests.utils.utils import random_lower_string as rls
    from app import crud
    from app.models import UserUpdate
    new_pass = rls()
    crud.update_user(session=db, db_user=user, user_in=UserUpdate(password=new_pass))
    return user_authentication_headers(client=client, email=user.email, password=new_pass)


# ---------------------------------------------------------------------------
# Read recipes (list)
# ---------------------------------------------------------------------------

def test_read_recipes_empty(client: TestClient, normal_user_token_headers: dict[str, str]) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/recipes/",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert "data" in content
    assert "count" in content


def test_read_recipes_returns_own_only(client: TestClient, db: Session) -> None:
    user = create_random_user(db)
    recipe = create_random_recipe(db, owner_id=user.id)

    from tests.utils.utils import random_lower_string as rls
    from app import crud
    from app.models import UserUpdate
    pw = rls()
    crud.update_user(session=db, db_user=user, user_in=UserUpdate(password=pw))
    headers = user_authentication_headers(client=client, email=user.email, password=pw)

    response = client.get(f"{settings.API_V1_STR}/recipes/", headers=headers)
    assert response.status_code == 200
    ids = [r["id"] for r in response.json()["data"]]
    assert str(recipe.id) in ids


# ---------------------------------------------------------------------------
# Create recipe
# ---------------------------------------------------------------------------

def test_create_recipe_no_ingredients(client: TestClient, normal_user_token_headers: dict[str, str]) -> None:
    data = {"title": "Omelette", "description": "Simple", "base_servings": 2}
    response = client.post(
        f"{settings.API_V1_STR}/recipes/",
        headers=normal_user_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["title"] == "Omelette"
    assert content["base_servings"] == 2
    assert content["ingredients"] == []
    assert "id" in content
    assert "owner_id" in content


def test_create_recipe_with_ingredients(client: TestClient, normal_user_token_headers: dict[str, str]) -> None:
    data = {
        "title": "Pancakes",
        "base_servings": 4,
        "ingredients": [
            {"name": "Flour", "quantity": 200, "unit": "g"},
            {"name": "Milk", "quantity": 300, "unit": "ml"},
            {"name": "Egg", "quantity": 2, "unit": "piece"},
        ],
    }
    response = client.post(
        f"{settings.API_V1_STR}/recipes/",
        headers=normal_user_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["title"] == "Pancakes"
    assert len(content["ingredients"]) == 3
    names = [i["name"] for i in content["ingredients"]]
    assert "Flour" in names
    assert "Milk" in names


def test_create_recipe_missing_title(client: TestClient, normal_user_token_headers: dict[str, str]) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/recipes/",
        headers=normal_user_token_headers,
        json={"base_servings": 2},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Read recipe by id
# ---------------------------------------------------------------------------

def test_read_recipe(client: TestClient, normal_user_token_headers: dict[str, str], db: Session) -> None:
    user_response = client.get(f"{settings.API_V1_STR}/users/me", headers=normal_user_token_headers)
    user_id = uuid.UUID(user_response.json()["id"])
    recipe = create_random_recipe(db, owner_id=user_id)

    response = client.get(
        f"{settings.API_V1_STR}/recipes/{recipe.id}",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["id"] == str(recipe.id)
    assert content["title"] == recipe.title
    assert len(content["ingredients"]) == 1


def test_read_recipe_not_found(client: TestClient, normal_user_token_headers: dict[str, str]) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/recipes/{uuid.uuid4()}",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 404


def test_read_recipe_not_owner(client: TestClient, db: Session) -> None:
    recipe = create_random_recipe(db)
    other_user = create_random_user(db)

    from tests.utils.utils import random_lower_string as rls
    from app import crud
    from app.models import UserUpdate
    pw = rls()
    crud.update_user(session=db, db_user=other_user, user_in=UserUpdate(password=pw))
    headers = user_authentication_headers(client=client, email=other_user.email, password=pw)

    response = client.get(f"{settings.API_V1_STR}/recipes/{recipe.id}", headers=headers)
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Update recipe
# ---------------------------------------------------------------------------

def test_update_recipe_metadata(client: TestClient, db: Session) -> None:
    user = create_random_user(db)
    recipe = create_random_recipe(db, owner_id=user.id)

    from tests.utils.utils import random_lower_string as rls
    from app import crud
    from app.models import UserUpdate
    pw = rls()
    crud.update_user(session=db, db_user=user, user_in=UserUpdate(password=pw))
    headers = user_authentication_headers(client=client, email=user.email, password=pw)

    response = client.put(
        f"{settings.API_V1_STR}/recipes/{recipe.id}",
        headers=headers,
        json={"title": "Updated Title", "base_servings": 6},
    )
    assert response.status_code == 200
    content = response.json()
    assert content["title"] == "Updated Title"
    assert content["base_servings"] == 6


def test_update_recipe_replace_ingredients(client: TestClient, db: Session) -> None:
    user = create_random_user(db)
    recipe = create_random_recipe(db, owner_id=user.id)

    from tests.utils.utils import random_lower_string as rls
    from app import crud
    from app.models import UserUpdate
    pw = rls()
    crud.update_user(session=db, db_user=user, user_in=UserUpdate(password=pw))
    headers = user_authentication_headers(client=client, email=user.email, password=pw)

    response = client.put(
        f"{settings.API_V1_STR}/recipes/{recipe.id}",
        headers=headers,
        json={"ingredients": [{"name": "Sugar", "quantity": 50, "unit": "g"}]},
    )
    assert response.status_code == 200
    content = response.json()
    assert len(content["ingredients"]) == 1
    assert content["ingredients"][0]["name"] == "Sugar"


def test_update_recipe_not_found(client: TestClient, normal_user_token_headers: dict[str, str]) -> None:
    response = client.put(
        f"{settings.API_V1_STR}/recipes/{uuid.uuid4()}",
        headers=normal_user_token_headers,
        json={"title": "x"},
    )
    assert response.status_code == 404


def test_update_recipe_not_owner(client: TestClient, db: Session) -> None:
    recipe = create_random_recipe(db)
    other = create_random_user(db)

    from tests.utils.utils import random_lower_string as rls
    from app import crud
    from app.models import UserUpdate
    pw = rls()
    crud.update_user(session=db, db_user=other, user_in=UserUpdate(password=pw))
    headers = user_authentication_headers(client=client, email=other.email, password=pw)

    response = client.put(
        f"{settings.API_V1_STR}/recipes/{recipe.id}",
        headers=headers,
        json={"title": "steal"},
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Delete recipe
# ---------------------------------------------------------------------------

def test_delete_recipe(client: TestClient, db: Session) -> None:
    user = create_random_user(db)
    recipe = create_random_recipe(db, owner_id=user.id)

    from tests.utils.utils import random_lower_string as rls
    from app import crud
    from app.models import UserUpdate
    pw = rls()
    crud.update_user(session=db, db_user=user, user_in=UserUpdate(password=pw))
    headers = user_authentication_headers(client=client, email=user.email, password=pw)

    response = client.delete(f"{settings.API_V1_STR}/recipes/{recipe.id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["message"] == "Recipe deleted successfully"

    # Verify gone
    response = client.get(f"{settings.API_V1_STR}/recipes/{recipe.id}", headers=headers)
    assert response.status_code == 404


def test_delete_recipe_not_found(client: TestClient, normal_user_token_headers: dict[str, str]) -> None:
    response = client.delete(
        f"{settings.API_V1_STR}/recipes/{uuid.uuid4()}",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 404


def test_delete_recipe_not_owner(client: TestClient, db: Session) -> None:
    recipe = create_random_recipe(db)
    other = create_random_user(db)

    from tests.utils.utils import random_lower_string as rls
    from app import crud
    from app.models import UserUpdate
    pw = rls()
    crud.update_user(session=db, db_user=other, user_in=UserUpdate(password=pw))
    headers = user_authentication_headers(client=client, email=other.email, password=pw)

    response = client.delete(f"{settings.API_V1_STR}/recipes/{recipe.id}", headers=headers)
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Ingredient sub-routes
# ---------------------------------------------------------------------------

def test_add_ingredient(client: TestClient, db: Session) -> None:
    user = create_random_user(db)
    recipe = create_random_recipe(db, owner_id=user.id)

    from tests.utils.utils import random_lower_string as rls
    from app import crud
    from app.models import UserUpdate
    pw = rls()
    crud.update_user(session=db, db_user=user, user_in=UserUpdate(password=pw))
    headers = user_authentication_headers(client=client, email=user.email, password=pw)

    response = client.post(
        f"{settings.API_V1_STR}/recipes/{recipe.id}/ingredients",
        headers=headers,
        json={"name": "Butter", "quantity": 50, "unit": "g"},
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == "Butter"
    assert content["quantity"] == 50
    assert content["unit"] == "g"
    assert content["recipe_id"] == str(recipe.id)


def test_add_ingredient_recipe_not_found(client: TestClient, normal_user_token_headers: dict[str, str]) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/recipes/{uuid.uuid4()}/ingredients",
        headers=normal_user_token_headers,
        json={"name": "x", "quantity": 1, "unit": "g"},
    )
    assert response.status_code == 404


def test_add_ingredient_not_owner(client: TestClient, db: Session) -> None:
    recipe = create_random_recipe(db)
    other = create_random_user(db)

    from tests.utils.utils import random_lower_string as rls
    from app import crud
    from app.models import UserUpdate
    pw = rls()
    crud.update_user(session=db, db_user=other, user_in=UserUpdate(password=pw))
    headers = user_authentication_headers(client=client, email=other.email, password=pw)

    response = client.post(
        f"{settings.API_V1_STR}/recipes/{recipe.id}/ingredients",
        headers=headers,
        json={"name": "x", "quantity": 1, "unit": "g"},
    )
    assert response.status_code == 403


def test_update_ingredient(client: TestClient, db: Session) -> None:
    user = create_random_user(db)
    recipe = create_random_recipe(db, owner_id=user.id)
    ingredient_id = recipe.ingredients[0].id

    from tests.utils.utils import random_lower_string as rls
    from app import crud
    from app.models import UserUpdate
    pw = rls()
    crud.update_user(session=db, db_user=user, user_in=UserUpdate(password=pw))
    headers = user_authentication_headers(client=client, email=user.email, password=pw)

    response = client.put(
        f"{settings.API_V1_STR}/recipes/{recipe.id}/ingredients/{ingredient_id}",
        headers=headers,
        json={"name": "Whole Wheat Flour", "quantity": 250},
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == "Whole Wheat Flour"
    assert content["quantity"] == 250


def test_update_ingredient_not_found(client: TestClient, db: Session) -> None:
    user = create_random_user(db)
    recipe = create_random_recipe(db, owner_id=user.id)

    from tests.utils.utils import random_lower_string as rls
    from app import crud
    from app.models import UserUpdate
    pw = rls()
    crud.update_user(session=db, db_user=user, user_in=UserUpdate(password=pw))
    headers = user_authentication_headers(client=client, email=user.email, password=pw)

    response = client.put(
        f"{settings.API_V1_STR}/recipes/{recipe.id}/ingredients/{uuid.uuid4()}",
        headers=headers,
        json={"name": "x"},
    )
    assert response.status_code == 404


def test_update_ingredient_recipe_not_found(client: TestClient, normal_user_token_headers: dict[str, str]) -> None:
    response = client.put(
        f"{settings.API_V1_STR}/recipes/{uuid.uuid4()}/ingredients/{uuid.uuid4()}",
        headers=normal_user_token_headers,
        json={"name": "x"},
    )
    assert response.status_code == 404


def test_delete_ingredient(client: TestClient, db: Session) -> None:
    user = create_random_user(db)
    recipe = create_random_recipe(db, owner_id=user.id)
    ingredient_id = recipe.ingredients[0].id

    from tests.utils.utils import random_lower_string as rls
    from app import crud
    from app.models import UserUpdate
    pw = rls()
    crud.update_user(session=db, db_user=user, user_in=UserUpdate(password=pw))
    headers = user_authentication_headers(client=client, email=user.email, password=pw)

    response = client.delete(
        f"{settings.API_V1_STR}/recipes/{recipe.id}/ingredients/{ingredient_id}",
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Ingredient deleted successfully"


def test_delete_ingredient_not_found(client: TestClient, db: Session) -> None:
    user = create_random_user(db)
    recipe = create_random_recipe(db, owner_id=user.id)

    from tests.utils.utils import random_lower_string as rls
    from app import crud
    from app.models import UserUpdate
    pw = rls()
    crud.update_user(session=db, db_user=user, user_in=UserUpdate(password=pw))
    headers = user_authentication_headers(client=client, email=user.email, password=pw)

    response = client.delete(
        f"{settings.API_V1_STR}/recipes/{recipe.id}/ingredients/{uuid.uuid4()}",
        headers=headers,
    )
    assert response.status_code == 404


def test_delete_ingredient_recipe_not_found(client: TestClient, normal_user_token_headers: dict[str, str]) -> None:
    response = client.delete(
        f"{settings.API_V1_STR}/recipes/{uuid.uuid4()}/ingredients/{uuid.uuid4()}",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 404


def test_delete_ingredient_not_owner(client: TestClient, db: Session) -> None:
    recipe = create_random_recipe(db)
    ingredient_id = recipe.ingredients[0].id
    other = create_random_user(db)

    from tests.utils.utils import random_lower_string as rls
    from app import crud
    from app.models import UserUpdate
    pw = rls()
    crud.update_user(session=db, db_user=other, user_in=UserUpdate(password=pw))
    headers = user_authentication_headers(client=client, email=other.email, password=pw)

    response = client.delete(
        f"{settings.API_V1_STR}/recipes/{recipe.id}/ingredients/{ingredient_id}",
        headers=headers,
    )
    assert response.status_code == 403
