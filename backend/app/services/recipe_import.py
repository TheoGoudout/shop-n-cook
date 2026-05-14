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
from langchain_core.rate_limiters import InMemoryRateLimiter
from pydantic import BaseModel

from app.core.config import settings
from app.models.ingredient import IngredientCategory, Unit


class ParsedIngredient(BaseModel):
    name: str
    category: IngredientCategory
    quantity: float
    unit: Unit
    notes: str | None = None


class ParsedStep(BaseModel):
    instruction: str
    ingredient_names: list[str] = []


class ParsedRecipe(BaseModel):
    title: str
    description: str | None = None
    steps: list[ParsedStep] = []
    servings: int | None = None
    prep_time_minutes: int | None = None
    cook_time_minutes: int | None = None
    ingredients: list[ParsedIngredient] = []
    source_url: str | None = None
    image_url: str | None = None


_CATEGORIES = ", ".join(c.value for c in IngredientCategory)
_UNITS = ", ".join(u.value for u in Unit)


def _build_system_prompt(language: str | None = None) -> str:
    lang = (language or "en").split("-")[0].lower()

    if lang == "fr":
        lang_rule = (
            "- Translate all text fields (title, description, step instructions, "
            "ingredient names, and notes) to French\n"
            "- Use standard French culinary terminology for ingredient names"
        )
    else:
        lang_rule = (
            "- Use standard American English ingredient names to avoid regional duplicates "
            '(e.g. "all-purpose flour" not "plain flour", "eggplant" not "aubergine", '
            '"zucchini" not "courgette", "cilantro" not "coriander", '
            '"granulated sugar" or "powdered sugar" not just "sugar" when the type matters)'
        )

    return f"""You are a recipe extraction assistant. Given the text content of a recipe web page, extract the recipe information and return it as JSON.

Return ONLY a valid JSON object with this exact structure:
{{
  "title": "Recipe name",
  "description": "Short description or null",
  "servings": integer or null,
  "prep_time_minutes": integer or null,
  "cook_time_minutes": integer or null,
  "ingredients": [
    {{
      "name": "ingredient name",
      "category": "string (use one of: {_CATEGORIES})",
      "quantity": numeric value,
      "unit": "unit string (use one of: {_UNITS})",
      "notes": "optional preparation note or null"
    }}
  ],
  "steps": [
    {{
      "instruction": "What to do in this step",
      "ingredient_names": ["ingredient name 1", "ingredient name 2"]
    }}
  ]
}}

Rules:
- Split instructions into individual steps (one action per step)
- For each step, list the ingredient names used in that step — use the exact same names as in the ingredients list
- Only reference ingredients in a step if they are actually used in that step
- Convert all measurements to the closest available unit from the list
- If quantity is fractional (e.g. 1/2), convert to decimal (0.5)
- If no unit applies, use "piece"
- Only include ingredients with a measurable quantity — skip garnishes, serving suggestions, or "to taste"/"to serve" items that have no defined amount
{lang_rule}
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
    rate_limiter = InMemoryRateLimiter(
        requests_per_second=2.0,
        check_every_n_seconds=0.1,
        max_bucket_size=10,  # Allows for small bursts
    )

    if provider == "anthropic":
        if not settings.ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY is not configured")
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(  # type: ignore[call-arg]
            model=settings.ANTHROPIC_MODEL,
            api_key=settings.ANTHROPIC_API_KEY,  # type: ignore[arg-type]
            max_retries=2,
            timeout=60,
            max_tokens=2048,
            temperature=0,
            rate_limiter=rate_limiter,
        )

    if provider == "openai":
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is not configured")
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=settings.OPENAI_MODEL,
            api_key=settings.OPENAI_API_KEY,  # type: ignore[arg-type]
            max_retries=3,
            timeout=45,
            max_completion_tokens=2000,
            temperature=0,
            rate_limiter=rate_limiter,
        )

    if provider == "google":
        if not settings.GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY is not configured")
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=settings.GOOGLE_MODEL,
            google_api_key=settings.GOOGLE_API_KEY,
            max_retries=2,
            timeout=30,
            max_output_tokens=2000,
            temperature=0,
            rate_limiter=rate_limiter,
        )

    raise ValueError(
        f"Unknown AI_PROVIDER: '{provider}'. Must be anthropic, openai, or google."
    )


def _fetch_page(url: str) -> tuple[str, str | None]:
    """Fetch a URL and return (focused recipe text, og:image URL or None)."""
    response = httpx.get(
        url,
        timeout=15,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0 (compatible; recipe-importer/1.0)"},
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    # --- Extract image ---
    image_url: str | None = None
    for meta in soup.find_all("meta"):
        prop = meta.get("property", "") or meta.get("name", "")
        if prop in ("og:image", "twitter:image"):
            content = str(meta.get("content") or "").strip()
            if content:
                image_url = content
                break

    # --- 1. Try JSON-LD (best quality, lowest tokens) ---
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except Exception:
            continue

        # Handle list or single object
        items = data if isinstance(data, list) else [data]

        for item in items:
            if not isinstance(item, dict):
                continue

            if item.get("@type") in ("Recipe", ["Recipe"]):
                # Extract only relevant fields
                extracted = {
                    "title": item.get("name"),
                    "description": item.get("description"),
                    "ingredients": item.get("recipeIngredient"),
                    "instructions": item.get("recipeInstructions"),
                }
                return json.dumps(extracted), image_url

    # --- 2. Targeted HTML extraction ---
    def find_section(keywords: list[str]) -> str:
        for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5"]):
            text = tag.get_text(strip=True).lower()
            if any(k in text for k in keywords):
                content = []
                for sib in tag.find_next_siblings():
                    if sib.name and sib.name.startswith("h"):
                        break
                    content.append(sib.get_text(" ", strip=True))
                return "\n".join(content)
        return ""

    ingredients_text = find_section(["ingredient"])
    instructions_text = find_section(["instruction", "direction", "method"])

    combined = f"""
TITLE:
{soup.title.string if soup.title else ""}

INGREDIENTS:
{ingredients_text}

INSTRUCTIONS:
{instructions_text}
    """.strip()

    if len(combined) > 300:
        return combined[:5000], image_url

    # --- 3. Fallback (clean + trimmed full text) ---
    for tag in soup(
        ["script", "style", "nav", "footer", "aside", "header", "noscript"]
    ):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)

    return text[:4000], image_url


def import_recipe_from_url(url: str, language: str | None = None) -> ParsedRecipe:
    """Fetch the given URL and use an LLM to extract recipe data."""
    _configure_langsmith()
    page_text, image_url = _fetch_page(url)
    llm = _get_llm()

    messages = [
        SystemMessage(content=_build_system_prompt(language)),
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
