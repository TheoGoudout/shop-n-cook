import logging
import uuid

import httpx

logger = logging.getLogger(__name__)

_OFF_SEARCH_URL = "https://world.openfoodfacts.org/cgi/search.pl"


def fetch_image_from_openfoodfacts(name: str) -> str | None:
    try:
        resp = httpx.get(
            _OFF_SEARCH_URL,
            params={
                "search_terms": name,
                "action": "process",
                "json": "1",
                "page_size": "1",
            },
            timeout=10,
            headers={"User-Agent": "ShopNCook/1.0"},
        )
        resp.raise_for_status()
        products = resp.json().get("products", [])
        if not products:
            return None
        product = products[0]
        return product.get("image_front_url") or product.get("image_url") or None
    except Exception:
        logger.warning("Failed to fetch image from Open Food Facts for %r", name)
        return None


def fetch_and_update_ingredient_image(ingredient_id: uuid.UUID) -> None:
    from sqlmodel import Session

    from app.core.db import engine
    from app.models.ingredient import Ingredient

    with Session(engine) as session:
        ingredient = session.get(Ingredient, ingredient_id)
        if not ingredient or ingredient.image_url:
            return
        url = fetch_image_from_openfoodfacts(ingredient.name)
        if url:
            ingredient.image_url = url
            session.add(ingredient)
            session.commit()
