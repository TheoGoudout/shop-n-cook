"""AI-powered recipe import from a URL or from photos, using LangChain.

Supports Anthropic Claude, OpenAI GPT, and Google Gemini.
Optional LangSmith tracing via LANGCHAIN_TRACING_V2 + LANGCHAIN_API_KEY.

This package is structured around sibling modules:

- models.py: ParsedIngredient / ParsedStep / ParsedRecipe Pydantic schemas
- errors.py: InvalidPhotoError / NoRecipeFoundError
- prompt.py: build_system_prompt + the units/categories rule fragments
- scraper.py: fetch_page (HTTP + JSON-LD + HTML fallback)
- photos.py: PhotoInput + validate_photos (count / size / magic-byte checks)
- llm.py: configure_langsmith + get_llm (Anthropic / OpenAI / Google)
- jsonld.py: find_recipe (the schema.org Recipe a page publishes, however nested)
- orchestrator.py: import_recipe_from_url / import_recipe_from_html /
  import_recipe_from_photos tie them together
- mapping.py: parsed_to_create / parsed_to_update / parsed_to_fill turn a
  ParsedRecipe into a RecipeCreate / RecipeUpdate
- version.py: IMPORT_VERSION, the pipeline revision stamped on imported recipes

The public surface (re-exported below) is the import functions plus the
ParsedRecipe schemas. The orchestrator imports its dependencies via module
references (llm_module.get_llm, scraper_module.fetch_page) so tests can
patch them at app.services.recipe_import.llm.get_llm /
app.services.recipe_import.scraper.fetch_page.

Photos are transient: they are validated, encoded into the model request and
discarded. Nothing is written to disk or to the database.
"""

from app.services.recipe_import.errors import (
    InvalidPhotoError,
    NoRecipeFoundError,
    RecipeImportError,
)
from app.services.recipe_import.models import (
    ParsedIngredient,
    ParsedRecipe,
    ParsedStep,
)
from app.services.recipe_import.orchestrator import (
    import_recipe_from_html,
    import_recipe_from_photos,
    import_recipe_from_url,
)
from app.services.recipe_import.photos import PhotoInput, validate_photos
from app.services.recipe_import.version import IMPORT_VERSION

__all__ = [
    "IMPORT_VERSION",
    "InvalidPhotoError",
    "NoRecipeFoundError",
    "ParsedIngredient",
    "ParsedRecipe",
    "ParsedStep",
    "PhotoInput",
    "RecipeImportError",
    "import_recipe_from_html",
    "import_recipe_from_photos",
    "import_recipe_from_url",
    "validate_photos",
]
