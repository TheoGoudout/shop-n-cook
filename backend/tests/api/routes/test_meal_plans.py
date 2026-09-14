"""Meal plans: slots, access control, and turning a week into one shopping list."""

import uuid
from datetime import date, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models import (
    IngredientCreate,
    MealPlanCreate,
    RecipeCreate,
    RecipeIngredientCreate,
    Unit,
)
from tests.utils.user import create_random_user
from tests.utils.utils import random_lower_string

TODAY = date(2026, 3, 2)


def _recipe(
    db: Session,
    owner_id: uuid.UUID,
    *,
    ingredient: str | None = None,
    quantity: float = 500,
    unit: Unit = Unit.GRAM,
    servings: int = 2,
    is_public: bool = False,
) -> object:
    ingredients = []
    if ingredient:
        ingredients.append(
            RecipeIngredientCreate(
                ingredient_name=ingredient, quantity=quantity, unit=unit
            )
        )
    return crud.create_recipe(
        session=db,
        recipe_in=RecipeCreate(
            title=random_lower_string(),
            servings=servings,
            is_public=is_public,
            ingredients=ingredients,
        ),
        owner_id=owner_id,
    )


def _plan(db: Session, owner_id: uuid.UUID, days: int = 7) -> object:
    return crud.create_meal_plan(
        session=db,
        plan_in=MealPlanCreate(
            name=random_lower_string(),
            start_date=TODAY,
            end_date=TODAY + timedelta(days=days - 1),
        ),
        owner_id=owner_id,
    )


def _me(db: Session) -> object:
    user = crud.get_user_by_email(session=db, email=settings.EMAIL_TEST_USER)
    assert user is not None
    return user


