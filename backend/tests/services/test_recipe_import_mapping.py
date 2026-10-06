from app.models import Unit
from app.models.recipe import ImportSource
from app.services.recipe_import import ParsedIngredient, ParsedRecipe, ParsedStep
from app.services.recipe_import.mapping import parsed_to_create, parsed_to_update


def _parsed(**overrides: object) -> ParsedRecipe:
    data: dict[str, object] = {
        "title": "  Gratin dauphinois  ",
        "source_url": "https://recipes.example/recette/1",
        "ingredients": [
            ParsedIngredient(name="Pommes de terre", quantity=1, unit=Unit.KILOGRAM),
            ParsedIngredient(name="sel", quantity=0, unit=Unit.PINCH),
            ParsedIngredient(name="crème", quantity=40, unit=Unit.CENTILITER),
        ],
        "steps": [
            ParsedStep(instruction="Éplucher.", ingredient_names=["pommes de terre"]),
            ParsedStep(instruction="Assaisonner.", ingredient_names=["Sel", "crème"]),
        ],
    }
    data.update(overrides)
    return ParsedRecipe(**data)  # type: ignore[arg-type]


def test_parsed_to_create_drops_what_create_would_reject() -> None:
    recipe_in = parsed_to_create(
        _parsed(description="x" * 1500, servings=0), is_public=True
    )
    assert recipe_in.title == "Gratin dauphinois"
    assert [i.ingredient_name for i in recipe_in.ingredients] == [
        "Pommes de terre",
        "crème",
    ]
    # Step links point into the filtered list; the dropped "sel" is unlinked.
    assert [s.ingredient_indices for s in recipe_in.steps] == [[0], [1]]
    assert recipe_in.description is not None
    assert len(recipe_in.description) == 1000
    assert recipe_in.servings is None
    assert recipe_in.is_public
    assert recipe_in.import_consent
    assert recipe_in.import_source == ImportSource.URL


def test_parsed_to_update_links_steps_by_name() -> None:
    parsed = _parsed()
    parsed.ingredients[1].quantity = 1
    recipe_in = parsed_to_update(parsed)
    assert recipe_in.ingredients is not None
    assert len(recipe_in.ingredients) == 3
    assert recipe_in.steps is not None
    assert [s.ingredient_indices for s in recipe_in.steps] == [[0], [1, 2]]


def test_parsed_to_update_drops_what_update_would_reject() -> None:
    recipe_in = parsed_to_update(_parsed(description="x" * 1500, servings=0))
    assert recipe_in.title == "Gratin dauphinois"
    assert recipe_in.ingredients is not None
    assert [i.ingredient_name for i in recipe_in.ingredients] == [
        "Pommes de terre",
        "crème",
    ]
    assert recipe_in.description is not None
    assert len(recipe_in.description) == 1000
    assert recipe_in.servings is None
