import logging
import uuid

import httpx

logger = logging.getLogger(__name__)

_SPOONACULAR_SEARCH_URL = "https://api.spoonacular.com/food/ingredients/search"
_SPOONACULAR_IMAGE_BASE = "https://spoonacular.com/cdn/ingredients_250x250"


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


def fetch_and_update_ingredients_batch(
    ingredient_ids: list[uuid.UUID], *, force_image: bool = False
) -> None:
    """Fetch Spoonacular images for ingredients.

    Makes individual Spoonacular API calls per ingredient using the English name if
    available. Only updates image_url if missing, unless force_image=True.
    """
    from sqlmodel import Session

    from app.core.db import engine
    from app.models.ingredient import Ingredient

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

        needs_image = (
            ingredients if force_image else [i for i in ingredients if not i.image_url]
        )

        logger.info("%d need image (force_image=%s)", len(needs_image), force_image)

        for ingredient in needs_image:
            search_name = ingredient.name_en or ingredient.name
            url = fetch_image_from_spoonacular(search_name)
            if url:
                logger.info("Updating image_url for %r", ingredient.name)
                ingredient.image_url = url
            else:
                logger.warning("No image URL obtained for %r", ingredient.name)

        if needs_image:
            for ingredient in needs_image:
                session.add(ingredient)
            session.commit()
            logger.info(
                "Committed image updates for %d ingredient(s)", len(needs_image)
            )
        else:
            logger.info("No image updates needed, skipping commit")


def fetch_and_update_ingredient_image(ingredient_id: uuid.UUID) -> None:
    logger.info("fetch_and_update_ingredient_image called for id=%s", ingredient_id)
    fetch_and_update_ingredients_batch([ingredient_id], force_image=True)
