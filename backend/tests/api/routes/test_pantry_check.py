"""Checking what is already at home before shopping.

Eight tomatoes needed with three in the cupboard means five to buy — and
everything downstream of the list (cost, store comparison, export) should see
five, while the recipes keep saying eight.
"""

import uuid
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models import (
    IngredientCreate,
    RecipeCreate,
    RecipeIngredientCreate,
    ShoppingList,
    ShoppingListCreate,
    ShoppingListItemCreate,
    Unit,
)
from app.models.ingredient import PriceSource
from tests.utils.user import create_random_user
from tests.utils.utils import random_lower_string

LISTS = f"{settings.API_V1_STR}/shopping-lists"


def _own_list(db: Session) -> ShoppingList:
    superuser = crud.get_user_by_email(session=db, email=settings.FIRST_SUPERUSER)
    assert superuser is not None
    return crud.create_shopping_list(
        session=db,
        list_in=ShoppingListCreate(name=random_lower_string()),
        owner_id=superuser.id,
    )


def _add(db: Session, sl: ShoppingList, name: str, qty: float, unit: Unit) -> None:
    crud.add_item_to_shopping_list(
        session=db,
        shopping_list=sl,
        item_in=ShoppingListItemCreate(name=name, quantity=qty, unit=unit),
    )


def _item(body: dict, name: str) -> dict:  # type: ignore[type-arg]
    return next(i for i in body["items"] if i["name"] == name)


def _check(
    client: TestClient,
    headers: dict[str, str],
    sl: ShoppingList,
    entries: dict[uuid.UUID, float],
) -> dict:  # type: ignore[type-arg]
    response = client.put(
        f"{LISTS}/{sl.id}/pantry-check",
        headers=headers,
        json={
            "items": [
                {"item_id": str(item_id), "quantity_at_home": qty}
                for item_id, qty in entries.items()
            ]
        },
    )
    assert response.status_code == 200, response.text
    return response.json()  # type: ignore[no-any-return]


