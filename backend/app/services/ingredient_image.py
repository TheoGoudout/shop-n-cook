import json
import logging
import uuid

import httpx

logger = logging.getLogger(__name__)

_SPOONACULAR_SEARCH_URL = "https://api.spoonacular.com/food/ingredients/search"
_SPOONACULAR_IMAGE_BASE = "https://spoonacular.com/cdn/ingredients_250x250"

_BATCH_ENRICH_PROMPT = (
    "For each of the following food ingredient names (which may be in any language):\n"
    "1. Translate to English (if already in English, return it unchanged)\n"
    "2. Classify into exactly one of: "
    "produce, dairy, meat, seafood, grains, pantry, spices, beverages, frozen, bakery, other\n\n"
    "Return ONLY a JSON object where each key is the original ingredient name (exactly as given) "
    'and the value is an object with "name_en" (English name) and "category" fields.\n\n'
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


def _enrich_ingredients_batch(names: list[str]) -> dict[str, dict[str, str]]:
    """Return {name: {"name_en": ..., "category": ...}} for all names in one LLM call."""
    from langchain_core.messages import HumanMessage

    from app.models.ingredient import IngredientCategory
    from app.services.recipe_import import _get_llm

    if not names:
        return {}
    try:
        llm = _get_llm()
        names_list = "\n".join(f"- {n}" for n in names)
        response = llm.invoke(
            [HumanMessage(content=_BATCH_ENRICH_PROMPT.format(names_list=names_list))]
        )
        content = str(response.content).strip()
        start = content.find("{")
        end = content.rfind("}") + 1
        if start < 0 or end <= start:
            raise ValueError("No JSON object in response")
        raw: dict[str, dict] = json.loads(content[start:end])
        valid_categories = {c.value for c in IngredientCategory}
        result: dict[str, dict[str, str]] = {}
        for name, info in raw.items():
            if not isinstance(info, dict):
                continue
            entry: dict[str, str] = {}
            cat = info.get("category", "")
            if isinstance(cat, str) and cat.lower() in valid_categories:
                entry["category"] = cat.lower()
            name_en = info.get("name_en", "")
            if isinstance(name_en, str) and name_en.strip():
                entry["name_en"] = name_en.strip()
            if entry:
                result[name] = entry
        return result
    except Exception:
        logger.warning("Batch enrichment failed for %d ingredients", len(names))
        return {}


def fetch_and_update_ingredients_batch(
    ingredient_ids: list[uuid.UUID], *, force_image: bool = False
) -> None:
    """Fetch Spoonacular images and enrich ingredients (English name + category).

    Makes a single LLM call to translate names to English and suggest categories,
    then individual Spoonacular API calls per ingredient using the English name.
    Only updates fields that are still at their default, unless force_image=True
    which overwrites any existing image_url.
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

        needs_enrichment = [
            i
            for i in ingredients
            if i.category == IngredientCategory.OTHER or not i.name_en
        ]
        needs_image = (
            ingredients if force_image else [i for i in ingredients if not i.image_url]
        )

        logger.info(
            "%d need enrichment, %d need image (force_image=%s)",
            len(needs_enrichment),
            len(needs_image),
            force_image,
        )

        if needs_enrichment:
            enrichment_map = _enrich_ingredients_batch(
                [i.name for i in needs_enrichment]
            )
            for ingredient in needs_enrichment:
                info = enrichment_map.get(ingredient.name, {})
                cat = info.get("category")
                if cat and ingredient.category == IngredientCategory.OTHER:
                    logger.info("Setting category for %r: %s", ingredient.name, cat)
                    ingredient.category = cat  # type: ignore[assignment]
                elif not cat:
                    logger.warning("No category suggested for %r", ingredient.name)
                name_en = info.get("name_en")
                if name_en and not ingredient.name_en:
                    logger.info(
                        "Setting name_en for %r: %r", ingredient.name, name_en
                    )
                    ingredient.name_en = name_en
                elif not name_en:
                    logger.warning("No English name obtained for %r", ingredient.name)

        for ingredient in needs_image:
            search_name = ingredient.name_en or ingredient.name
            url = fetch_image_from_spoonacular(search_name)
            if url:
                logger.info("Updating image_url for %r", ingredient.name)
                ingredient.image_url = url
            else:
                logger.warning("No image URL obtained for %r", ingredient.name)

        if needs_enrichment or needs_image:
            for ingredient in ingredients:
                session.add(ingredient)
            session.commit()
            logger.info("Committed updates for %d ingredient(s)", len(ingredients))
        else:
            logger.info("No updates needed, skipping commit")


def fetch_and_update_ingredient_image(ingredient_id: uuid.UUID) -> None:
    logger.info("fetch_and_update_ingredient_image called for id=%s", ingredient_id)
    fetch_and_update_ingredients_batch([ingredient_id], force_image=True)
