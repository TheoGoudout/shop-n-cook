"""Normalisation of free-text ingredient names.

Recipe ingredients are stored as the strings their source used, so the same
thing arrives as ``Tomato``, ``tomatoes`` and ``  Tomatoes ``. Both the price
lookup and the shopping-list merge need those to land on one key, so the rule
lives here rather than being re-derived at each call site.
"""

import re

__all__ = ["normalize_ingredient_name"]

_WHITESPACE = re.compile(r"\s+")

# Words short enough that stripping a trailing "s" would corrupt them
# ("gas" -> "ga"), or where the plural is not formed with one.
_MIN_STEM_LENGTH = 4

_IRREGULAR_PLURALS = {
    "leaves": "leaf",
    "loaves": "loaf",
    "halves": "half",
    "knives": "knife",
    "potatoes": "potato",
    "tomatoes": "tomato",
    "chillies": "chilli",
    "berries": "berry",
    "cherries": "cherry",
}


def _is_invariant(word: str) -> bool:
    """Words whose trailing "s" is part of the word, not a plural marker.

    Mass nouns like ``couscous`` and ``molasses`` are common enough in recipes
    that mangling them into ``couscou`` would be a visible bug.
    """
    return word.endswith("us") or word.endswith("ss")


def _singularize(word: str) -> str:
    if word in _IRREGULAR_PLURALS:
        return _IRREGULAR_PLURALS[word]
    if _is_invariant(word):
        return word
    if word.endswith("ies") and len(word) > _MIN_STEM_LENGTH:
        return f"{word[:-3]}y"
    if word.endswith(("ses", "xes", "hes")):
        stem = word[:-2]
        # "molasses" -> "molass" is not a word; a stem still ending in "s"
        # means the "es" was not a plural marker.
        return word if stem.endswith("s") else stem
    if word.endswith("s"):
        stem = word[:-1]
        if len(stem) >= _MIN_STEM_LENGTH - 1:
            return stem
    return word


def normalize_ingredient_name(name: str) -> str:
    """Fold a free-text ingredient name to a comparison key.

    Lowercases, collapses whitespace and singularises each word, so
    ``"  Cherry Tomatoes "`` and ``"cherry tomato"`` agree. Deliberately
    conservative: it never rewrites a word it cannot confidently singularise,
    because a wrong merge is worse than a missed one.
    """
    cleaned = _WHITESPACE.sub(" ", name.strip().lower())
    if not cleaned:
        return ""
    return " ".join(_singularize(word) for word in cleaned.split(" "))