def test_create_and_read_a_plan(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/meal-plans/",
        headers=normal_user_token_headers,
        json={
            "name": "Week one",
            "start_date": TODAY.isoformat(),
            "end_date": (TODAY + timedelta(days=6)).isoformat(),
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Week one"
    assert body["entries"] == []
    assert body["shopping_list_id"] is None


def test_a_backwards_date_range_is_rejected(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/meal-plans/",
        headers=normal_user_token_headers,
        json={
            "name": "Backwards",
            "start_date": TODAY.isoformat(),
            "end_date": (TODAY - timedelta(days=1)).isoformat(),
        },
    )
    assert response.status_code == 422


def test_adding_an_entry_pins_a_recipe_to_a_slot(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    me = _me(db)
    recipe = _recipe(db, me.id)  # type: ignore[attr-defined]
    plan = _plan(db, me.id)  # type: ignore[attr-defined]

    response = client.post(
        f"{settings.API_V1_STR}/meal-plans/{plan.id}/entries",  # type: ignore[attr-defined]
        headers=normal_user_token_headers,
        json={
            "recipe_id": str(recipe.id),  # type: ignore[attr-defined]
            "entry_date": TODAY.isoformat(),
            "meal_type": "dinner",
            "servings": 4,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["recipe_title"] == recipe.title  # type: ignore[attr-defined]
    assert body["servings"] == 4
    assert body["meal_type"] == "dinner"


def test_a_plan_cannot_reference_someone_elses_private_recipe(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    stranger = create_random_user(db)
    private_recipe = _recipe(db, stranger.id, is_public=False)
    plan = _plan(db, _me(db).id)  # type: ignore[attr-defined]

    response = client.post(
        f"{settings.API_V1_STR}/meal-plans/{plan.id}/entries",  # type: ignore[attr-defined]
        headers=normal_user_token_headers,
        json={
            "recipe_id": str(private_recipe.id),  # type: ignore[attr-defined]
            "entry_date": TODAY.isoformat(),
        },
    )
    assert response.status_code == 403


def test_a_plan_may_reference_a_public_recipe(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    stranger = create_random_user(db)
    shared = _recipe(db, stranger.id, is_public=True)
    plan = _plan(db, _me(db).id)  # type: ignore[attr-defined]

    response = client.post(
        f"{settings.API_V1_STR}/meal-plans/{plan.id}/entries",  # type: ignore[attr-defined]
        headers=normal_user_token_headers,
        json={
            "recipe_id": str(shared.id),  # type: ignore[attr-defined]
            "entry_date": TODAY.isoformat(),
        },
    )
    assert response.status_code == 200


def test_reading_someone_elses_plan_is_refused(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    stranger = create_random_user(db)
    plan = _plan(db, stranger.id)
    response = client.get(
        f"{settings.API_V1_STR}/meal-plans/{plan.id}",  # type: ignore[attr-defined]
        headers=normal_user_token_headers,
    )
    assert response.status_code == 403


def test_a_plan_lists_only_your_own(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    stranger = create_random_user(db)
    theirs = _plan(db, stranger.id)
    mine = _plan(db, _me(db).id)  # type: ignore[attr-defined]

    response = client.get(
        f"{settings.API_V1_STR}/meal-plans/", headers=normal_user_token_headers
    )
    ids = {p["id"] for p in response.json()["data"]}
    assert str(mine.id) in ids  # type: ignore[attr-defined]
    assert str(theirs.id) not in ids  # type: ignore[attr-defined]


def test_entries_come_back_sorted_by_date(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    me = _me(db)
    plan = _plan(db, me.id)  # type: ignore[attr-defined]
    for offset in (3, 0, 1):
        recipe = _recipe(db, me.id)  # type: ignore[attr-defined]
        client.post(
            f"{settings.API_V1_STR}/meal-plans/{plan.id}/entries",  # type: ignore[attr-defined]
            headers=normal_user_token_headers,
            json={
                "recipe_id": str(recipe.id),  # type: ignore[attr-defined]
                "entry_date": (TODAY + timedelta(days=offset)).isoformat(),
            },
        )

    response = client.get(
        f"{settings.API_V1_STR}/meal-plans/{plan.id}",  # type: ignore[attr-defined]
        headers=normal_user_token_headers,
    )
    dates = [e["entry_date"] for e in response.json()["entries"]]
    assert dates == sorted(dates)


def test_an_entry_can_be_moved_and_rescaled(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    me = _me(db)
    recipe = _recipe(db, me.id)  # type: ignore[attr-defined]
    plan = _plan(db, me.id)  # type: ignore[attr-defined]
    created = client.post(
        f"{settings.API_V1_STR}/meal-plans/{plan.id}/entries",  # type: ignore[attr-defined]
        headers=normal_user_token_headers,
        json={"recipe_id": str(recipe.id), "entry_date": TODAY.isoformat()},  # type: ignore[attr-defined]
    )
    entry_id = created.json()["id"]

    moved = client.patch(
        f"{settings.API_V1_STR}/meal-plans/{plan.id}/entries/{entry_id}",  # type: ignore[attr-defined]
        headers=normal_user_token_headers,
        json={
            "entry_date": (TODAY + timedelta(days=2)).isoformat(),
            "meal_type": "lunch",
            "servings": 6,
        },
    )
    assert moved.status_code == 200
    assert moved.json()["entry_date"] == (TODAY + timedelta(days=2)).isoformat()
    assert moved.json()["meal_type"] == "lunch"
    assert moved.json()["servings"] == 6


def test_an_entry_from_another_plan_is_not_found(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    me = _me(db)
    recipe = _recipe(db, me.id)  # type: ignore[attr-defined]
    plan_a = _plan(db, me.id)  # type: ignore[attr-defined]
    plan_b = _plan(db, me.id)  # type: ignore[attr-defined]
    created = client.post(
        f"{settings.API_V1_STR}/meal-plans/{plan_a.id}/entries",  # type: ignore[attr-defined]
        headers=normal_user_token_headers,
        json={"recipe_id": str(recipe.id), "entry_date": TODAY.isoformat()},  # type: ignore[attr-defined]
    )
    entry_id = created.json()["id"]

    response = client.delete(
        f"{settings.API_V1_STR}/meal-plans/{plan_b.id}/entries/{entry_id}",  # type: ignore[attr-defined]
        headers=normal_user_token_headers,
    )
    assert response.status_code == 404


def test_generating_a_shopping_list_merges_repeated_recipes(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    """A recipe cooked twice in a week is one row, not two."""
    me = _me(db)
    flour = f"flour-{random_lower_string()}"
    recipe = _recipe(db, me.id, ingredient=flour, quantity=500, servings=2)  # type: ignore[attr-defined]
    plan = _plan(db, me.id)  # type: ignore[attr-defined]

    for offset in (0, 3):
        client.post(
            f"{settings.API_V1_STR}/meal-plans/{plan.id}/entries",  # type: ignore[attr-defined]
            headers=normal_user_token_headers,
            json={
                "recipe_id": str(recipe.id),  # type: ignore[attr-defined]
                "entry_date": (TODAY + timedelta(days=offset)).isoformat(),
                "servings": 2,
            },
        )

    response = client.post(
        f"{settings.API_V1_STR}/meal-plans/{plan.id}/shopping-list",  # type: ignore[attr-defined]
        headers=normal_user_token_headers,
    )
    assert response.status_code == 200
    body = response.json()
    matching = [i for i in body["items"] if i["name"] == flour]
    assert len(matching) == 1
    assert matching[0]["quantity"] == 1000


def test_the_generated_list_is_linked_back_to_the_plan(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    me = _me(db)
    recipe = _recipe(db, me.id, ingredient=f"rice-{random_lower_string()}")  # type: ignore[attr-defined]
    plan = _plan(db, me.id)  # type: ignore[attr-defined]
    client.post(
        f"{settings.API_V1_STR}/meal-plans/{plan.id}/entries",  # type: ignore[attr-defined]
        headers=normal_user_token_headers,
        json={"recipe_id": str(recipe.id), "entry_date": TODAY.isoformat()},  # type: ignore[attr-defined]
    )
    generated = client.post(
        f"{settings.API_V1_STR}/meal-plans/{plan.id}/shopping-list",  # type: ignore[attr-defined]
        headers=normal_user_token_headers,
    )
    list_id = generated.json()["id"]

    reread = client.get(
        f"{settings.API_V1_STR}/meal-plans/{plan.id}",  # type: ignore[attr-defined]
        headers=normal_user_token_headers,
    )
    assert reread.json()["shopping_list_id"] == list_id


def test_generating_from_an_empty_plan_is_refused(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    plan = _plan(db, _me(db).id)  # type: ignore[attr-defined]
    response = client.post(
        f"{settings.API_V1_STR}/meal-plans/{plan.id}/shopping-list",  # type: ignore[attr-defined]
        headers=normal_user_token_headers,
    )
    assert response.status_code == 422


def test_a_plan_reports_what_the_week_costs(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    me = _me(db)
    name = f"pasta-{random_lower_string()}"
    ingredient = crud.create_ingredient(
        session=db, ingredient_in=IngredientCreate(name=name)
    )
    ingredient.price_amount = Decimal("2.00")
    ingredient.price_quantity = 1.0
    ingredient.price_unit = Unit.KILOGRAM
    db.add(ingredient)
    db.commit()

    recipe = _recipe(db, me.id, ingredient=name, quantity=500, servings=2)  # type: ignore[attr-defined]
    plan = _plan(db, me.id)  # type: ignore[attr-defined]
    client.post(
        f"{settings.API_V1_STR}/meal-plans/{plan.id}/entries",  # type: ignore[attr-defined]
        headers=normal_user_token_headers,
        json={
            "recipe_id": str(recipe.id),  # type: ignore[attr-defined]
            "entry_date": TODAY.isoformat(),
            "servings": 4,
        },
    )

    response = client.get(
        f"{settings.API_V1_STR}/meal-plans/{plan.id}",  # type: ignore[attr-defined]
        headers=normal_user_token_headers,
    )
    body = response.json()
    # 500 g at 2 servings, doubled to 4 servings = 1 kg = 2.00
    assert Decimal(str(body["estimated_total"])) == Decimal("2.00")
    assert Decimal(str(body["entries"][0]["estimated_cost_per_serving"])) == Decimal(
        "0.50"
    )


def test_deleting_a_plan_leaves_its_generated_list(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    me = _me(db)
    recipe = _recipe(db, me.id, ingredient=f"oats-{random_lower_string()}")  # type: ignore[attr-defined]
    plan = _plan(db, me.id)  # type: ignore[attr-defined]
    client.post(
        f"{settings.API_V1_STR}/meal-plans/{plan.id}/entries",  # type: ignore[attr-defined]
        headers=normal_user_token_headers,
        json={"recipe_id": str(recipe.id), "entry_date": TODAY.isoformat()},  # type: ignore[attr-defined]
    )
    list_id = client.post(
        f"{settings.API_V1_STR}/meal-plans/{plan.id}/shopping-list",  # type: ignore[attr-defined]
        headers=normal_user_token_headers,
    ).json()["id"]

    deleted = client.delete(
        f"{settings.API_V1_STR}/meal-plans/{plan.id}",  # type: ignore[attr-defined]
        headers=normal_user_token_headers,
    )
    assert deleted.status_code == 200

    still_there = client.get(
        f"{settings.API_V1_STR}/shopping-lists/{list_id}",
        headers=normal_user_token_headers,
    )
    assert still_there.status_code == 200
