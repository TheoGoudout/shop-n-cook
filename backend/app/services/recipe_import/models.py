"""Pydantic schemas for parsed recipe data."""

from __future__ import annotations

from pydantic import BaseModel

from app.models.ingredient import IngredientCategory, Unit


class ParsedIngredient(BaseModel):
    name: str
    name_en: str | None = None
    quantity: float
    unit: Unit
    notes: str | None = None
    category: IngredientCategory = IngredientCategory.OTHER


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
