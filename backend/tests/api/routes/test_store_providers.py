"""Store endpoints backed by a provider, and the export that needs no store.

The contract worth protecting after collapsing store and shop into one idea:
there is exactly one store concept, no store is selected by default, and every
provider-backed feature is gated on what that store's provider can actually do.
"""

import uuid
from decimal import Decimal
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models import (
    IngredientCategory,
    IngredientUpdate,
    ShoppingList,
    ShoppingListItemCreate,
    Unit,
    User,
)
from app.models.store import StoreCreate
from app.services.store_providers.errors import ProviderUnavailableError
from app.services.store_providers.models import StoreProduct
from tests.utils.shopping_list import create_random_shopping_list
from tests.utils.user import authentication_token_from_email, create_random_user
from tests.utils.utils import random_lower_string

STORES = f"{settings.API_V1_STR}/stores"
LISTS = f"{settings.API_V1_STR}/shopping-lists"


def _list_with_items(db: Session, *, owner: User | None = None) -> ShoppingList:
    user = owner or create_random_user(db)
    shopping_list = create_random_shopping_list(db, user.id)
    assert isinstance(shopping_list, ShoppingList)
    for name, quantity, unit in [
        ("tomates cerises", 500, Unit.GRAM),
        ("lait demi-écrémé", 1, Unit.LITER),
    ]:
        crud.add_item_to_shopping_list(
            session=db,
            shopping_list=shopping_list,
            item_in=ShoppingListItemCreate(name=name, quantity=quantity, unit=unit),
        )
    db.refresh(shopping_list)
    return shopping_list


def _store(db: Session, *, provider_slug: str | None) -> uuid.UUID:
    store = crud.create_store(
        session=db,
        store_in=StoreCreate(
            slug=f"test-{random_lower_string()[:8]}",
            name="Test Store",
            provider_slug=provider_slug,
        ),
    )
    return store.id


