import json
import logging
import uuid

import httpx

logger = logging.getLogger(__name__)

_OFF_SEARCH_URL = "https://world.openfoodfacts.org/cgi/search.pl"

_BATCH_CATEGORY_PROMPT = (
    "Classify each of the following food ingredients into exactly one of these categories: "
    "produce, dairy, meat, seafood, grains, pantry, spices, beverages, frozen, bakery, other.\n\n"
    "Return ONLY a JSON object where each key is an ingredient name (exactly as given) "
    "and the value is its category.\n\n"
    "Ingredients:\n{names_list}"
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


def _suggest_categories_batch(names: list[str]) -> dict[str, str]:
    """Return {name: IngredientCategory value} for all names in one LLM call."""
    from langchain_core.messages import HumanMessage

    from app.models.ingredient import IngredientCategory
    from app.services.recipe_import import _get_llm

    if not names:
        return {}
    try:
        llm = _get_llm()
        names_list = "\n".join(f"- {n}" for n in names)
        response = llm.invoke(
            [HumanMessage(content=_BATCH_CATEGORY_PROMPT.format(names_list=names_list))]
        )
        content = str(response.content).strip()
        start = content.find("{")
        end = content.rfind("}") + 1
        if start < 0 or end <= start:
            raise ValueError("No JSON object in response")
        raw: dict[str, str] = json.loads(content[start:end])
        valid = {c.value for c in IngredientCategory}
        return {
            name: cat.lower()
            for name, cat in raw.items()
            if isinstance(cat, str) and cat.lower() in valid
        }
    except Exception:
        logger.warning(
            "Batch category suggestion failed for %d ingredients", len(names)
        )
        return {}


def fetch_and_update_ingredients_batch(ingredient_ids: list[uuid.UUID]) -> None:
    """Fetch OFF images and suggest categories for a list of ingredients.

    Makes a single LLM call for all category suggestions, then individual OFF
    API calls per ingredient. Only updates fields that are still at their default.
    """
    from sqlmodel import Session

    from app.core.db import engine
    from app.models.ingredient import Ingredient, IngredientCategory

    if not ingredient_ids:
        return

    with Session(engine) as session:
        ingredients = [
            ing
            for iid in ingredient_ids
            if (ing := session.get(Ingredient, iid)) is not None
        ]

        needs_category = [
            i for i in ingredients if i.category == IngredientCategory.OTHER
        ]
        needs_image = [i for i in ingredients if not i.image_url]

        if needs_category:
            category_map = _suggest_categories_batch([i.name for i in needs_category])
            for ingredient in needs_category:
                cat = category_map.get(ingredient.name)
                if cat:
                    ingredient.category = cat  # type: ignore[assignment]

        for ingredient in needs_image:
            url = fetch_image_from_openfoodfacts(ingredient.name)
            if url:
                ingredient.image_url = url

        if needs_category or needs_image:
            for ingredient in ingredients:
                session.add(ingredient)
            session.commit()


def fetch_and_update_ingredient_image(ingredient_id: uuid.UUID) -> None:
    fetch_and_update_ingredients_batch([ingredient_id])
