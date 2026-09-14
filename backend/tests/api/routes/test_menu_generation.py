"""The generate and swap endpoints, and their fallbacks to user settings."""

import uuid
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models import IngredientCreate, RecipeCreate, RecipeIngredientCreate, Unit
from tests.utils.utils import random_lower_string

START = date(2026, 4, 6)


def _me(db: Session) -> object:
    user = crud.get_user_by_email(session=db, email=settings.EMAIL_TEST_USER)
    assert user is not None
    return user


def _recipe(
    db: Session,
    owner_id: uuid.UUID,
    *,
    vegan: bool = False,
    cuisine: str | None = None,
    ingredient: str | None = None,
    quantity: float = 1,
    servings: int = 2,
) -> object:
    ingredients = []
    if ingredient:
        ingredients.append(
            RecipeIngredientCreate(
                ingredient_name=ingredient, quantity=quantity, unit=Unit.KILOGRAM
            )
        )
    return crud.create_recipe(
        session=db,
        recipe_in=RecipeCreate(
            title=random_lower_string(),
            servings=servings,
            is_vegan=vegan,
            cuisine_type=cuisine,
            ingredients=ingredients,
        ),
        owner_id=owner_id,
    )


def _priced(db: Session, name: str, amount: str) -> None:
    ingredient = crud.create_ingredient(
        session=db, ingredient_in=IngredientCreate(name=name)
    )
    ingredient.price_amount = Decimal(amount)
    ingredient.price_quantity = 1.0
    ingredient.price_unit = Unit.KILOGRAM
    db.add(ingredient)
    db.commit()


