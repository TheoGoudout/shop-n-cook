"""Top-level orchestrator: gather the input, prompt the LLM, parse the response."""

from __future__ import annotations

import base64
import json
from collections.abc import Sequence
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.services.recipe_import import llm as llm_module
from app.services.recipe_import import scraper as scraper_module
from app.services.recipe_import.errors import NoRecipeFoundError
from app.services.recipe_import.models import ParsedRecipe
from app.services.recipe_import.photos import PhotoInput
from app.services.recipe_import.prompt import build_system_prompt


def _parse_llm_response(raw: Any) -> dict[str, Any]:
    """Normalise a chat model response into the parsed recipe payload.

    Handles both plain string content and the Anthropic-style list of content
    blocks, strips markdown fences, and drops entries the model could not fully
    fill in (ingredients without a quantity or unit, blank steps).
    """
    if isinstance(raw, str):
        content = raw.strip()
    elif isinstance(raw, list):
        content = "".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in raw
        ).strip()
    else:
        content = ""

    # Strip markdown code fences if present
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
        content = content.strip()

    data: dict[str, Any] = json.loads(content)
    if "ingredients" in data:
        data["ingredients"] = [
            ing
            for ing in data["ingredients"]
            if ing.get("quantity") is not None and ing.get("unit") is not None
        ]
    if "steps" in data:
        data["steps"] = [
            step for step in data["steps"] if step.get("instruction", "").strip()
        ]
    return data


def import_recipe_from_url(url: str, language: str | None = None) -> ParsedRecipe:
    """Fetch the given URL and use an LLM to extract recipe data."""
    llm_module.configure_langsmith()
    page_text, image_url = scraper_module.fetch_page(url)
    llm = llm_module.get_llm()

    messages = [
        SystemMessage(content=build_system_prompt(language)),
        HumanMessage(
            content=f"""
Extract the recipe from this content.

Note: The input may already contain structured data (JSON or partial fields). Normalize it.

Content:
{page_text}
"""
        ),
    ]

    response = llm.invoke(messages)
    data = _parse_llm_response(response.content)
    return ParsedRecipe(**data, source_url=url, image_url=image_url)


def import_recipe_from_photos(
    photos: Sequence[PhotoInput], language: str | None = None
) -> ParsedRecipe:
    """Use a vision model to extract one recipe from one or more photographs.

    The photos are encoded into the request and never persisted. Every image is
    treated as part of a single recipe.

    Raises:
        NoRecipeFoundError: if no recipe could be read from the images.
    """
    llm_module.configure_langsmith()
    llm = llm_module.get_llm(vision=True)

    # Typed to match HumanMessage.content, whose list element type is invariant.
    content: list[str | dict[Any, Any]] = [
        {
            "type": "image",
            "source_type": "base64",
            "data": base64.standard_b64encode(photo.data).decode("ascii"),
            "mime_type": photo.media_type,
        }
        for photo in photos
    ]
    content.append(
        {
            "type": "text",
            "text": (
                "Extract the recipe from these photos. They are all parts of the "
                "same single recipe."
            ),
        }
    )

    messages = [
        SystemMessage(content=build_system_prompt(language, source="photo")),
        HumanMessage(content=content),
    ]

    response = llm.invoke(messages)
    data = _parse_llm_response(response.content)
    if not str(data.get("title") or "").strip():
        raise NoRecipeFoundError("No recipe could be read from the photos")
    return ParsedRecipe(**data)
