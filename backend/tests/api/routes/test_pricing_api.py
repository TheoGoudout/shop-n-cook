"""Costs as they reach the API surface."""

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models import (
    IngredientCreate,
    RecipeCreate,
    RecipeIngredientCreate,
    ShoppingListCreate,
    Unit,
)
from app.models.ingredient import PriceSource
from tests.utils.user import create_random_user
from tests.utils.utils import random_lower_string


def _priced_ingredient(
    db: Session, name: str, amount: str, quantity: float, unit: Unit
) -> None:
    ingredient = crud.create_ingredient(
        session=db, ingredient_in=IngredientCreate(name=name)
    )
    ingredient.price_amount = Decimal(amount)
    ingredient.price_quantity = quantity
    ingredient.price_unit = unit
    ingredient.price_source = PriceSource.MANUAL
    db.add(ingredient)
    db.commit()


def test_recipe_reports_cost_and_cost_per_serving(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    flour = f"flour-{random_lower_string()}"
    _priced_ingredient(db, flour, "2.00", 1, Unit.KILOGRAM)

    response = client.post(
        f"{settings.API_V1_STR}/recipes/",
        headers=normal_user_token_headers,
        json={
            "title": random_lower_string(),
            "servings": 4,
            "ingredients": [{"ingredient_name": flour, "quantity": 500, "unit": "g"}],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert Decimal(str(body["estimated_cost"])) == Decimal("1.00")
    assert Decimal(str(body["estimated_cost_per_serving"])) == Decimal("0.25")
    assert body["unpriced_ingredient_count"] == 0
    assert body["currency"] == "EUR"
    assert Decimal(str(body["ingredients"][0]["estimated_cost"])) == Decimal("1.00")


def test_unpriced_ingredients_are_counted_not_treated_as_free(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    known = f"sugar-{random_lower_string()}"
    _priced_ingredient(db, known, "1.00", 1, Unit.KILOGRAM)

    response = client.post(
        f"{settings.API_V1_STR}/recipes/",
        headers=normal_user_token_headers,
        json={
            "title": random_lower_string(),
            "servings": 2,
            "ingredients": [
                {"ingredient_name": known, "quantity": 1, "unit": "kg"},
                {
                    "ingredient_name": f"saffron-{random_lower_string()}",
                    "quantity": 1,
                    "unit": "g",
                },
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["unpriced_ingredient_count"] == 1
    # The total covers only what could be priced, and says so via the count.
    assert Decimal(str(body["estimated_cost"])) == Decimal("1.00")


def test_recipe_with_no_priced_ingredients_has_no_total(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/recipes/",
        headers=normal_user_token_headers,
        json={
            "title": random_lower_string(),
            "servings": 2,
            "ingredients": [
                {"ingredient_name": random_lower_string(), "quantity": 1, "unit": "g"}
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["estimated_cost"] is None
    assert body["estimated_cost_per_serving"] is None
    assert body["unpriced_ingredient_count"] == 1


def test_shopping_list_reports_a_running_total(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    rice = f"rice-{random_lower_string()}"
    _priced_ingredient(db, rice, "4.00", 1, Unit.KILOGRAM)

    created = client.post(
        f"{settings.API_V1_STR}/shopping-lists/",
        headers=normal_user_token_headers,
        json={"name": random_lower_string()},
    )
    assert created.status_code == 200
    list_id = created.json()["id"]

    added = client.post(
        f"{settings.API_V1_STR}/shopping-lists/{list_id}/items",
        headers=normal_user_token_headers,
        json={"name": rice, "quantity": 500, "unit": "g"},
    )
    assert added.status_code == 200
    body = added.json()
    assert Decimal(str(body["estimated_total"])) == Decimal("2.00")
    assert body["unpriced_item_count"] == 0
    assert body["currency"] == "EUR"


def test_user_settings_round_trip_a_budget(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = client.put(
        f"{settings.API_V1_STR}/users/me/settings/",
        headers=normal_user_token_headers,
        json={"budget_amount": "75.50", "currency": "GBP"},
    )
    assert response.status_code == 200
    body = response.json()
    assert Decimal(str(body["budget_amount"])) == Decimal("75.50")
    assert body["currency"] == "GBP"


def test_budget_defaults_to_unset(db: Session) -> None:
    """A fresh user has no budget and is denominated in euros.

    Uses its own user rather than the shared fixture, whose settings other
    tests in this module deliberately change.
    """
    user = create_random_user(db)
    user_settings = crud.get_or_create_user_settings(session=db, user_id=user.id)
    assert user_settings.budget_amount is None
    assert user_settings.currency == "EUR"


def test_a_negative_budget_is_rejected(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = client.put(
        f"{settings.API_V1_STR}/users/me/settings/",
        headers=normal_user_token_headers,
        json={"budget_amount": "-10.00"},
    )
    assert response.status_code == 422


def test_ingredient_price_is_editable_by_a_superuser(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    name = f"butter-{random_lower_string()}"
    ingredient = crud.create_ingredient(
        session=db, ingredient_in=IngredientCreate(name=name)
    )
    response = client.patch(
        f"{settings.API_V1_STR}/ingredients/{ingredient.id}",
        headers=superuser_token_headers,
        json={"price_amount": "8.40", "price_quantity": 1, "price_unit": "kg"},
    )
    assert response.status_code == 200
    body = response.json()
    assert Decimal(str(body["price_amount"])) == Decimal("8.4000")
    assert body["price_unit"] == "kg"


def test_recipe_cost_scales_with_planned_servings(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    """A recipe for 2 planned at 4 servings must cost twice as much."""
    pasta = f"pasta-{random_lower_string()}"
    _priced_ingredient(db, pasta, "2.00", 1, Unit.KILOGRAM)

    recipe = crud.create_recipe(
        session=db,
        recipe_in=RecipeCreate(
            title=random_lower_string(),
            servings=2,
            ingredients=[
                RecipeIngredientCreate(
                    ingredient_name=pasta, quantity=500, unit=Unit.GRAM
                )
            ],
        ),
        owner_id=crud.get_user_by_email(session=db, email=settings.EMAIL_TEST_USER).id,  # type: ignore[union-attr]
    )
    sl = crud.create_shopping_list(
        session=db,
        list_in=ShoppingListCreate(name=random_lower_string()),
        owner_id=recipe.owner_id,
    )

    response = client.post(
        f"{settings.API_V1_STR}/shopping-lists/{sl.id}/add-recipe/{recipe.id}?servings=4",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 200
    planned = response.json()["planned_recipes"][0]
    assert Decimal(str(planned["estimated_cost"])) == Decimal("2.00")
