"""The price-estimation endpoints, including who is allowed to call them."""

from decimal import Decimal
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models import IngredientCreate
from app.models.ingredient import PriceSource
from tests.utils.utils import random_lower_string


def test_estimate_one_price_is_queued(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    ingredient = crud.create_ingredient(
        session=db,
        ingredient_in=IngredientCreate(name=f"kale-{random_lower_string()}"),
    )
    with patch("app.api.routes.ingredients.estimate_ingredient_price") as queued:
        response = client.post(
            f"{settings.API_V1_STR}/ingredients/{ingredient.id}/estimate-price",
            headers=superuser_token_headers,
        )
    assert response.status_code == 200
    queued.assert_called_once()


def test_estimate_one_price_404s_for_an_unknown_ingredient(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/ingredients/"
        "00000000-0000-0000-0000-000000000000/estimate-price",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404


def test_estimate_one_price_is_superuser_only(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    ingredient = crud.create_ingredient(
        session=db,
        ingredient_in=IngredientCreate(name=f"leek-{random_lower_string()}"),
    )
    response = client.post(
        f"{settings.API_V1_STR}/ingredients/{ingredient.id}/estimate-price",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 403


def test_batch_estimate_targets_the_ids_it_is_given(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    ingredient = crud.create_ingredient(
        session=db,
        ingredient_in=IngredientCreate(name=f"fennel-{random_lower_string()}"),
    )
    with patch("app.api.routes.ingredients.estimate_prices_batch") as queued:
        response = client.post(
            f"{settings.API_V1_STR}/ingredients/estimate-prices",
            headers=superuser_token_headers,
            json={"ingredient_ids": [str(ingredient.id)], "currency": "GBP"},
        )
    assert response.status_code == 200
    ids, kwargs = queued.call_args[0][0], queued.call_args[1]
    assert ids == [ingredient.id]
    assert kwargs["currency"] == "GBP"


def test_batch_estimate_with_no_ids_targets_unpriced_ingredients(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """The common case after a bulk import: fill in whatever has no price."""
    unpriced = crud.create_ingredient(
        session=db,
        ingredient_in=IngredientCreate(name=f"chard-{random_lower_string()}"),
    )
    priced = crud.create_ingredient(
        session=db,
        ingredient_in=IngredientCreate(name=f"quince-{random_lower_string()}"),
    )
    priced.price_amount = Decimal("3.00")
    priced.price_source = PriceSource.MANUAL
    db.add(priced)
    db.commit()

    with patch("app.api.routes.ingredients.estimate_prices_batch") as queued:
        response = client.post(
            f"{settings.API_V1_STR}/ingredients/estimate-prices",
            headers=superuser_token_headers,
            json={},
        )
    assert response.status_code == 200
    targeted = queued.call_args[0][0]
    assert unpriced.id in targeted
    assert priced.id not in targeted


def test_batch_estimate_is_superuser_only(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/ingredients/estimate-prices",
        headers=normal_user_token_headers,
        json={},
    )
    assert response.status_code == 403
