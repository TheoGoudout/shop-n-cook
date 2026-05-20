import json
import logging
import uuid

import httpx

logger = logging.getLogger(__name__)

_SPOONACULAR_SEARCH_URL = "https://api.spoonacular.com/food/ingredients/search"
_SPOONACULAR_IMAGE_BASE = "https://spoonacular.com/cdn/ingredients_250x250"

_BATCH_CATEGORY_PROMPT = (
    "Classify each of the following food ingredients into exactly one of these categories: "
    "produce, dairy, meat, seafood, grains, pantry, spices, beverages, frozen, bakery, other.\n\n"
    "Return ONLY a JSON object where each key is an ingredient name (exactly as given) "
    "and the value is its category.\n\n"
    "Ingredients:\n{names_list}"
)


def fetch_image_from_spoonacular(name: str) -> str | None:
    from app.core.config import settings

    if not settings.SPOONACULAR_API_KEY:
        logger.warning("SPOONACULAR_API_KEY not set; skipping image fetch for %r", name)
        return None
    logger.info("Fetching Spoonacular image for %r", name)
    try:
        resp = httpx.get(
            _SPOONACULAR_SEARCH_URL,
            params={"query": name, "number": 1, "apiKey": settings.SPOONACULAR_API_KEY},
            timeout=10,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        logger.info("Spoonacular returned %d result(s) for %r", len(results), name)
        if not results:
            logger.warning("No Spoonacular results found for %r", name)
            return None
        image = results[0].get("image")
        if not image:
            return None
        url = f"{_SPOONACULAR_IMAGE_BASE}/{image}"
        logger.info("Selected Spoonacular image for %r: %s", name, url)
        return url
    except Exception:
        logger.exception("Failed to fetch image from Spoonacular for %r", name)
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


def fetch_and_update_ingredients_batch(
    ingredient_ids: list[uuid.UUID], *, force_image: bool = False
) -> None:
    """Fetch Spoonacular images and suggest categories for a list of ingredients.

    Makes a single LLM call for all category suggestions, then individual Spoonacular
    API calls per ingredient. Only updates fields that are still at their default,
    unless force_image=True which overwrites any existing image_url.
    """
    from sqlmodel import Session

    from app.core.db import engine
    from app.models.ingredient import Ingredient, IngredientCategory

    if not ingredient_ids:
        logger.info(
            "fetch_and_update_ingredients_batch called with empty list, skipping"
        )
        return

    logger.info(
        "fetch_and_update_ingredients_batch: processing %d ingredient(s), force_image=%s",
        len(ingredient_ids),
        force_image,
    )

    with Session(engine) as session:
        ingredients = [
            ing
            for iid in ingredient_ids
            if (ing := session.get(Ingredient, iid)) is not None
        ]

        missing_ids = set(ingredient_ids) - {i.id for i in ingredients}
        if missing_ids:
            logger.warning("Ingredient IDs not found in DB: %s", missing_ids)

        logger.info(
            "Loaded %d ingredient(s): %s",
            len(ingredients),
            [
                f"{i.name!r} (id={i.id}, image={'set' if i.image_url else 'missing'})"
                for i in ingredients
            ],
        )

        needs_category = [
            i for i in ingredients if i.category == IngredientCategory.OTHER
        ]
        needs_image = (
            ingredients if force_image else [i for i in ingredients if not i.image_url]
        )

        logger.info(
            "%d need category, %d need image (force_image=%s)",
            len(needs_category),
            len(needs_image),
            force_image,
        )

        if needs_category:
            category_map = _suggest_categories_batch([i.name for i in needs_category])
            for ingredient in needs_category:
                cat = category_map.get(ingredient.name)
                if cat:
                    logger.info("Setting category for %r: %s", ingredient.name, cat)
                    ingredient.category = cat  # type: ignore[assignment]
                else:
                    logger.warning("No category suggested for %r", ingredient.name)

        for ingredient in needs_image:
            url = fetch_image_from_spoonacular(ingredient.name)
            if url:
                logger.info("Updating image_url for %r", ingredient.name)
                ingredient.image_url = url
            else:
                logger.warning("No image URL obtained for %r", ingredient.name)

        if needs_category or needs_image:
            for ingredient in ingredients:
                session.add(ingredient)
            session.commit()
            logger.info("Committed updates for %d ingredient(s)", len(ingredients))
        else:
            logger.info("No updates needed, skipping commit")


def fetch_and_update_ingredient_image(ingredient_id: uuid.UUID) -> None:
    logger.info("fetch_and_update_ingredient_image called for id=%s", ingredient_id)
    fetch_and_update_ingredients_batch([ingredient_id], force_image=True)
