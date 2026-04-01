import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from tests.utils.recipe import create_random_recipe
from tests.utils.user import create_random_user, user_authentication_headers
from tests.utils.utils import random_lower_string


def _new_user_headers(client: TestClient, db: Session) -> tuple:
    user = create_random_user(db)
    from app import crud
    from app.models import UserUpdate
    pw = random_lower_string()
    crud.update_user(session=db, db_user=user, user_in=UserUpdate(password=pw))
    headers = user_authentication_headers(client=client, email=user.email, password=pw)
    return user, headers


def _create_list(client: TestClient, headers: dict, name: str = "My List") -> dict:
    r = client.post(
        f"{settings.API_V1_STR}/shopping-lists/",
        headers=headers,
        json={"name": name},
    )
    assert r.status_code == 200
    return r.json()


def _add_recipe(client: TestClient, headers: dict, list_id: str, recipe_id: str,
                num_people: int = 4, num_meals: int = 1) -> dict:
    r = client.post(
        f"{settings.API_V1_STR}/shopping-lists/{list_id}/recipes",
        headers=headers,
        json={"recipe_id": recipe_id, "num_people": num_people, "num_meals": num_meals},
    )
    assert r.status_code == 200
    return r.json()


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

def test_create_shopping_list(client: TestClient, db: Session) -> None:
    _, headers = _new_user_headers(client, db)
    content = _create_list(client, headers, "Weekly Shop")
    assert content["name"] == "Weekly Shop"
    assert "id" in content
    assert content["recipes"] == []
    assert content["ingredients"] == []


def test_create_shopping_list_missing_name(client: TestClient, db: Session) -> None:
    _, headers = _new_user_headers(client, db)
    r = client.post(
        f"{settings.API_V1_STR}/shopping-lists/",
        headers=headers,
        json={},
    )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Read list (index)
# ---------------------------------------------------------------------------

def test_read_shopping_lists_empty(client: TestClient, db: Session) -> None:
    _, headers = _new_user_headers(client, db)
    r = client.get(f"{settings.API_V1_STR}/shopping-lists/", headers=headers)
    assert r.status_code == 200
    assert r.json()["data"] == []


def test_read_shopping_lists_returns_own(client: TestClient, db: Session) -> None:
    _, headers = _new_user_headers(client, db)
    _create_list(client, headers, "My List")
    r = client.get(f"{settings.API_V1_STR}/shopping-lists/", headers=headers)
    assert r.status_code == 200
    assert r.json()["count"] >= 1


# ---------------------------------------------------------------------------
# Read single
# ---------------------------------------------------------------------------

