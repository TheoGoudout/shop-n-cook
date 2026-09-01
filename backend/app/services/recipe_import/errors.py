"""Exceptions raised by the recipe import service."""

from __future__ import annotations


class RecipeImportError(Exception):
    """Base class for recipe import failures."""


class InvalidPhotoError(RecipeImportError):
    """The uploaded photos were rejected before reaching the model."""


class NoRecipeFoundError(RecipeImportError):
    """The model could not read a recipe out of the supplied photos."""
