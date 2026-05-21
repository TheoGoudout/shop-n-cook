"""AI-powered recipe import from URL using LangChain.

Supports Anthropic Claude, OpenAI GPT, and Google Gemini.
Optional LangSmith tracing via LANGCHAIN_TRACING_V2 + LANGCHAIN_API_KEY.

This package is structured around four sibling modules:

- models.py: ParsedIngredient / ParsedStep / ParsedRecipe Pydantic schemas
- prompt.py: build_system_prompt + the units/categories rule fragments
- scraper.py: fetch_page (HTTP + JSON-LD + HTML fallback)
- llm.py: configure_langsmith + get_llm (Anthropic / OpenAI / Google)
- orchestrator.py: import_recipe_from_url ties them together

The public surface (re-exported below) is import_recipe_from_url plus the
ParsedRecipe schemas. The orchestrator imports its dependencies via module
references (llm_module.get_llm, scraper_module.fetch_page) so tests can
patch them at app.services.recipe_import.llm.get_llm /
app.services.recipe_import.scraper.fetch_page.
"""

from app.services.recipe_import.models import (
    ParsedIngredient,
    ParsedRecipe,
    ParsedStep,
)
from app.services.recipe_import.orchestrator import import_recipe_from_url

__all__ = [
    "ParsedIngredient",
    "ParsedRecipe",
    "ParsedStep",
    "import_recipe_from_url",
]
