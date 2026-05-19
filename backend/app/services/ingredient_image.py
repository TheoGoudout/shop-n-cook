import logging
import uuid

import httpx

logger = logging.getLogger(__name__)

_OFF_SEARCH_URL = "https://world.openfoodfacts.org/cgi/search.pl"

_CATEGORY_PROMPT = (
    "Classify this food ingredient into exactly one of these categories: "
    "produce, dairy, meat, seafood, grains, pantry, spices, beverages, frozen, bakery, other. "
    "Ingredient: {name}. "
    "Reply with ONLY the category name, nothing else."
)


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


def suggest_ingredient_category(name: str) -> str:
    """Return an IngredientCategory value for the given name, or 'other' on failure."""
    from langchain_core.messages import HumanMessage

    from app.models.ingredient import IngredientCategory
    from app.services.recipe_import import _get_llm

    try:
        llm = _get_llm()
        response = llm.invoke(
            [HumanMessage(content=_CATEGORY_PROMPT.format(name=name))]
        )
        category_str = str(response.content).strip().lower()
        return IngredientCategory(category_str)
    except Exception:
        logger.debug("Category suggestion failed for %r, defaulting to 'other'", name)
        return IngredientCategory.OTHER


def fetch_and_update_ingredient_image(ingredient_id: uuid.UUID) -> None:
    from sqlmodel import Session

    from app.core.db import engine
    from app.models.ingredient import Ingredient, IngredientCategory

    with Session(engine) as session:
        ingredient = session.get(Ingredient, ingredient_id)
        if not ingredient:
            return
        changed = False
        if not ingredient.image_url:
            url = fetch_image_from_openfoodfacts(ingredient.name)
            if url:
                ingredient.image_url = url
                changed = True
        if ingredient.category == IngredientCategory.OTHER:
            ingredient.category = suggest_ingredient_category(ingredient.name)  # type: ignore[assignment]
            changed = True
        if changed:
            session.add(ingredient)
            session.commit()
