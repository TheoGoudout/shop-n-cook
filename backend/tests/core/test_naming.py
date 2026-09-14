"""Ingredient-name normalisation — the key both pricing and merging agree on."""

import pytest

from app.core.naming import normalize_ingredient_name


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Tomato", "tomato"),
        ("tomatoes", "tomato"),
        ("  Cherry  Tomatoes ", "cherry tomato"),
        ("EGGS", "egg"),
        ("Olive Oil", "olive oil"),
        ("potatoes", "potato"),
        ("leaves", "leaf"),
        ("berries", "berry"),
        ("dishes", "dish"),
    ],
)
def test_normalisation(raw: str, expected: str) -> None:
    assert normalize_ingredient_name(raw) == expected


def test_plural_and_singular_agree() -> None:
    assert normalize_ingredient_name("Tomatoes") == normalize_ingredient_name("tomato")


@pytest.mark.parametrize("word", ["gas", "molasses", "couscous", "watercress"])
def test_words_ending_in_s_are_not_mangled(word: str) -> None:
    """Stripping a trailing "s" from these would invent an ingredient."""
    assert normalize_ingredient_name(word) == word


def test_empty_input() -> None:
    assert normalize_ingredient_name("") == ""
    assert normalize_ingredient_name("   ") == ""