def test_generating_a_menu_creates_a_plan_with_entries(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    me = _me(db)
    for _ in range(5):
        _recipe(db, me.id)  # type: ignore[attr-defined]

    response = client.post(
        f"{settings.API_V1_STR}/meal-plans/generate",
        headers=normal_user_token_headers,
        json={"start_date": START.isoformat(), "days": 5, "include_public": False},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["entries"]) == 5
    assert body["start_date"] == START.isoformat()
    assert body["end_date"] == date(2026, 4, 10).isoformat()


def test_generation_honours_a_dietary_constraint(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    me = _me(db)
    vegan_ids = {str(_recipe(db, me.id, vegan=True).id) for _ in range(3)}  # type: ignore[attr-defined]
    for _ in range(3):
        _recipe(db, me.id, vegan=False)  # type: ignore[attr-defined]

    response = client.post(
        f"{settings.API_V1_STR}/meal-plans/generate",
        headers=normal_user_token_headers,
        json={
            "start_date": START.isoformat(),
            "days": 3,
            "require_vegan": True,
            "include_public": False,
        },
    )
    assert response.status_code == 200
    chosen = {e["recipe_id"] for e in response.json()["entries"]}
    assert chosen <= vegan_ids


def test_generation_with_no_matching_recipes_is_refused(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    me = _me(db)
    _recipe(db, me.id, vegan=False)  # type: ignore[attr-defined]
    response = client.post(
        f"{settings.API_V1_STR}/meal-plans/generate",
        headers=normal_user_token_headers,
        json={
            "start_date": START.isoformat(),
            "days": 3,
            "require_gluten_free": True,
            "require_dairy_free": True,
            "require_vegan": True,
            "include_public": False,
        },
    )
    assert response.status_code == 422


def test_generation_falls_back_to_household_size(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    """The common case is one button with no form, so settings supply defaults."""
    me = _me(db)
    _recipe(db, me.id)  # type: ignore[attr-defined]
    client.put(
        f"{settings.API_V1_STR}/users/me/settings/",
        headers=normal_user_token_headers,
        json={"household_size": 5},
    )

    response = client.post(
        f"{settings.API_V1_STR}/meal-plans/generate",
        headers=normal_user_token_headers,
        json={"start_date": START.isoformat(), "days": 2, "include_public": False},
    )
    assert response.status_code == 200
    assert all(e["servings"] == 5 for e in response.json()["entries"])

    client.put(
        f"{settings.API_V1_STR}/users/me/settings/",
        headers=normal_user_token_headers,
        json={"household_size": 2},
    )


def test_generation_respects_a_budget(client: TestClient, db: Session) -> None:
    """Uses its own account so the library is exactly these six recipes.

    The shared fixture user accumulates recipes from other tests, most of them
    unpriced — and an unpriced recipe is deliberately allowed through a budget,
    so it would mask the ceiling this test exists to check.
    """
    from tests.utils.user import authentication_token_from_email

    email = f"budget-{random_lower_string()}@example.com"
    headers = authentication_token_from_email(client=client, email=email, db=db)
    user = crud.get_user_by_email(session=db, email=email)
    assert user is not None

    beef = f"beef-{random_lower_string()}"
    _priced(db, beef, "5.00")
    for _ in range(6):
        _recipe(db, user.id, ingredient=beef, quantity=1, servings=2)

    response = client.post(
        f"{settings.API_V1_STR}/meal-plans/generate",
        headers=headers,
        json={
            "start_date": START.isoformat(),
            "days": 6,
            "servings": 2,
            "budget": "12.00",
            "include_public": False,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert Decimal(str(body["estimated_total"])) <= Decimal("12.00")
    # 5.00 a meal against a 12.00 budget buys two, not six.
    assert len(body["entries"]) == 2


def test_generation_is_reproducible_for_one_seed(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    me = _me(db)
    for _ in range(8):
        _recipe(db, me.id)  # type: ignore[attr-defined]

    payload = {
        "start_date": START.isoformat(),
        "days": 4,
        "seed": 7,
        "include_public": False,
    }
    first = client.post(
        f"{settings.API_V1_STR}/meal-plans/generate",
        headers=normal_user_token_headers,
        json=payload,
    )
    second = client.post(
        f"{settings.API_V1_STR}/meal-plans/generate",
        headers=normal_user_token_headers,
        json=payload,
    )
    assert [e["recipe_id"] for e in first.json()["entries"]] == [
        e["recipe_id"] for e in second.json()["entries"]
    ]


def test_generation_without_any_recipes_is_refused(
    client: TestClient, db: Session
) -> None:
    """A brand-new account has nothing to compose a menu from."""
    from tests.utils.user import authentication_token_from_email

    email = f"empty-{random_lower_string()}@example.com"
    headers = authentication_token_from_email(client=client, email=email, db=db)
    response = client.post(
        f"{settings.API_V1_STR}/meal-plans/generate",
        headers=headers,
        json={"start_date": START.isoformat(), "days": 3, "include_public": False},
    )
    assert response.status_code == 422


def test_swapping_an_entry_changes_its_recipe(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    me = _me(db)
    for _ in range(4):
        _recipe(db, me.id)  # type: ignore[attr-defined]

    generated = client.post(
        f"{settings.API_V1_STR}/meal-plans/generate",
        headers=normal_user_token_headers,
        json={"start_date": START.isoformat(), "days": 1, "include_public": False},
    ).json()
    plan_id = generated["id"]
    entry = generated["entries"][0]

    swapped = client.post(
        f"{settings.API_V1_STR}/meal-plans/{plan_id}/entries/{entry['id']}/swap",
        headers=normal_user_token_headers,
        json={"start_date": START.isoformat(), "include_public": False},
    )
    assert swapped.status_code == 200
    assert swapped.json()["recipe_id"] != entry["recipe_id"]
    assert swapped.json()["id"] == entry["id"]


def test_swapping_with_no_alternative_is_refused(
    client: TestClient, db: Session
) -> None:
    from tests.utils.user import authentication_token_from_email

    email = f"single-{random_lower_string()}@example.com"
    headers = authentication_token_from_email(client=client, email=email, db=db)
    user = crud.get_user_by_email(session=db, email=email)
    assert user is not None
    _recipe(db, user.id)

    generated = client.post(
        f"{settings.API_V1_STR}/meal-plans/generate",
        headers=headers,
        json={"start_date": START.isoformat(), "days": 1, "include_public": False},
    ).json()
    entry = generated["entries"][0]

    response = client.post(
        f"{settings.API_V1_STR}/meal-plans/{generated['id']}"
        f"/entries/{entry['id']}/swap",
        headers=headers,
        json={"start_date": START.isoformat(), "include_public": False},
    )
    assert response.status_code == 422


def test_swapping_someone_elses_plan_is_refused(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    from tests.utils.user import create_random_user

    stranger = create_random_user(db)
    from app.models import MealPlanCreate

    plan = crud.create_meal_plan(
        session=db,
        plan_in=MealPlanCreate(
            name=random_lower_string(), start_date=START, end_date=START
        ),
        owner_id=stranger.id,
    )
    response = client.post(
        f"{settings.API_V1_STR}/meal-plans/{plan.id}"
        f"/entries/00000000-0000-0000-0000-000000000000/swap",
        headers=normal_user_token_headers,
        json={"start_date": START.isoformat()},
    )
    assert response.status_code == 403
