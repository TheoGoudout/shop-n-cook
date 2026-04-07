import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app import crud
from app.models import IngredientCategory, IngredientCreate, ShoppingListItemCreate, Unit
from tests.utils.ingredient import create_random_ingredient
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
    superuser = crud.get_user_by_email(
        session=db, email=settings.FIRST_SUPERUSER
    )
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
    superuser = crud.get_user_by_email(
        session=db, email=settings.FIRST_SUPERUSER
    )
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
    superuser = crud.get_user_by_email(
        session=db, email=settings.FIRST_SUPERUSER
    )
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
    superuser = crud.get_user_by_email(
        session=db, email=settings.FIRST_SUPERUSER
    )
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
    superuser = crud.get_user_by_email(
        session=db, email=settings.FIRST_SUPERUSER
    )
    sl = create_random_shopping_list(db, owner_id=superuser.id)  # type: ignore[union-attr]
    ingredient = create_random_ingredient(db)
    response = client.post(
        f"{settings.API_V1_STR}/shopping-lists/{sl.id}/items",  # type: ignore[attr-defined]
        headers=superuser_token_headers,
        json={
            "ingredient_id": str(ingredient.id),
            "quantity": 2.0,
            "unit": Unit.PIECE.value,
        },
    )
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["ingredient_name"] == ingredient.name
    assert items[0]["quantity"] == 2.0


def test_add_item_ingredient_not_found(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    superuser = crud.get_user_by_email(
        session=db, email=settings.FIRST_SUPERUSER
    )
    sl = create_random_shopping_list(db, owner_id=superuser.id)  # type: ignore[union-attr]
    response = client.post(
        f"{settings.API_V1_STR}/shopping-lists/{sl.id}/items",  # type: ignore[attr-defined]
        headers=superuser_token_headers,
        json={
            "ingredient_id": str(uuid.uuid4()),
            "quantity": 1.0,
            "unit": Unit.PIECE.value,
        },
    )
    assert response.status_code == 404


def test_update_item_is_checked(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    superuser = crud.get_user_by_email(
        session=db, email=settings.FIRST_SUPERUSER
    )
    sl = create_random_shopping_list(db, owner_id=superuser.id)  # type: ignore[union-attr]
    ingredient = create_random_ingredient(db)
    # add item
    sl = crud.add_item_to_shopping_list(
        session=db,
        shopping_list=sl,  # type: ignore[arg-type]
        item_in=ShoppingListItemCreate(
            ingredient_id=ingredient.id,
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
    superuser = crud.get_user_by_email(
        session=db, email=settings.FIRST_SUPERUSER
    )
    sl = create_random_shopping_list(db, owner_id=superuser.id)  # type: ignore[union-attr]
    ingredient = create_random_ingredient(db)
    sl = crud.add_item_to_shopping_list(
        session=db,
        shopping_list=sl,  # type: ignore[arg-type]
        item_in=ShoppingListItemCreate(
            ingredient_id=ingredient.id,
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
    superuser = crud.get_user_by_email(
        session=db, email=settings.FIRST_SUPERUSER
    )
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
    superuser = crud.get_user_by_email(
        session=db, email=settings.FIRST_SUPERUSER
    )
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
    superuser = crud.get_user_by_email(
        session=db, email=settings.FIRST_SUPERUSER
    )
    sl = create_random_shopping_list(db, owner_id=superuser.id)  # type: ignore[union-attr]
    response = client.post(
        f"{settings.API_V1_STR}/shopping-lists/{sl.id}/add-recipe/{uuid.uuid4()}",  # type: ignore[attr-defined]
        headers=superuser_token_headers,
    )
    assert response.status_code == 404


def test_ingredient_blocked_delete_when_in_recipe(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Deleting an ingredient used in a recipe must return 409."""
    superuser = crud.get_user_by_email(
        session=db, email=settings.FIRST_SUPERUSER
    )
    recipe = create_random_recipe(db, owner_id=superuser.id, with_ingredients=True)  # type: ignore[union-attr]
    ingredient_id = recipe.recipe_ingredients[0].ingredient_id  # type: ignore[attr-defined]
    response = client.delete(
        f"{settings.API_V1_STR}/ingredients/{ingredient_id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 409
