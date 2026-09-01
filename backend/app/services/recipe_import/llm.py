"""LangChain chat model factory and LangSmith tracing setup."""

from __future__ import annotations

import os

from langchain_core.language_models import BaseChatModel
from langchain_core.rate_limiters import InMemoryRateLimiter

from app.core.config import settings


def configure_langsmith() -> None:
    """Enable LangSmith tracing if configured."""
    if settings.LANGCHAIN_TRACING_V2 and settings.LANGCHAIN_API_KEY:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = settings.LANGCHAIN_API_KEY
        os.environ["LANGCHAIN_PROJECT"] = settings.LANGCHAIN_PROJECT
        os.environ["LANGCHAIN_ENDPOINT"] = settings.LANGCHAIN_ENDPOINT


def get_llm(*, vision: bool = False) -> BaseChatModel:
    """Return the configured LangChain chat model.

    Pass ``vision=True`` for image input: it selects the provider's
    ``*_VISION_MODEL`` and allows a longer timeout, since reading a photographed
    recipe is slower than parsing scraped text.
    """
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
            model=(
                settings.ANTHROPIC_VISION_MODEL if vision else settings.ANTHROPIC_MODEL
            ),
            api_key=settings.ANTHROPIC_API_KEY,  # type: ignore[arg-type]
            max_retries=2,
            timeout=120 if vision else 60,
            max_tokens=2560,
            temperature=0,
            rate_limiter=rate_limiter,
        )

    if provider == "openai":
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is not configured")
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=settings.OPENAI_VISION_MODEL if vision else settings.OPENAI_MODEL,
            api_key=settings.OPENAI_API_KEY,  # type: ignore[arg-type]
            max_retries=3,
            timeout=90 if vision else 45,
            max_completion_tokens=2000,
            temperature=0,
            rate_limiter=rate_limiter,
        )

    if provider == "google":
        if not settings.GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY is not configured")
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=settings.GOOGLE_VISION_MODEL if vision else settings.GOOGLE_MODEL,
            google_api_key=settings.GOOGLE_API_KEY,
            max_retries=2,
            timeout=90 if vision else 30,
            max_output_tokens=2000,
            temperature=0,
            rate_limiter=rate_limiter,
        )

    raise ValueError(
        f"Unknown AI_PROVIDER: '{provider}'. Must be anthropic, openai, or google."
    )