def test_new_list_is_not_yet_checked(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    sl = _own_list(db)
    _add(db, sl, "tomato", 8, Unit.PIECE)
    body = client.get(f"{LISTS}/{sl.id}", headers=superuser_token_headers).json()
    assert body["pantry_checked_at"] is None
    tomato = _item(body, "tomato")
    assert tomato["quantity_at_home"] == 0
    assert tomato["quantity_to_buy"] == 8


def test_what_is_at_home_is_subtracted(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    sl = _own_list(db)
    _add(db, sl, "tomato", 8, Unit.PIECE)
    body = _check(client, superuser_token_headers, sl, {sl.items[0].id: 3})
    tomato = _item(body, "tomato")
    assert tomato["quantity"] == 8
    assert tomato["quantity_at_home"] == 3
    assert tomato["quantity_to_buy"] == 5
    assert body["pantry_checked_at"] is not None


def test_empty_check_still_marks_the_list_checked(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    sl = _own_list(db)
    body = _check(client, superuser_token_headers, sl, {})
    assert body["pantry_checked_at"] is not None


def test_more_at_home_than_needed_buys_nothing(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    sl = _own_list(db)
    _add(db, sl, "egg", 4, Unit.PIECE)
    body = _check(client, superuser_token_headers, sl, {sl.items[0].id: 12})
    assert _item(body, "egg")["quantity_to_buy"] == 0


def test_cost_covers_only_what_is_bought(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    covered = f"salt-{random_lower_string()}"
    partial = f"tomato-{random_lower_string()}"
    for name in (covered, partial):
        ingredient = crud.create_ingredient(
            session=db, ingredient_in=IngredientCreate(name=name)
        )
        ingredient.price_amount = Decimal("0.50")
        ingredient.price_quantity = 1
        ingredient.price_unit = Unit.PIECE
        ingredient.price_source = PriceSource.MANUAL
        db.add(ingredient)
    db.commit()

    sl = _own_list(db)
    _add(db, sl, covered, 1, Unit.PIECE)
    _add(db, sl, partial, 8, Unit.PIECE)
    ids = {item.name: item.id for item in sl.items}
    body = _check(
        client, superuser_token_headers, sl, {ids[covered]: 1, ids[partial]: 3}
    )

    assert Decimal(str(_item(body, partial)["estimated_cost"])) == Decimal("2.50")
    assert Decimal(str(_item(body, covered)["estimated_cost"])) == Decimal("0")
    assert Decimal(str(body["estimated_total"])) == Decimal("2.50")
    assert body["unpriced_item_count"] == 0


def test_covered_item_is_not_counted_as_unpriced(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    sl = _own_list(db)
    _add(db, sl, f"mystery-{random_lower_string()}", 2, Unit.PIECE)
    body = _check(client, superuser_token_headers, sl, {sl.items[0].id: 2})
    assert body["unpriced_item_count"] == 0


def test_export_and_store_comparison_use_the_remainder(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    sl = _own_list(db)
    _add(db, sl, "tomato", 8, Unit.PIECE)
    _add(db, sl, "salt", 1, Unit.PINCH)
    ids = {item.name: item.id for item in sl.items}
    _check(client, superuser_token_headers, sl, {ids["tomato"]: 3, ids["salt"]: 1})

    export = client.post(
        f"{LISTS}/{sl.id}/export", headers=superuser_token_headers, json={}
    ).json()
    lines = [item for group in export["groups"] for item in group["items"]]
    assert [(line["name"], line["quantity"]) for line in lines] == [("tomato", 5)]

    comparison = client.get(
        f"{LISTS}/{sl.id}/store-comparison", headers=superuser_token_headers
    )
    assert comparison.status_code == 200


def test_recipe_changes_keep_what_is_at_home(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """The need moves with the recipes; the cupboard does not."""
    superuser = crud.get_user_by_email(session=db, email=settings.FIRST_SUPERUSER)
    assert superuser is not None
    recipe = crud.create_recipe(
        session=db,
        recipe_in=RecipeCreate(
            title=random_lower_string(),
            servings=2,
            ingredients=[
                RecipeIngredientCreate(
                    ingredient_name="tomato", quantity=4, unit=Unit.PIECE
                )
            ],
        ),
        owner_id=superuser.id,
    )
    sl = _own_list(db)
    added = client.post(
        f"{LISTS}/{sl.id}/add-recipe/{recipe.id}", headers=superuser_token_headers
    ).json()
    tomato_id = _item(added, "tomato")["id"]
    planned_id = added["planned_recipes"][0]["id"]
    _check(client, superuser_token_headers, sl, {uuid.UUID(tomato_id): 3})

    client.patch(
        f"{LISTS}/{sl.id}/planned-recipes/{planned_id}",
        headers=superuser_token_headers,
        json={"servings_planned": 4},
    )
    tomato = _item(
        client.get(f"{LISTS}/{sl.id}", headers=superuser_token_headers).json(),
        "tomato",
    )
    assert tomato["quantity"] == 8
    assert tomato["quantity_at_home"] == 3
    assert tomato["quantity_to_buy"] == 5


def test_unit_change_carries_what_is_at_home(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    sl = _own_list(db)
    _add(db, sl, "flour", 1, Unit.KILOGRAM)
    item_id = sl.items[0].id
    _check(client, superuser_token_headers, sl, {item_id: 0.25})

    response = client.put(
        f"{LISTS}/{sl.id}/items/{item_id}",
        headers=superuser_token_headers,
        json={"quantity": 1000, "unit": Unit.GRAM.value},
    )
    assert response.status_code == 200
    assert response.json()["quantity_at_home"] == 250
    assert response.json()["quantity_to_buy"] == 750


def test_unit_change_without_conversion_forgets_what_is_at_home(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    sl = _own_list(db)
    _add(db, sl, "garlic", 3, Unit.CLOVE)
    item_id = sl.items[0].id
    _check(client, superuser_token_headers, sl, {item_id: 2})

    response = client.put(
        f"{LISTS}/{sl.id}/items/{item_id}",
        headers=superuser_token_headers,
        json={"unit": Unit.PIECE.value},
    )
    assert response.json()["quantity_at_home"] == 0


def test_at_home_can_be_set_on_a_single_item(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    sl = _own_list(db)
    _add(db, sl, "milk", 2, Unit.LITER)
    response = client.put(
        f"{LISTS}/{sl.id}/items/{sl.items[0].id}",
        headers=superuser_token_headers,
        json={"quantity_at_home": 0.5},
    )
    assert response.json()["quantity_to_buy"] == 1.5


def test_rejects_negative_quantities(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    sl = _own_list(db)
    _add(db, sl, "rice", 1, Unit.KILOGRAM)
    response = client.put(
        f"{LISTS}/{sl.id}/pantry-check",
        headers=superuser_token_headers,
        json={"items": [{"item_id": str(sl.items[0].id), "quantity_at_home": -1}]},
    )
    assert response.status_code == 422


def test_item_from_another_list_is_404_and_changes_nothing(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    sl = _own_list(db)
    _add(db, sl, "rice", 1, Unit.KILOGRAM)
    other = _own_list(db)
    _add(db, other, "pasta", 1, Unit.KILOGRAM)
    response = client.put(
        f"{LISTS}/{sl.id}/pantry-check",
        headers=superuser_token_headers,
        json={
            "items": [
                {"item_id": str(sl.items[0].id), "quantity_at_home": 1},
                {"item_id": str(other.items[0].id), "quantity_at_home": 1},
            ]
        },
    )
    assert response.status_code == 404
    db.refresh(sl)
    assert sl.items[0].quantity_at_home == 0
    assert sl.pantry_checked_at is None


def test_other_users_list_is_forbidden(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    stranger = create_random_user(db)
    sl = crud.create_shopping_list(
        session=db,
        list_in=ShoppingListCreate(name=random_lower_string()),
        owner_id=stranger.id,
    )
    response = client.put(
        f"{LISTS}/{sl.id}/pantry-check",
        headers=normal_user_token_headers,
        json={"items": []},
    )
    assert response.status_code == 403


def test_rename_merge_sums_what_is_at_home(db: Session) -> None:
    sl = _own_list(db)
    old = f"tomate-{random_lower_string()}"
    new = f"tomato-{random_lower_string()}"
    _add(db, sl, old, 4, Unit.PIECE)
    _add(db, sl, new, 4, Unit.PIECE)
    for item in sl.items:
        item.quantity_at_home = 1
        db.add(item)
    db.commit()

    crud.rename_ingredient_references(db, old, new)
    db.refresh(sl)
    assert len(sl.items) == 1
    assert sl.items[0].quantity == 8
    assert sl.items[0].quantity_at_home == 2
