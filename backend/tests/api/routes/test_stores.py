"""Store and per-store price endpoints, and the basket comparison."""

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.core.stores_seed import DEFAULT_STORES
from app.models import IngredientCreate, ShoppingListCreate, StoreCreate, Unit
from app.models.store import IngredientPriceCreate
from tests.utils.utils import random_lower_string


def _store(db: Session, index: float = 1.0) -> object:
    slug = f"store-{random_lower_string()}"
    return crud.create_store(
        session=db,
        store_in=StoreCreate(name=slug.title(), slug=slug, price_index=index),
    )


def _priced_ingredient(db: Session, amount: str) -> object:
    ingredient = crud.create_ingredient(
        session=db,
        ingredient_in=IngredientCreate(name=f"item-{random_lower_string()}"),
    )
    ingredient.price_amount = Decimal(amount)
    ingredient.price_quantity = 1.0
    ingredient.price_unit = Unit.KILOGRAM
    db.add(ingredient)
    db.commit()
    return ingredient


def test_the_default_retailers_are_seeded(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/stores/", headers=normal_user_token_headers
    )
    assert response.status_code == 200
    slugs = {s["slug"] for s in response.json()["data"]}
    for slug, _, _ in DEFAULT_STORES:
        assert slug in slugs


def test_listing_stores_requires_a_login(client: TestClient) -> None:
    assert client.get(f"{settings.API_V1_STR}/stores/").status_code == 401


def test_creating_a_store_is_superuser_only(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/stores/",
        headers=normal_user_token_headers,
        json={"name": "Nope", "slug": f"nope-{random_lower_string()}"},
    )
    assert response.status_code == 403