def test_read_shopping_list(client: TestClient, db: Session) -> None:
    _, headers = _new_user_headers(client, db)
    created = _create_list(client, headers)

    r = client.get(
        f"{settings.API_V1_STR}/shopping-lists/{created['id']}",
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["id"] == created["id"]


def test_read_shopping_list_not_found(client: TestClient, db: Session) -> None:
    _, headers = _new_user_headers(client, db)
    r = client.get(
        f"{settings.API_V1_STR}/shopping-lists/{uuid.uuid4()}",
        headers=headers,
    )
    assert r.status_code == 404


def test_read_shopping_list_not_owner(client: TestClient, db: Session) -> None:
    _, headers_a = _new_user_headers(client, db)
    _, headers_b = _new_user_headers(client, db)
    created = _create_list(client, headers_a)

    r = client.get(
        f"{settings.API_V1_STR}/shopping-lists/{created['id']}",
        headers=headers_b,
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

def test_update_shopping_list(client: TestClient, db: Session) -> None:
    _, headers = _new_user_headers(client, db)
    created = _create_list(client, headers, "Old")
    r = client.put(
        f"{settings.API_V1_STR}/shopping-lists/{created['id']}",
        headers=headers,
        json={"name": "New"},
    )
    assert r.status_code == 200
    assert r.json()["name"] == "New"


def test_update_shopping_list_not_found(client: TestClient, db: Session) -> None:
    _, headers = _new_user_headers(client, db)
    r = client.put(
        f"{settings.API_V1_STR}/shopping-lists/{uuid.uuid4()}",
        headers=headers,
        json={"name": "x"},
    )
    assert r.status_code == 404


def test_update_shopping_list_not_owner(client: TestClient, db: Session) -> None:
    _, headers_a = _new_user_headers(client, db)
    _, headers_b = _new_user_headers(client, db)
    created = _create_list(client, headers_a)
    r = client.put(
        f"{settings.API_V1_STR}/shopping-lists/{created['id']}",
        headers=headers_b,
        json={"name": "steal"},
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

def test_delete_shopping_list(client: TestClient, db: Session) -> None:
    _, headers = _new_user_headers(client, db)
    created = _create_list(client, headers)
    r = client.delete(
        f"{settings.API_V1_STR}/shopping-lists/{created['id']}",
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["message"] == "Shopping list deleted successfully"

    r2 = client.get(
        f"{settings.API_V1_STR}/shopping-lists/{created['id']}",
        headers=headers,
    )
    assert r2.status_code == 404


def test_delete_shopping_list_not_found(client: TestClient, db: Session) -> None:
    _, headers = _new_user_headers(client, db)
    r = client.delete(
        f"{settings.API_V1_STR}/shopping-lists/{uuid.uuid4()}",
        headers=headers,
    )
    assert r.status_code == 404


def test_delete_shopping_list_not_owner(client: TestClient, db: Session) -> None:
    _, headers_a = _new_user_headers(client, db)
    _, headers_b = _new_user_headers(client, db)
    created = _create_list(client, headers_a)
    r = client.delete(
        f"{settings.API_V1_STR}/shopping-lists/{created['id']}",
        headers=headers_b,
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Add recipe to list
# ---------------------------------------------------------------------------

def test_add_recipe_to_list(client: TestClient, db: Session) -> None:
    user, headers = _new_user_headers(client, db)
    recipe = create_random_recipe(db, owner_id=user.id)
    sl = _create_list(client, headers)

    content = _add_recipe(client, headers, sl["id"], str(recipe.id), num_people=2, num_meals=3)
    assert len(content["recipes"]) == 1
    entry = content["recipes"][0]
    assert entry["recipe_id"] == str(recipe.id)
    assert entry["num_people"] == 2
    assert entry["num_meals"] == 3


def test_add_recipe_list_not_found(client: TestClient, db: Session) -> None:
    user, headers = _new_user_headers(client, db)
    recipe = create_random_recipe(db, owner_id=user.id)
    r = client.post(
        f"{settings.API_V1_STR}/shopping-lists/{uuid.uuid4()}/recipes",
        headers=headers,
        json={"recipe_id": str(recipe.id), "num_people": 2, "num_meals": 1},
    )
    assert r.status_code == 404


def test_add_recipe_recipe_not_found(client: TestClient, db: Session) -> None:
    _, headers = _new_user_headers(client, db)
    sl = _create_list(client, headers)
    r = client.post(
        f"{settings.API_V1_STR}/shopping-lists/{sl['id']}/recipes",
        headers=headers,
        json={"recipe_id": str(uuid.uuid4()), "num_people": 2, "num_meals": 1},
    )
    assert r.status_code == 404


def test_add_recipe_not_owner_of_list(client: TestClient, db: Session) -> None:
    user_a, headers_a = _new_user_headers(client, db)
    _, headers_b = _new_user_headers(client, db)
    recipe = create_random_recipe(db, owner_id=user_a.id)
    sl = _create_list(client, headers_a)

    r = client.post(
        f"{settings.API_V1_STR}/shopping-lists/{sl['id']}/recipes",
        headers=headers_b,
        json={"recipe_id": str(recipe.id), "num_people": 2, "num_meals": 1},
    )
    assert r.status_code == 403


def test_add_recipe_not_owner_of_recipe(client: TestClient, db: Session) -> None:
    _, headers_a = _new_user_headers(client, db)
    recipe = create_random_recipe(db)  # owned by another user
    sl = _create_list(client, headers_a)

    r = client.post(
        f"{settings.API_V1_STR}/shopping-lists/{sl['id']}/recipes",
        headers=headers_a,
        json={"recipe_id": str(recipe.id), "num_people": 2, "num_meals": 1},
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Update recipe in list
# ---------------------------------------------------------------------------

def test_update_recipe_in_list(client: TestClient, db: Session) -> None:
    user, headers = _new_user_headers(client, db)
    recipe = create_random_recipe(db, owner_id=user.id)
    sl = _create_list(client, headers)
    updated = _add_recipe(client, headers, sl["id"], str(recipe.id))
    entry_id = updated["recipes"][0]["id"]

    r = client.put(
        f"{settings.API_V1_STR}/shopping-lists/{sl['id']}/recipes/{entry_id}",
        headers=headers,
        json={"num_people": 6, "num_meals": 2},
    )
    assert r.status_code == 200
    entry = r.json()["recipes"][0]
    assert entry["num_people"] == 6
    assert entry["num_meals"] == 2


def test_update_recipe_in_list_not_found(client: TestClient, db: Session) -> None:
    _, headers = _new_user_headers(client, db)
    sl = _create_list(client, headers)
    r = client.put(
        f"{settings.API_V1_STR}/shopping-lists/{sl['id']}/recipes/{uuid.uuid4()}",
        headers=headers,
        json={"num_people": 2},
    )
    assert r.status_code == 404


def test_update_recipe_list_not_found(client: TestClient, db: Session) -> None:
    _, headers = _new_user_headers(client, db)
    r = client.put(
        f"{settings.API_V1_STR}/shopping-lists/{uuid.uuid4()}/recipes/{uuid.uuid4()}",
        headers=headers,
        json={"num_people": 2},
    )
    assert r.status_code == 404


def test_update_recipe_in_list_not_owner(client: TestClient, db: Session) -> None:
    user_a, headers_a = _new_user_headers(client, db)
    _, headers_b = _new_user_headers(client, db)
    recipe = create_random_recipe(db, owner_id=user_a.id)
    sl = _create_list(client, headers_a)
    updated = _add_recipe(client, headers_a, sl["id"], str(recipe.id))
    entry_id = updated["recipes"][0]["id"]

    r = client.put(
        f"{settings.API_V1_STR}/shopping-lists/{sl['id']}/recipes/{entry_id}",
        headers=headers_b,
        json={"num_people": 10},
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Remove recipe from list
# ---------------------------------------------------------------------------

def test_remove_recipe_from_list(client: TestClient, db: Session) -> None:
    user, headers = _new_user_headers(client, db)
    recipe = create_random_recipe(db, owner_id=user.id)
    sl = _create_list(client, headers)
    updated = _add_recipe(client, headers, sl["id"], str(recipe.id))
    entry_id = updated["recipes"][0]["id"]

    r = client.delete(
        f"{settings.API_V1_STR}/shopping-lists/{sl['id']}/recipes/{entry_id}",
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["recipes"] == []


def test_remove_recipe_not_found(client: TestClient, db: Session) -> None:
    _, headers = _new_user_headers(client, db)
    sl = _create_list(client, headers)
    r = client.delete(
        f"{settings.API_V1_STR}/shopping-lists/{sl['id']}/recipes/{uuid.uuid4()}",
        headers=headers,
    )
    assert r.status_code == 404


def test_remove_recipe_list_not_found(client: TestClient, db: Session) -> None:
    _, headers = _new_user_headers(client, db)
    r = client.delete(
        f"{settings.API_V1_STR}/shopping-lists/{uuid.uuid4()}/recipes/{uuid.uuid4()}",
        headers=headers,
    )
    assert r.status_code == 404


def test_remove_recipe_not_owner(client: TestClient, db: Session) -> None:
    user_a, headers_a = _new_user_headers(client, db)
    _, headers_b = _new_user_headers(client, db)
    recipe = create_random_recipe(db, owner_id=user_a.id)
    sl = _create_list(client, headers_a)
    updated = _add_recipe(client, headers_a, sl["id"], str(recipe.id))
    entry_id = updated["recipes"][0]["id"]

    r = client.delete(
        f"{settings.API_V1_STR}/shopping-lists/{sl['id']}/recipes/{entry_id}",
        headers=headers_b,
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Ingredient aggregation
# ---------------------------------------------------------------------------

def test_ingredients_aggregated(client: TestClient, db: Session) -> None:
    """Two recipes with the same ingredient should sum quantities."""
    user, headers = _new_user_headers(client, db)
    sl = _create_list(client, headers)

    # Create recipe 1: 200g flour, base=4 servings
    r1 = client.post(f"{settings.API_V1_STR}/recipes/", headers=headers,
                     json={"title": "R1", "base_servings": 4,
                           "ingredients": [{"name": "flour", "quantity": 200, "unit": "g"}]})
    # Create recipe 2: 100g flour, base=2 servings
    r2 = client.post(f"{settings.API_V1_STR}/recipes/", headers=headers,
                     json={"title": "R2", "base_servings": 2,
                           "ingredients": [{"name": "flour", "quantity": 100, "unit": "g"}]})
    id1 = r1.json()["id"]
    id2 = r2.json()["id"]

    # Add both to list: 4 people, 1 meal each
    _add_recipe(client, headers, sl["id"], id1, num_people=4, num_meals=1)
    _add_recipe(client, headers, sl["id"], id2, num_people=2, num_meals=1)

    r = client.get(f"{settings.API_V1_STR}/shopping-lists/{sl['id']}", headers=headers)
    ingredients = r.json()["ingredients"]
    flour = next((i for i in ingredients if i["name"] == "flour"), None)
    assert flour is not None
    # Recipe 1: 200g * (4/4) = 200g, Recipe 2: 100g * (2/2) = 100g → total 300g
    assert flour["total_quantity"] == 300.0
    assert len(flour["sources"]) == 2


def test_ingredients_different_units_not_merged(client: TestClient, db: Session) -> None:
    """Same ingredient name but different units must stay separate."""
    user, headers = _new_user_headers(client, db)
    sl = _create_list(client, headers)

    r1 = client.post(f"{settings.API_V1_STR}/recipes/", headers=headers,
                     json={"title": "R1", "base_servings": 1,
                           "ingredients": [{"name": "sugar", "quantity": 100, "unit": "g"}]})
    r2 = client.post(f"{settings.API_V1_STR}/recipes/", headers=headers,
                     json={"title": "R2", "base_servings": 1,
                           "ingredients": [{"name": "sugar", "quantity": 2, "unit": "tbsp"}]})
    _add_recipe(client, headers, sl["id"], r1.json()["id"])
    _add_recipe(client, headers, sl["id"], r2.json()["id"])

    r = client.get(f"{settings.API_V1_STR}/shopping-lists/{sl['id']}", headers=headers)
    ingredients = r.json()["ingredients"]
    sugar_entries = [i for i in ingredients if i["name"] == "sugar"]
    assert len(sugar_entries) == 2


def test_ingredients_scaling(client: TestClient, db: Session) -> None:
    """Verify scaling: num_people * num_meals / base_servings."""
    user, headers = _new_user_headers(client, db)
    sl = _create_list(client, headers)

    r1 = client.post(f"{settings.API_V1_STR}/recipes/", headers=headers,
                     json={"title": "Cake", "base_servings": 4,
                           "ingredients": [{"name": "sugar", "quantity": 200, "unit": "g"}]})
    _add_recipe(client, headers, sl["id"], r1.json()["id"], num_people=8, num_meals=2)

    r = client.get(f"{settings.API_V1_STR}/shopping-lists/{sl['id']}", headers=headers)
    ingredients = r.json()["ingredients"]
    sugar = next(i for i in ingredients if i["name"] == "sugar")
    # 200 * (8 * 2 / 4) = 200 * 4 = 800
    assert sugar["total_quantity"] == 800.0


# ---------------------------------------------------------------------------
# Toggle ingredient check
# ---------------------------------------------------------------------------

def test_check_ingredient(client: TestClient, db: Session) -> None:
    user, headers = _new_user_headers(client, db)
    recipe = create_random_recipe(db, owner_id=user.id)  # has 1 ingredient: flour
    sl = _create_list(client, headers)
    _add_recipe(client, headers, sl["id"], str(recipe.id), num_people=4)

    r = client.post(
        f"{settings.API_V1_STR}/shopping-lists/{sl['id']}/ingredients/check",
        headers=headers,
        params={"ingredient_name": "flour", "unit": "g", "is_checked": True},
    )
    assert r.status_code == 200
    ingredients = r.json()["ingredients"]
    flour = next(i for i in ingredients if i["name"] == "flour")
    assert flour["is_checked"] is True


def test_uncheck_ingredient(client: TestClient, db: Session) -> None:
    user, headers = _new_user_headers(client, db)
    recipe = create_random_recipe(db, owner_id=user.id)
    sl = _create_list(client, headers)
    _add_recipe(client, headers, sl["id"], str(recipe.id), num_people=4)

    # Check then uncheck
    client.post(
        f"{settings.API_V1_STR}/shopping-lists/{sl['id']}/ingredients/check",
        headers=headers,
        params={"ingredient_name": "flour", "unit": "g", "is_checked": True},
    )
    r = client.post(
        f"{settings.API_V1_STR}/shopping-lists/{sl['id']}/ingredients/check",
        headers=headers,
        params={"ingredient_name": "flour", "unit": "g", "is_checked": False},
    )
    assert r.status_code == 200
    ingredients = r.json()["ingredients"]
    flour = next(i for i in ingredients if i["name"] == "flour")
    assert flour["is_checked"] is False


def test_check_ingredient_list_not_found(client: TestClient, db: Session) -> None:
    _, headers = _new_user_headers(client, db)
    r = client.post(
        f"{settings.API_V1_STR}/shopping-lists/{uuid.uuid4()}/ingredients/check",
        headers=headers,
        params={"ingredient_name": "flour", "unit": "g", "is_checked": True},
    )
    assert r.status_code == 404


def test_check_ingredient_not_owner(client: TestClient, db: Session) -> None:
    _, headers_a = _new_user_headers(client, db)
    _, headers_b = _new_user_headers(client, db)
    sl = _create_list(client, headers_a)

    r = client.post(
        f"{settings.API_V1_STR}/shopping-lists/{sl['id']}/ingredients/check",
        headers=headers_b,
        params={"ingredient_name": "flour", "unit": "g", "is_checked": True},
    )
    assert r.status_code == 403
