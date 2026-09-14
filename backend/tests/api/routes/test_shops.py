"""Shop endpoints.

The contract worth protecting: ``/price-list`` is a *use case*, so a shop that
cannot do the job still returns 200 with an honest partial body. Only the thin
pass-through (``/search``) turns a shop failure into an error status.
"""

import uuid
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
from app.services.shops.errors import ShopUnavailableError
from app.services.shops.models import ShopProduct
from tests.utils.shopping_list import create_random_shopping_list
from tests.utils.user import (
    authentication_token_from_email,
    create_random_user,
)

PREFIX = f"{settings.API_V1_STR}/shops"


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


class TestReadShops:
    def test_lists_shops_with_capabilities(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        response = client.get(f"{PREFIX}/", headers=superuser_token_headers)
        assert response.status_code == 200
        body = response.json()
        by_slug = {shop["slug"]: shop for shop in body["data"]}
        assert body["count"] == len(body["data"])

        # Auchan: searchable, but its catalogue is priceless without a store.
        assert "search" in by_slug["auchan"]["capabilities"]
        assert "prices" not in by_slug["auchan"]["capabilities"]
        assert by_slug["auchan"]["requires_store"] is True

        # Carrefour: no server search at all; extension transport only.
        assert by_slug["carrefour"]["transport"] == "extension"
        assert by_slug["carrefour"]["requires_extension"] is True
        assert "search" not in by_slug["carrefour"]["capabilities"]

        # Open Prices: the one source that both searches and prices.
        assert {"search", "prices"} <= set(by_slug["openprices"]["capabilities"])
        assert by_slug["openprices"]["attribution"]

    def test_requires_authentication(self, client: TestClient) -> None:
        assert client.get(f"{PREFIX}/").status_code == 401

    def test_country_filter_hides_shops_from_other_countries(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        response = client.get(
            f"{PREFIX}/", headers=superuser_token_headers, params={"country": "ZZ"}
        )
        slugs = {shop["slug"] for shop in response.json()["data"]}
        assert not {"auchan", "carrefour", "openprices"} & slugs
        # The list-only shops are country-agnostic and always remain. See
        # TestExport.test_list_only_shops_are_offered_in_every_country.
        assert slugs == {"market", "printable"}


class TestSearch:
    def test_search_returns_products(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        with patch(
            "app.services.shops.families.html_catalog.HtmlCatalogProvider.search",
            return_value=[ShopProduct(sku="A1", name="Tomates cerises 250g")],
        ):
            response = client.get(
                f"{PREFIX}/auchan/search",
                headers=superuser_token_headers,
                params={"q": "tomate"},
            )
        assert response.status_code == 200
        assert response.json()["products"][0]["sku"] == "A1"

    def test_unknown_shop_is_404(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        response = client.get(
            f"{PREFIX}/nope/search",
            headers=superuser_token_headers,
            params={"q": "tomate"},
        )
        assert response.status_code == 404

    def test_searching_a_shop_that_cannot_search_is_409(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        response = client.get(
            f"{PREFIX}/carrefour/search",
            headers=superuser_token_headers,
            params={"q": "tomate"},
        )
        assert response.status_code == 409

    def test_unreachable_shop_is_502_on_the_passthrough(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        with patch(
            "app.services.shops.families.html_catalog.HtmlCatalogProvider.search",
            side_effect=ShopUnavailableError("403"),
        ):
            response = client.get(
                f"{PREFIX}/auchan/search",
                headers=superuser_token_headers,
                params={"q": "tomate"},
            )
        assert response.status_code == 502


class TestPriceList:
    def test_prices_a_list(
        self,
        client: TestClient,
        superuser_token_headers: dict[str, str],
        db: Session,
    ) -> None:
        shopping_list = _list_with_items(db)
        with patch(
            "app.services.shops.families.html_catalog.HtmlCatalogProvider.search",
            return_value=[
                ShopProduct(
                    sku="A1",
                    name="Tomates cerises rouges 250g",
                    pack_quantity=250,
                    pack_unit=Unit.GRAM,
                )
            ],
        ):
            response = client.post(
                f"{PREFIX}/auchan/price-list",
                headers=superuser_token_headers,
                json={"shopping_list_id": str(shopping_list.id)},
            )
        assert response.status_code == 200
        body = response.json()
        assert body["total"] is None, "Auchan cannot price without a store"
        assert body["partial"] is True
        assert "prices_require_store" in body["notes"]
        assert body["items"][0]["pack_count"] == 2

    def test_unreachable_shop_degrades_instead_of_failing(
        self,
        client: TestClient,
        superuser_token_headers: dict[str, str],
        db: Session,
    ) -> None:
        shopping_list = _list_with_items(db)
        with patch(
            "app.services.shops.families.html_catalog.HtmlCatalogProvider.search",
            side_effect=ShopUnavailableError("403"),
        ):
            response = client.post(
                f"{PREFIX}/auchan/price-list",
                headers=superuser_token_headers,
                json={"shopping_list_id": str(shopping_list.id)},
            )
        assert response.status_code == 200
        body = response.json()
        assert "shop_unavailable" in body["notes"]
        assert all(i["match_status"] == "shop_unavailable" for i in body["items"])

    def test_shop_without_search_still_returns_the_lines(
        self,
        client: TestClient,
        superuser_token_headers: dict[str, str],
        db: Session,
    ) -> None:
        shopping_list = _list_with_items(db)
        response = client.post(
            f"{PREFIX}/carrefour/price-list",
            headers=superuser_token_headers,
            json={"shopping_list_id": str(shopping_list.id)},
        )
        assert response.status_code == 200
        body = response.json()
        assert len(body["items"]) == 2
        assert body["notes"] == ["search_unsupported"]

    def test_other_users_list_is_forbidden(
        self, client: TestClient, db: Session
    ) -> None:
        shopping_list = _list_with_items(db)
        outsider = authentication_token_from_email(
            client=client, email="shops-outsider@example.com", db=db
        )
        response = client.post(
            f"{PREFIX}/carrefour/price-list",
            headers=outsider,
            json={"shopping_list_id": str(shopping_list.id)},
        )
        assert response.status_code == 403

    def test_missing_list_is_404(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        response = client.post(
            f"{PREFIX}/carrefour/price-list",
            headers=superuser_token_headers,
            json={"shopping_list_id": str(uuid.uuid4())},
        )
        assert response.status_code == 404


class TestCart:
    def test_extension_shop_returns_a_plan(
        self,
        client: TestClient,
        superuser_token_headers: dict[str, str],
        db: Session,
    ) -> None:
        shopping_list = _list_with_items(db)
        response = client.post(
            f"{PREFIX}/carrefour/cart",
            headers=superuser_token_headers,
            json={"shopping_list_id": str(shopping_list.id), "store_id": "drive-12"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["transport"] == "extension"
        assert body["url"] is None
        assert body["plan"]["origin"] == "https://www.carrefour.fr"
        assert body["plan"]["store_id"] == "drive-12"
        assert len(body["plan"]["entries"]) == 2
        assert body["plan"]["entries"][0]["requested_unit"] == "g"

    def test_server_shop_returns_a_url(
        self,
        client: TestClient,
        superuser_token_headers: dict[str, str],
        db: Session,
    ) -> None:
        shopping_list = _list_with_items(db)
        with patch(
            "app.services.shops.families.html_catalog.HtmlCatalogProvider.search",
            return_value=[ShopProduct(sku="A1", name="Tomates cerises 250g")],
        ):
            response = client.post(
                f"{PREFIX}/auchan/cart",
                headers=superuser_token_headers,
                json={"shopping_list_id": str(shopping_list.id)},
            )
        assert response.status_code == 200
        body = response.json()
        assert body["transport"] == "server"
        assert body["url"].startswith("https://www.auchan.fr/recherche")
        assert body["plan"] is None

    def test_checked_items_are_excluded(
        self,
        client: TestClient,
        superuser_token_headers: dict[str, str],
        db: Session,
    ) -> None:
        """A ticked-off line is already in the basket or the cupboard."""
        shopping_list = _list_with_items(db)
        for item in shopping_list.items:
            item.is_checked = True
            db.add(item)
        db.commit()
        db.refresh(shopping_list)

        response = client.post(
            f"{PREFIX}/carrefour/cart",
            headers=superuser_token_headers,
            json={"shopping_list_id": str(shopping_list.id)},
        )
        assert response.status_code == 200
        assert response.json()["plan"]["entries"] == []


class TestExport:
    def test_renders_a_list_to_carry(
        self,
        client: TestClient,
        superuser_token_headers: dict[str, str],
        db: Session,
    ) -> None:
        shopping_list = _list_with_items(db)
        response = client.post(
            f"{PREFIX}/market/export",
            headers=superuser_token_headers,
            json={"shopping_list_id": str(shopping_list.id)},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["shop_slug"] == "market"
        assert body["item_count"] == 2
        assert "tomates cerises" in body["content"]
        assert body["groups"]

    def test_aisles_come_from_the_ingredient_catalogue(
        self,
        client: TestClient,
        superuser_token_headers: dict[str, str],
        db: Session,
    ) -> None:
        """The service takes no database dependency, so the route resolves
        categories and hands them over on the line."""
        # Ingredients outlive the session fixture, which only clears lists,
        # recipes and users — so this has to be idempotent across runs.
        ingredient, _ = crud.get_or_create_ingredient(db, "tomates cerises")
        crud.update_ingredient(
            session=db,
            ingredient=ingredient,
            update_in=IngredientUpdate(category=IngredientCategory.PRODUCE),
        )
        shopping_list = _list_with_items(db)
        response = client.post(
            f"{PREFIX}/market/export",
            headers=superuser_token_headers,
            json={"shopping_list_id": str(shopping_list.id)},
        )
        categories = [group["category"] for group in response.json()["groups"]]
        assert "produce" in categories

    def test_format_is_honoured(
        self,
        client: TestClient,
        superuser_token_headers: dict[str, str],
        db: Session,
    ) -> None:
        shopping_list = _list_with_items(db)
        response = client.post(
            f"{PREFIX}/market/export",
            headers=superuser_token_headers,
            json={"shopping_list_id": str(shopping_list.id), "format": "csv"},
        )
        body = response.json()
        assert body["format"] == "csv"
        assert body["content"].startswith("category,item,quantity,unit,note")

    def test_labels_translate_the_rendered_headings(
        self,
        client: TestClient,
        superuser_token_headers: dict[str, str],
        db: Session,
    ) -> None:
        shopping_list = _list_with_items(db)
        response = client.post(
            f"{PREFIX}/market/export",
            headers=superuser_token_headers,
            json={
                "shopping_list_id": str(shopping_list.id),
                "category_labels": {"other": "Divers", "produce": "Primeur"},
            },
        )
        content = response.json()["content"]
        assert "DIVERS" in content or "PRIMEUR" in content

    def test_exporting_from_a_shop_that_cannot_is_409(
        self,
        client: TestClient,
        superuser_token_headers: dict[str, str],
        db: Session,
    ) -> None:
        shopping_list = _list_with_items(db)
        response = client.post(
            f"{PREFIX}/carrefour/export",
            headers=superuser_token_headers,
            json={"shopping_list_id": str(shopping_list.id)},
        )
        assert response.status_code == 409

    def test_other_users_list_is_forbidden(
        self, client: TestClient, db: Session
    ) -> None:
        shopping_list = _list_with_items(db)
        outsider = authentication_token_from_email(
            client=client, email="export-outsider@example.com", db=db
        )
        response = client.post(
            f"{PREFIX}/market/export",
            headers=outsider,
            json={"shopping_list_id": str(shopping_list.id)},
        )
        assert response.status_code == 403

    def test_list_only_shops_are_offered_in_every_country(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        response = client.get(
            f"{PREFIX}/", headers=superuser_token_headers, params={"country": "ZZ"}
        )
        body = response.json()
        slugs = {shop["slug"] for shop in body["data"]}
        assert {"market", "printable"} <= slugs
        market = next(s for s in body["data"] if s["slug"] == "market")
        assert market["transport"] == "offline"
        assert market["capabilities"] == ["list_export"]