def test_a_duplicate_slug_is_rejected(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    slug = f"dup-{random_lower_string()}"
    payload = {"name": "Dup", "slug": slug}
    first = client.post(
        f"{settings.API_V1_STR}/stores/",
        headers=superuser_token_headers,
        json=payload,
    )
    assert first.status_code == 200
    second = client.post(
        f"{settings.API_V1_STR}/stores/",
        headers=superuser_token_headers,
        json=payload,
    )
    assert second.status_code == 409


def test_setting_a_store_price_is_an_upsert(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    ingredient = _priced_ingredient(db, "2.00")
    store = _store(db)
    url = f"{settings.API_V1_STR}/ingredients/{ingredient.id}/prices"  # type: ignore[attr-defined]

    first = client.put(
        url,
        headers=superuser_token_headers,
        json={
            "store_id": str(store.id),  # type: ignore[attr-defined]
            "price_amount": "3.00",
            "price_quantity": 1,
            "price_unit": "kg",
        },
    )
    assert first.status_code == 200

    second = client.put(
        url,
        headers=superuser_token_headers,
        json={
            "store_id": str(store.id),  # type: ignore[attr-defined]
            "price_amount": "4.00",
            "price_quantity": 1,
            "price_unit": "kg",
        },
    )
    assert second.status_code == 200
    assert Decimal(str(second.json()["price_amount"])) == Decimal("4.0000")

    listed = client.get(url, headers=superuser_token_headers)
    assert listed.json()["count"] == 1


def test_a_price_for_an_unknown_store_is_rejected(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    ingredient = _priced_ingredient(db, "2.00")
    response = client.put(
        f"{settings.API_V1_STR}/ingredients/{ingredient.id}/prices",  # type: ignore[attr-defined]
        headers=superuser_token_headers,
        json={
            "store_id": "00000000-0000-0000-0000-000000000000",
            "price_amount": "3.00",
            "price_quantity": 1,
            "price_unit": "kg",
        },
    )
    assert response.status_code == 404


def test_selecting_a_store_changes_what_a_list_costs(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    ingredient = _priced_ingredient(db, "10.00")
    discounter = _store(db, index=0.5)

    created = client.post(
        f"{settings.API_V1_STR}/shopping-lists/",
        headers=normal_user_token_headers,
        json={"name": random_lower_string()},
    )
    list_id = created.json()["id"]
    client.post(
        f"{settings.API_V1_STR}/shopping-lists/{list_id}/items",
        headers=normal_user_token_headers,
        json={"name": ingredient.name, "quantity": 1, "unit": "kg"},  # type: ignore[attr-defined]
    )

    before = client.get(
        f"{settings.API_V1_STR}/shopping-lists/{list_id}",
        headers=normal_user_token_headers,
    )
    assert Decimal(str(before.json()["estimated_total"])) == Decimal("10.00")

    client.put(
        f"{settings.API_V1_STR}/users/me/settings/",
        headers=normal_user_token_headers,
        json={"preferred_store_id": str(discounter.id)},  # type: ignore[attr-defined]
    )

    after = client.get(
        f"{settings.API_V1_STR}/shopping-lists/{list_id}",
        headers=normal_user_token_headers,
    )
    assert Decimal(str(after.json()["estimated_total"])) == Decimal("5.00")

    # Leave the shared fixture user as we found it.
    client.put(
        f"{settings.API_V1_STR}/users/me/settings/",
        headers=normal_user_token_headers,
        json={"preferred_store_id": None},
    )


def test_store_comparison_ranks_cheapest_first(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    ingredient = _priced_ingredient(db, "10.00")
    created = client.post(
        f"{settings.API_V1_STR}/shopping-lists/",
        headers=normal_user_token_headers,
        json={"name": random_lower_string()},
    )
    list_id = created.json()["id"]
    client.post(
        f"{settings.API_V1_STR}/shopping-lists/{list_id}/items",
        headers=normal_user_token_headers,
        json={"name": ingredient.name, "quantity": 1, "unit": "kg"},  # type: ignore[attr-defined]
    )

    response = client.get(
        f"{settings.API_V1_STR}/shopping-lists/{list_id}/store-comparison",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 200
    body = response.json()
    totals = [
        Decimal(str(e["estimated_total"]))
        for e in body["data"]
        if e["estimated_total"] is not None
    ]
    assert totals == sorted(totals)
    assert body["cheapest_store_id"] == body["data"][0]["store_id"]


def test_store_comparison_refuses_someone_elses_list(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    from tests.utils.user import create_random_user

    stranger = create_random_user(db)
    other_list = crud.create_shopping_list(
        session=db,
        list_in=ShoppingListCreate(name=random_lower_string()),
        owner_id=stranger.id,
    )
    response = client.get(
        f"{settings.API_V1_STR}/shopping-lists/{other_list.id}/store-comparison",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 403


def test_updating_a_store_changes_its_index(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    store = _store(db, index=1.0)
    response = client.patch(
        f"{settings.API_V1_STR}/stores/{store.id}",  # type: ignore[attr-defined]
        headers=superuser_token_headers,
        json={"price_index": 0.75, "is_active": False},
    )
    assert response.status_code == 200
    assert response.json()["price_index"] == 0.75
    assert response.json()["is_active"] is False


def test_an_inactive_store_is_hidden_by_default(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    store = _store(db)
    client.patch(
        f"{settings.API_V1_STR}/stores/{store.id}",  # type: ignore[attr-defined]
        headers=superuser_token_headers,
        json={"is_active": False},
    )
    active = client.get(
        f"{settings.API_V1_STR}/stores/", headers=superuser_token_headers
    )
    assert store.id not in {s["id"] for s in active.json()["data"]}  # type: ignore[attr-defined]

    everything = client.get(
        f"{settings.API_V1_STR}/stores/?active_only=false",
        headers=superuser_token_headers,
    )
    assert str(store.id) in {s["id"] for s in everything.json()["data"]}  # type: ignore[attr-defined]


def test_deleting_a_store_removes_its_prices(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    ingredient = _priced_ingredient(db, "2.00")
    store = _store(db)
    crud.upsert_ingredient_price(
        session=db,
        ingredient=ingredient,  # type: ignore[arg-type]
        price_in=IngredientPriceCreate(
            store_id=store.id,  # type: ignore[attr-defined]
            price_amount=Decimal("3.00"),
            price_quantity=1.0,
            price_unit=Unit.KILOGRAM,
        ),
    )
    response = client.delete(
        f"{settings.API_V1_STR}/stores/{store.id}",  # type: ignore[attr-defined]
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    remaining = crud.get_ingredient_prices(
        session=db,
        ingredient_id=ingredient.id,  # type: ignore[attr-defined]
    )
    assert remaining == []


def test_deleting_a_store_price_falls_back_to_the_baseline(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    ingredient = _priced_ingredient(db, "2.00")
    store = _store(db)
    crud.upsert_ingredient_price(
        session=db,
        ingredient=ingredient,  # type: ignore[arg-type]
        price_in=IngredientPriceCreate(
            store_id=store.id,  # type: ignore[attr-defined]
            price_amount=Decimal("3.00"),
            price_quantity=1.0,
            price_unit=Unit.KILOGRAM,
        ),
    )
    response = client.delete(
        f"{settings.API_V1_STR}/ingredients/{ingredient.id}/prices/{store.id}",  # type: ignore[attr-defined]
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    assert (
        crud.get_ingredient_price(
            session=db,
            ingredient_id=ingredient.id,  # type: ignore[attr-defined]
            store_id=store.id,  # type: ignore[attr-defined]
        )
        is None
    )


def test_unknown_ids_give_404s(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    missing = "00000000-0000-0000-0000-000000000000"
    ingredient = _priced_ingredient(db, "2.00")

    assert (
        client.patch(
            f"{settings.API_V1_STR}/stores/{missing}",
            headers=superuser_token_headers,
            json={"price_index": 1.0},
        ).status_code
        == 404
    )
    assert (
        client.delete(
            f"{settings.API_V1_STR}/stores/{missing}", headers=superuser_token_headers
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"{settings.API_V1_STR}/ingredients/{missing}/prices",
            headers=superuser_token_headers,
        ).status_code
        == 404
    )
    assert (
        client.delete(
            f"{settings.API_V1_STR}/ingredients/{ingredient.id}/prices/{missing}",  # type: ignore[attr-defined]
            headers=superuser_token_headers,
        ).status_code
        == 404
    )
