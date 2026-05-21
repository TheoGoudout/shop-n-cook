"""Top-level orchestrator: fetch page, prompt the LLM, parse the response."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.services.recipe_import import llm as llm_module
from app.services.recipe_import import scraper as scraper_module
from app.services.recipe_import.models import ParsedRecipe
from app.services.recipe_import.prompt import build_system_prompt


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
    raw = response.content
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
    return ParsedRecipe(**data, source_url=url, image_url=image_url)