class TestStoreCapabilities:
    def test_seeded_stores_expose_what_their_provider_can_do(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        response = client.get(f"{STORES}/", headers=superuser_token_headers)
        assert response.status_code == 200
        by_slug = {s["slug"]: s for s in response.json()["data"]}

        # Carrefour is extension-only: no server search, basket via the browser.
        carrefour = by_slug["carrefour"]
        assert carrefour["provider_slug"] == "carrefour"
        assert carrefour["requires_extension"] is True
        assert carrefour["can_refresh_prices"] is False

        # Auchan is searchable but priceless without a branch session.
        auchan = by_slug["auchan"]
        assert "search" in auchan["capabilities"]
        assert auchan["can_refresh_prices"] is False

        # A chain with no integration is still a perfectly good store.
        lidl = by_slug["lidl"]
        assert lidl["provider_slug"] is None
        assert lidl["capabilities"] == []

    def test_a_stale_provider_slug_does_not_break_the_listing(
        self, client: TestClient, db: Session, superuser_token_headers: dict[str, str]
    ) -> None:
        """A slug this build no longer registers degrades to a curated store."""
        _store(db, provider_slug="a-provider-that-was-removed")
        response = client.get(
            f"{STORES}/", headers=superuser_token_headers, params={"limit": 200}
        )
        assert response.status_code == 200


class TestRefreshPrices:
    def test_writes_provider_prices_into_the_price_book(
        self, client: TestClient, db: Session, superuser_token_headers: dict[str, str]
    ) -> None:
        ingredient, _ = crud.get_or_create_ingredient(db, "tomates cerises")
        crud.update_ingredient(
            session=db,
            ingredient=ingredient,
            update_in=IngredientUpdate(category=IngredientCategory.PRODUCE),
        )
        store_id = _store(db, provider_slug="openprices")

        product = StoreProduct(
            sku="1",
            name="Tomates cerises 250g",
            price=Decimal("2.49"),
            pack_quantity=250,
            pack_unit=Unit.GRAM,
        )
        with (
            patch(
                "app.services.store_providers.families.openprices."
                "OpenPricesProvider.search",
                return_value=[product],
            ),
            patch(
                "app.services.store_providers.families.openprices."
                "OpenPricesProvider.attach_prices",
                side_effect=lambda products, **_: list(products),
            ),
        ):
            response = client.post(
                f"{STORES}/{store_id}/refresh-prices",
                headers=superuser_token_headers,
                # The catalogue is ordered by name and grows across the
                # session, so a small limit can page past the ingredient
                # under test entirely.
                params={"limit": 2000},
            )
        assert response.status_code == 200, response.text
        assert response.json()["refreshed_count"] >= 1

        stored = crud.get_ingredient_price(
            session=db, ingredient_id=ingredient.id, store_id=store_id
        )
        assert stored is not None
        assert stored.price_amount == Decimal("2.49")
        assert stored.price_unit is Unit.GRAM

    def test_unreachable_retailer_degrades_rather_than_failing(
        self, client: TestClient, db: Session, superuser_token_headers: dict[str, str]
    ) -> None:
        crud.get_or_create_ingredient(db, "tomates cerises")
        store_id = _store(db, provider_slug="openprices")
        with patch(
            "app.services.store_providers.families.openprices."
            "OpenPricesProvider.search",
            side_effect=ProviderUnavailableError("503"),
        ):
            response = client.post(
                f"{STORES}/{store_id}/refresh-prices",
                headers=superuser_token_headers,
                params={"limit": 5},
            )
        assert response.status_code == 200
        body = response.json()
        assert body["stopped_early"] is True
        assert body["refreshed_count"] == 0
        assert all(s["reason"] == "store_unavailable" for s in body["skipped"])

    def test_a_store_with_no_provider_is_409(
        self, client: TestClient, db: Session, superuser_token_headers: dict[str, str]
    ) -> None:
        store_id = _store(db, provider_slug=None)
        response = client.post(
            f"{STORES}/{store_id}/refresh-prices", headers=superuser_token_headers
        )
        assert response.status_code == 409
        assert "curated by hand" in response.json()["detail"]

    def test_a_provider_that_cannot_price_is_409(
        self, client: TestClient, db: Session, superuser_token_headers: dict[str, str]
    ) -> None:
        store_id = _store(db, provider_slug="auchan")
        response = client.post(
            f"{STORES}/{store_id}/refresh-prices", headers=superuser_token_headers
        )
        assert response.status_code == 409

    def test_regular_users_cannot_refresh(
        self, client: TestClient, db: Session, normal_user_token_headers: dict[str, str]
    ) -> None:
        """IngredientPrice rows are shared, so a refresh edits common data."""
        store_id = _store(db, provider_slug="openprices")
        response = client.post(
            f"{STORES}/{store_id}/refresh-prices", headers=normal_user_token_headers
        )
        assert response.status_code == 403


class TestCart:
    def test_extension_store_returns_a_plan(
        self, client: TestClient, db: Session, superuser_token_headers: dict[str, str]
    ) -> None:
        store_id = _store(db, provider_slug="carrefour")
        shopping_list = _list_with_items(db)
        response = client.post(
            f"{STORES}/{store_id}/cart",
            headers=superuser_token_headers,
            json={"shopping_list_id": str(shopping_list.id), "branch_id": "drive-12"},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["transport"] == "extension"
        assert body["plan"]["origin"] == "https://www.carrefour.fr"
        assert body["plan"]["branch_id"] == "drive-12"
        assert len(body["plan"]["entries"]) == 2

    def test_store_without_a_provider_is_409(
        self, client: TestClient, db: Session, superuser_token_headers: dict[str, str]
    ) -> None:
        store_id = _store(db, provider_slug=None)
        shopping_list = _list_with_items(db)
        response = client.post(
            f"{STORES}/{store_id}/cart",
            headers=superuser_token_headers,
            json={"shopping_list_id": str(shopping_list.id)},
        )
        assert response.status_code == 409

    def test_unknown_store_is_404(
        self, client: TestClient, db: Session, superuser_token_headers: dict[str, str]
    ) -> None:
        shopping_list = _list_with_items(db)
        response = client.post(
            f"{STORES}/{uuid.uuid4()}/cart",
            headers=superuser_token_headers,
            json={"shopping_list_id": str(shopping_list.id)},
        )
        assert response.status_code == 404


class TestExport:
    """Needs no store at all — which is the default state of the app."""

    def test_exports_without_any_store_selected(
        self, client: TestClient, db: Session, superuser_token_headers: dict[str, str]
    ) -> None:
        shopping_list = _list_with_items(db)
        response = client.post(
            f"{LISTS}/{shopping_list.id}/export",
            headers=superuser_token_headers,
            json={},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["item_count"] == 2
        assert "tomates cerises" in body["content"]

    def test_layout_changes_the_walking_order(
        self, client: TestClient, db: Session, superuser_token_headers: dict[str, str]
    ) -> None:
        shopping_list = _list_with_items(db)
        responses = {
            layout: client.post(
                f"{LISTS}/{shopping_list.id}/export",
                headers=superuser_token_headers,
                json={"layout": layout},
            )
            for layout in ("market", "supermarket")
        }
        for response in responses.values():
            assert response.status_code == 200
        assert responses["market"].json()["store_slug"] == "market"
        assert responses["supermarket"].json()["store_slug"] == "supermarket"

    def test_csv_format(
        self, client: TestClient, db: Session, superuser_token_headers: dict[str, str]
    ) -> None:
        shopping_list = _list_with_items(db)
        response = client.post(
            f"{LISTS}/{shopping_list.id}/export",
            headers=superuser_token_headers,
            json={"format": "csv"},
        )
        assert response.json()["content"].startswith("category,item,quantity,unit,note")

    def test_household_member_can_export_a_shared_list(
        self, client: TestClient, db: Session
    ) -> None:
        from app.models import HouseholdCreate, HouseholdMember, HouseholdRole

        owner = create_random_user(db)
        crud.create_household(
            session=db, household_in=HouseholdCreate(name="Chez Nous"), owner=owner
        )
        member_headers = authentication_token_from_email(
            client=client, email="export-member@example.com", db=db
        )
        member = crud.get_user_by_email(session=db, email="export-member@example.com")
        assert member is not None
        membership = crud.get_membership(session=db, user_id=owner.id)
        assert membership is not None
        db.add(
            HouseholdMember(
                household_id=membership.household_id,
                user_id=member.id,
                role=HouseholdRole.MEMBER,
            )
        )
        db.commit()

        shopping_list = _list_with_items(db, owner=owner)
        response = client.post(
            f"{LISTS}/{shopping_list.id}/export",
            headers=member_headers,
            json={},
        )
        assert response.status_code == 200, response.text

    def test_a_stranger_is_refused(self, client: TestClient, db: Session) -> None:
        shopping_list = _list_with_items(db)
        stranger = authentication_token_from_email(
            client=client, email="export-stranger@example.com", db=db
        )
        response = client.post(
            f"{LISTS}/{shopping_list.id}/export", headers=stranger, json={}
        )
        assert response.status_code == 403
