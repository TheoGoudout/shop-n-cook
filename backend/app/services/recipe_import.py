"""AI-powered recipe import from URL using LangChain.

Supports Anthropic Claude, OpenAI GPT, and Google Gemini.
Optional LangSmith tracing via LANGCHAIN_TRACING_V2 + LANGCHAIN_API_KEY.
"""

from __future__ import annotations

import json
import os
from typing import Any

import httpx
from bs4 import BeautifulSoup
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from app.core.config import settings


class ParsedIngredient(BaseModel):
    name: str
    quantity: float
    unit: str
    notes: str | None = None


class ParsedRecipe(BaseModel):
    title: str
    description: str | None = None
    instructions: str | None = None
    servings: int | None = None
    prep_time_minutes: int | None = None
    cook_time_minutes: int | None = None
    ingredients: list[ParsedIngredient] = []
    source_url: str | None = None
    image_url: str | None = None


_SYSTEM_PROMPT = """You are a recipe extraction assistant. Given the text content of a recipe web page, extract the recipe information and return it as JSON.

Return ONLY a valid JSON object with this exact structure:
{
  "title": "Recipe name",
  "description": "Short description or null",
  "instructions": "Full cooking instructions as a single string with steps separated by newlines, or null",
  "servings": integer or null,
  "prep_time_minutes": integer or null,
  "cook_time_minutes": integer or null,
  "ingredients": [
    {
      "name": "ingredient name",
      "quantity": numeric value,
      "unit": "unit string (use: g, kg, ml, L, piece, tbsp, tsp, cup, oz, lb, bunch, pinch, clove, slice, can, package)",
      "notes": "optional preparation note or null"
    }
  ]
}

Rules:
- Convert all measurements to the closest available unit from the list
- If quantity is fractional (e.g. 1/2), convert to decimal (0.5)
- If no unit applies, use "piece"
- Only include ingredients with a measurable quantity — skip garnishes, serving suggestions, or "to taste"/"to serve" items that have no defined amount
- Use standard American English ingredient names to avoid regional duplicates (e.g. "all-purpose flour" not "plain flour", "eggplant" not "aubergine", "zucchini" not "courgette", "cilantro" not "coriander", "granulated sugar" or "powdered sugar" not just "sugar" when the type matters)
- Do not include any text outside the JSON object"""


def _configure_langsmith() -> None:
    """Enable LangSmith tracing if configured."""
    if settings.LANGCHAIN_TRACING_V2 and settings.LANGCHAIN_API_KEY:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = settings.LANGCHAIN_API_KEY
        os.environ["LANGCHAIN_PROJECT"] = settings.LANGCHAIN_PROJECT
        os.environ["LANGCHAIN_ENDPOINT"] = settings.LANGCHAIN_ENDPOINT


def _get_llm() -> BaseChatModel:
    """Return the configured LangChain chat model."""
    provider = settings.AI_PROVIDER.lower()

    if provider == "anthropic":
        if not settings.ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY is not configured")
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(  # type: ignore[call-arg]
            model=settings.ANTHROPIC_MODEL,
            api_key=settings.ANTHROPIC_API_KEY,  # type: ignore[arg-type]
            max_tokens=2048,
        )

    if provider == "openai":
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is not configured")
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(  # type: ignore[call-arg]
            model=settings.OPENAI_MODEL,
            api_key=settings.OPENAI_API_KEY,  # type: ignore[arg-type]
            max_tokens=2048,
        )

    if provider == "google":
        if not settings.GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY is not configured")
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=settings.GOOGLE_MODEL,
            google_api_key=settings.GOOGLE_API_KEY,  # type: ignore[arg-type]
            max_output_tokens=2048,
        )

    raise ValueError(
        f"Unknown AI_PROVIDER: '{provider}'. Must be anthropic, openai, or google."
    )


def _fetch_page(url: str) -> tuple[str, str | None]:
    """Fetch a URL and return (cleaned plain text, og:image URL or None)."""
    response = httpx.get(
        url,
        timeout=15,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0 (compatible; recipe-importer/1.0)"},
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    image_url: str | None = None
    for meta in soup.find_all("meta"):
        prop = meta.get("property", "") or meta.get("name", "")
        if prop in ("og:image", "twitter:image"):
            content = (meta.get("content") or "").strip()
            if content:
                image_url = content
                break

    for tag in soup(
        ["script", "style", "nav", "footer", "aside", "header", "noscript"]
    ):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)
    return text[:12000], image_url


def import_recipe_from_url(url: str) -> ParsedRecipe:
    """Fetch the given URL and use an LLM to extract recipe data."""
    _configure_langsmith()
    page_text, image_url = _fetch_page(url)
    llm = _get_llm()

    messages = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=f"Extract the recipe from this page:\n\n{page_text}"),
    ]

    response = llm.invoke(messages)
    content = str(response.content).strip()

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
    return ParsedRecipe(**data, source_url=url, image_url=image_url)
