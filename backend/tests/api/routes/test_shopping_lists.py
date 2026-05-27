import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models import (
    ShoppingListItemCreate,
    Unit,
)
from tests.utils.recipe import create_random_recipe
from tests.utils.shopping_list import create_random_shopping_list
from tests.utils.user import create_random_user


def test_create_shopping_list(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    data = {"name": "Weekly groceries"}
    response = client.post(
        f"{settings.API_V1_STR}/shopping-lists/",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == data["name"]
    assert content["items"] == []
    assert "id" in content


def test_create_shopping_list_requires_auth(client: TestClient) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/shopping-lists/", json={"name": "No auth list"}
    )
    assert response.status_code == 401


def test_read_shopping_list(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    superuser = crud.get_user_by_email(session=db, email=settings.FIRST_SUPERUSER)
    sl = create_random_shopping_list(db, owner_id=superuser.id)  # type: ignore[union-attr]
    response = client.get(
        f"{settings.API_V1_STR}/shopping-lists/{sl.id}",  # type: ignore[attr-defined]
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    assert response.json()["id"] == str(sl.id)  # type: ignore[attr-defined]


def test_read_shopping_list_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/shopping-lists/{uuid.uuid4()}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404


def test_read_shopping_list_forbidden_for_other_user(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    other_user = create_random_user(db)
    sl = create_random_shopping_list(db, owner_id=other_user.id)
    response = client.get(
        f"{settings.API_V1_STR}/shopping-lists/{sl.id}",  # type: ignore[attr-defined]
        headers=normal_user_token_headers,
    )
    assert response.status_code == 403


def test_read_shopping_lists(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    superuser = crud.get_user_by_email(session=db, email=settings.FIRST_SUPERUSER)
    create_random_shopping_list(db, owner_id=superuser.id)  # type: ignore[union-attr]
    create_random_shopping_list(db, owner_id=superuser.id)  # type: ignore[union-attr]
    response = client.get(
        f"{settings.API_V1_STR}/shopping-lists/",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    assert response.json()["count"] >= 2


def test_update_shopping_list(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    superuser = crud.get_user_by_email(session=db, email=settings.FIRST_SUPERUSER)
    sl = create_random_shopping_list(db, owner_id=superuser.id)  # type: ignore[union-attr]
    response = client.put(
        f"{settings.API_V1_STR}/shopping-lists/{sl.id}",  # type: ignore[attr-defined]
        headers=superuser_token_headers,
        json={"name": "Renamed list"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Renamed list"


def test_delete_shopping_list(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    superuser = crud.get_user_by_email(session=db, email=settings.FIRST_SUPERUSER)
    sl = create_random_shopping_list(db, owner_id=superuser.id)  # type: ignore[union-attr]
    response = client.delete(
        f"{settings.API_V1_STR}/shopping-lists/{sl.id}",  # type: ignore[attr-defined]
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Shopping list deleted successfully"


def test_add_item_to_shopping_list(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    superuser = crud.get_user_by_email(session=db, email=settings.FIRST_SUPERUSER)
    sl = create_random_shopping_list(db, owner_id=superuser.id)  # type: ignore[union-attr]
    response = client.post(
        f"{settings.API_V1_STR}/shopping-lists/{sl.id}/items",  # type: ignore[attr-defined]
        headers=superuser_token_headers,
        json={
            "name": "Toilet paper",
            "quantity": 4.0,
            "unit": Unit.PACKAGE.value,
        },
    )
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["name"] == "Toilet paper"
    assert items[0]["quantity"] == 4.0


def test_update_item_is_checked(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    superuser = crud.get_user_by_email(session=db, email=settings.FIRST_SUPERUSER)
    sl = create_random_shopping_list(db, owner_id=superuser.id)  # type: ignore[union-attr]
    sl = crud.add_item_to_shopping_list(
        session=db,
        shopping_list=sl,  # type: ignore[arg-type]
        item_in=ShoppingListItemCreate(
            name="Milk",
            quantity=1.0,
            unit=Unit.PIECE,
        ),
    )
    item_id = sl.items[0].id  # type: ignore[attr-defined]
    response = client.put(
        f"{settings.API_V1_STR}/shopping-lists/{sl.id}/items/{item_id}",  # type: ignore[attr-defined]
        headers=superuser_token_headers,
        json={"is_checked": True},
    )
    assert response.status_code == 200
    assert response.json()["is_checked"] is True


def test_delete_item(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    superuser = crud.get_user_by_email(session=db, email=settings.FIRST_SUPERUSER)
    sl = create_random_shopping_list(db, owner_id=superuser.id)  # type: ignore[union-attr]
    sl = crud.add_item_to_shopping_list(
        session=db,
        shopping_list=sl,  # type: ignore[arg-type]
        item_in=ShoppingListItemCreate(
            name="Butter",
            quantity=1.0,
            unit=Unit.PIECE,
        ),
    )
    item_id = sl.items[0].id  # type: ignore[attr-defined]
    response = client.delete(
        f"{settings.API_V1_STR}/shopping-lists/{sl.id}/items/{item_id}",  # type: ignore[attr-defined]
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Item removed successfully"


def test_add_recipe_to_shopping_list(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    superuser = crud.get_user_by_email(session=db, email=settings.FIRST_SUPERUSER)
    sl = create_random_shopping_list(db, owner_id=superuser.id)  # type: ignore[union-attr]
    recipe = create_random_recipe(db, owner_id=superuser.id, with_ingredients=True)  # type: ignore[union-attr]
    response = client.post(
        f"{settings.API_V1_STR}/shopping-lists/{sl.id}/add-recipe/{recipe.id}",  # type: ignore[attr-defined]
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 2  # recipe has 2 ingredients


def test_add_recipe_aggregates_duplicate_ingredients(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Adding the same recipe twice should sum quantities, not duplicate rows."""
    superuser = crud.get_user_by_email(session=db, email=settings.FIRST_SUPERUSER)
    sl = create_random_shopping_list(db, owner_id=superuser.id)  # type: ignore[union-attr]
    recipe = create_random_recipe(db, owner_id=superuser.id, with_ingredients=True)  # type: ignore[union-attr]
    for _ in range(2):
        client.post(
            f"{settings.API_V1_STR}/shopping-lists/{sl.id}/add-recipe/{recipe.id}",  # type: ignore[attr-defined]
            headers=superuser_token_headers,
        )
    response = client.get(
        f"{settings.API_V1_STR}/shopping-lists/{sl.id}",  # type: ignore[attr-defined]
        headers=superuser_token_headers,
    )
    items = response.json()["items"]
    assert len(items) == 2  # still 2 distinct ingredients
    for item in items:
        assert item["quantity"] == 2.0  # each quantity doubled


def test_add_recipe_not_found(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    superuser = crud.get_user_by_email(session=db, email=settings.FIRST_SUPERUSER)
    sl = create_random_shopping_list(db, owner_id=superuser.id)  # type: ignore[union-attr]
    response = client.post(
        f"{settings.API_V1_STR}/shopping-lists/{sl.id}/add-recipe/{uuid.uuid4()}",  # type: ignore[attr-defined]
        headers=superuser_token_headers,
    )
    assert response.status_code == 404


def test_update_item_not_in_list(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """PUT with an item_id that belongs to a different list returns 404."""
    superuser = crud.get_user_by_email(session=db, email=settings.FIRST_SUPERUSER)
    sl1 = create_random_shopping_list(db, owner_id=superuser.id)  # type: ignore[union-attr]
    sl2 = create_random_shopping_list(db, owner_id=superuser.id)  # type: ignore[union-attr]
    sl2 = crud.add_item_to_shopping_list(
        session=db,
        shopping_list=sl2,  # type: ignore[arg-type]
        item_in=ShoppingListItemCreate(name="Sugar", quantity=1.0, unit=Unit.PIECE),
    )
    item_id = sl2.items[0].id  # type: ignore[attr-defined]
    # Use sl1's id but sl2's item_id → 404
    response = client.put(
        f"{settings.API_V1_STR}/shopping-lists/{sl1.id}/items/{item_id}",  # type: ignore[attr-defined]
        headers=superuser_token_headers,
        json={"is_checked": True},
    )
    assert response.status_code == 404


def test_delete_item_not_in_list(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """DELETE with an item_id that belongs to a different list returns 404."""
    superuser = crud.get_user_by_email(session=db, email=settings.FIRST_SUPERUSER)
    sl1 = create_random_shopping_list(db, owner_id=superuser.id)  # type: ignore[union-attr]
    sl2 = create_random_shopping_list(db, owner_id=superuser.id)  # type: ignore[union-attr]
    sl2 = crud.add_item_to_shopping_list(
        session=db,
        shopping_list=sl2,  # type: ignore[arg-type]
        item_in=ShoppingListItemCreate(name="Salt", quantity=1.0, unit=Unit.PIECE),
    )
    item_id = sl2.items[0].id  # type: ignore[attr-defined]
    response = client.delete(
        f"{settings.API_V1_STR}/shopping-lists/{sl1.id}/items/{item_id}",  # type: ignore[attr-defined]
        headers=superuser_token_headers,
    )
    assert response.status_code == 404


def test_update_planned_recipe_not_found(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """PATCH with a non-existent planned_recipe_id returns 404."""
    superuser = crud.get_user_by_email(session=db, email=settings.FIRST_SUPERUSER)
    sl = create_random_shopping_list(db, owner_id=superuser.id)  # type: ignore[union-attr]
    response = client.patch(
        f"{settings.API_V1_STR}/shopping-lists/{sl.id}/planned-recipes/{uuid.uuid4()}",  # type: ignore[attr-defined]
        headers=superuser_token_headers,
        json={"is_prepared": True},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Planned recipe not found"


def test_update_planned_recipe_wrong_list(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """PATCH where planned_recipe belongs to a different list returns 404."""
    superuser = crud.get_user_by_email(session=db, email=settings.FIRST_SUPERUSER)
    sl1 = create_random_shopping_list(db, owner_id=superuser.id)  # type: ignore[union-attr]
    sl2 = create_random_shopping_list(db, owner_id=superuser.id)  # type: ignore[union-attr]
    recipe = create_random_recipe(db, owner_id=superuser.id, with_ingredients=False)  # type: ignore[union-attr]
    sl2 = crud.add_recipe_to_shopping_list(
        session=db,
        shopping_list=sl2,
        recipe=recipe,  # type: ignore[arg-type]
    )
    planned_id = sl2.planned_recipes[0].id  # type: ignore[attr-defined]
    response = client.patch(
        f"{settings.API_V1_STR}/shopping-lists/{sl1.id}/planned-recipes/{planned_id}",  # type: ignore[attr-defined]
        headers=superuser_token_headers,
        json={"is_prepared": True},
    )
    assert response.status_code == 404


def test_delete_planned_recipe_not_found(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """DELETE with a non-existent planned_recipe_id returns 404."""
    superuser = crud.get_user_by_email(session=db, email=settings.FIRST_SUPERUSER)
    sl = create_random_shopping_list(db, owner_id=superuser.id)  # type: ignore[union-attr]
    response = client.delete(
        f"{settings.API_V1_STR}/shopping-lists/{sl.id}/planned-recipes/{uuid.uuid4()}",  # type: ignore[attr-defined]
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Planned recipe not found"


def test_delete_planned_recipe_wrong_list(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """DELETE where planned_recipe belongs to a different list returns 404."""
    superuser = crud.get_user_by_email(session=db, email=settings.FIRST_SUPERUSER)
    sl1 = create_random_shopping_list(db, owner_id=superuser.id)  # type: ignore[union-attr]
    sl2 = create_random_shopping_list(db, owner_id=superuser.id)  # type: ignore[union-attr]
    recipe = create_random_recipe(db, owner_id=superuser.id, with_ingredients=False)  # type: ignore[union-attr]
    sl2 = crud.add_recipe_to_shopping_list(
        session=db,
        shopping_list=sl2,
        recipe=recipe,  # type: ignore[arg-type]
    )
    planned_id = sl2.planned_recipes[0].id  # type: ignore[attr-defined]
    response = client.delete(
        f"{settings.API_V1_STR}/shopping-lists/{sl1.id}/planned-recipes/{planned_id}",  # type: ignore[attr-defined]
        headers=superuser_token_headers,
    )
    assert response.status_code == 404


def test_delete_planned_recipe_removes_ingredients(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Deleting a planned recipe removes its contributed ingredients from the list."""
    superuser = crud.get_user_by_email(session=db, email=settings.FIRST_SUPERUSER)
    sl = create_random_shopping_list(db, owner_id=superuser.id)  # type: ignore[union-attr]
    recipe = create_random_recipe(db, owner_id=superuser.id, with_ingredients=True)  # type: ignore[union-attr]
    add_resp = client.post(
        f"{settings.API_V1_STR}/shopping-lists/{sl.id}/add-recipe/{recipe.id}",  # type: ignore[attr-defined]
        headers=superuser_token_headers,
    )
    assert add_resp.status_code == 200
    planned_id = add_resp.json()["planned_recipes"][0]["id"]

    del_resp = client.delete(
        f"{settings.API_V1_STR}/shopping-lists/{sl.id}/planned-recipes/{planned_id}",
        headers=superuser_token_headers,
    )
    assert del_resp.status_code == 200

    list_resp = client.get(
        f"{settings.API_V1_STR}/shopping-lists/{sl.id}",
        headers=superuser_token_headers,
    )
    assert list_resp.json()["items"] == []
    assert list_resp.json()["planned_recipes"] == []


def test_delete_planned_recipe_partial_aggregate(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Deleting one of two recipes sharing an ingredient reduces (not zeros) the quantity."""
    superuser = crud.get_user_by_email(session=db, email=settings.FIRST_SUPERUSER)
    sl = create_random_shopping_list(db, owner_id=superuser.id)  # type: ignore[union-attr]
    recipe = create_random_recipe(db, owner_id=superuser.id, with_ingredients=True)  # type: ignore[union-attr]
    # Add the same recipe twice (shared ingredients, quantity doubled)
    for _ in range(2):
        client.post(
            f"{settings.API_V1_STR}/shopping-lists/{sl.id}/add-recipe/{recipe.id}",  # type: ignore[attr-defined]
            headers=superuser_token_headers,
        )
    list_resp = client.get(
        f"{settings.API_V1_STR}/shopping-lists/{sl.id}",
        headers=superuser_token_headers,
    )
    planned_id = list_resp.json()["planned_recipes"][0]["id"]

    client.delete(
        f"{settings.API_V1_STR}/shopping-lists/{sl.id}/planned-recipes/{planned_id}",
        headers=superuser_token_headers,
    )

    final_resp = client.get(
        f"{settings.API_V1_STR}/shopping-lists/{sl.id}",
        headers=superuser_token_headers,
    )
    items = final_resp.json()["items"]
    assert len(items) == 2  # still 2 distinct ingredients
    for item in items:
        assert item["quantity"] == 1.0  # back to single-recipe quantity


def test_update_planned_recipe_servings_adjusts_items(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Updating servings_planned scales ingredient quantities accordingly."""
    superuser = crud.get_user_by_email(session=db, email=settings.FIRST_SUPERUSER)
    sl = create_random_shopping_list(db, owner_id=superuser.id)  # type: ignore[union-attr]
    recipe = create_random_recipe(db, owner_id=superuser.id, with_ingredients=True)  # type: ignore[union-attr]
    add_resp = client.post(
        f"{settings.API_V1_STR}/shopping-lists/{sl.id}/add-recipe/{recipe.id}",  # type: ignore[attr-defined]
        headers=superuser_token_headers,
    )
    planned_id = add_resp.json()["planned_recipes"][0]["id"]
    original_servings = add_resp.json()["planned_recipes"][0]["recipe_servings"] or 1

    client.patch(
        f"{settings.API_V1_STR}/shopping-lists/{sl.id}/planned-recipes/{planned_id}",
        headers=superuser_token_headers,
        json={"servings_planned": original_servings * 2},
    )

    list_resp = client.get(
        f"{settings.API_V1_STR}/shopping-lists/{sl.id}",
        headers=superuser_token_headers,
    )
    for item in list_resp.json()["items"]:
        assert item["quantity"] == 2.0  # doubled servings → doubled quantities
