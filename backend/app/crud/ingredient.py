import json
import uuid
from collections.abc import Sequence

from sqlalchemy import update
from sqlmodel import Session, col, func, select

from app.models.ingredient import (
    Ingredient,
    IngredientCategory,
    IngredientCreate,
    IngredientUpdate,
)
from app.models.recipe import RecipeIngredient, RecipeIngredientCreate
from app.models.shopping_list import ShoppingListItem


def get_ingredient_by_name(session: Session, name: str) -> Ingredient | None:
    return session.exec(
        select(Ingredient).where(func.lower(Ingredient.name) == name.lower())
    ).first()


def get_ingredients_by_name(
    *, session: Session, names: Sequence[str]
) -> dict[str, Ingredient]:
    """The catalogue entries named exactly ``names``, keyed by name."""
    if not names:
        return {}
    rows = session.exec(select(Ingredient).where(col(Ingredient.name).in_(names)))
    return {row.name: row for row in rows}


def get_ingredient_categories_by_name(
    *, session: Session, names: Sequence[str]
) -> dict[str, IngredientCategory]:
    """Map lower-cased ingredient names to their catalogue category.

    One query for a whole shopping list rather than one per line. Names with no
    catalogue entry are simply absent from the result, which callers treat as
    "aisle unknown".
    """
    wanted = {name.strip().lower() for name in names if name.strip()}
    if not wanted:
        return {}
    rows = session.exec(
        select(Ingredient).where(func.lower(Ingredient.name).in_(wanted))
    ).all()
    return {row.name.strip().lower(): row.category for row in rows}


def get_or_create_ingredient(session: Session, name: str) -> tuple[Ingredient, bool]:
    existing = get_ingredient_by_name(session, name)
    if existing:
        return existing, False
    ingredient = Ingredient(name=name)
    session.add(ingredient)
    session.flush()
    session.refresh(ingredient)
    return ingredient, True


def sync_ingredient_catalog(
    *, session: Session, ingredients: Sequence[RecipeIngredientCreate]
) -> list[uuid.UUID]:
    """Make sure every ingredient a recipe uses is in the catalogue.

    Fills in a catalogue entry's category and English name when the recipe
    knows them and the catalogue does not. Returns the ids of the entries that
    still have no image, for the caller to fetch one in the background.
    """
    ids_missing_image: list[uuid.UUID] = []
    needs_commit = False
    for ing in ingredients:
        ingredient, _ = get_or_create_ingredient(session, ing.ingredient_name)
        changed = False
        if (
            ing.category is not None
            and ing.category != IngredientCategory.OTHER
            and ingredient.category == IngredientCategory.OTHER
        ):
            ingredient.category = ing.category
            changed = True
        if ing.name_en and not ingredient.name_en:
            ingredient.name_en = ing.name_en
            changed = True
        if changed:
            session.add(ingredient)
            needs_commit = True
        if not ingredient.image_url:
            ids_missing_image.append(ingredient.id)
    if needs_commit:
        session.flush()
    return ids_missing_image


def get_ingredients(
    session: Session, skip: int = 0, limit: int = 1000
) -> tuple[list[Ingredient], int]:
    count = session.exec(select(func.count()).select_from(Ingredient)).one()
    ingredients = session.exec(
        select(Ingredient).order_by(Ingredient.name).offset(skip).limit(limit)
    ).all()
    return list(ingredients), count


def get_ingredient(session: Session, ingredient_id: uuid.UUID) -> Ingredient | None:
    return session.get(Ingredient, ingredient_id)


def create_ingredient(session: Session, ingredient_in: IngredientCreate) -> Ingredient:
    ingredient = Ingredient.model_validate(ingredient_in)
    session.add(ingredient)
    session.flush()
    session.refresh(ingredient)
    return ingredient


def update_ingredient(
    session: Session, ingredient: Ingredient, update_in: IngredientUpdate
) -> Ingredient:
    data = update_in.model_dump(exclude_unset=True)
    ingredient.sqlmodel_update(data)
    session.add(ingredient)
    session.flush()
    session.refresh(ingredient)
    return ingredient


def get_duplicate_groups(session: Session) -> list[list[Ingredient]]:
    """Ask the LLM to identify groups of duplicate ingredient names."""
    from langchain_core.messages import HumanMessage, SystemMessage

    from app.services.recipe_import.llm import configure_langsmith, get_llm

    configure_langsmith()

    ingredients = session.exec(select(Ingredient).order_by(Ingredient.name)).all()
    if len(ingredients) < 2:
        return []

    names_json = json.dumps([i.name for i in ingredients], ensure_ascii=False)
    llm = get_llm()
    response = llm.invoke(
        [
            SystemMessage(
                content=(
                    "You are a culinary data analyst. Given a JSON list of ingredient names, "
                    "return ONLY a valid JSON array of arrays. Each inner array groups names "
                    "that refer to the same core ingredient (e.g. a name with size qualifiers, "
                    "parenthetical variants, or preparation notes alongside the base name). "
                    "Only include groups with at least 2 elements. "
                    "Do not include singletons. "
                    'Example output: [["courgettes","courgettes moyennes"],'
                    '["huile d\'olive","huile d\'olive (extra vierge)"]]'
                )
            ),
            HumanMessage(content=names_json),
        ]
    )
    if isinstance(response.content, str):
        raw = response.content
    elif isinstance(response.content, list):
        raw = next(
            (
                b["text"] if isinstance(b, dict) else getattr(b, "text", "")
                for b in response.content
                if (isinstance(b, dict) and b.get("type") == "text")
                or getattr(b, "type", None) == "text"
            ),
            "",
        )
    else:
        raw = ""
    if raw.startswith("```"):
        raw = raw.split("```")[1].lstrip("json").strip()
    raw = raw.strip()
    if not raw:
        return []
    groups_raw: list[list[str]] = json.loads(raw)

    name_to_obj = {i.name: i for i in ingredients}
    result = []
    for group in groups_raw:
        resolved = [name_to_obj[n] for n in group if n in name_to_obj]
        if len(resolved) >= 2:
            result.append(resolved)
    return result


def _merge_duplicate_shopping_list_items(session: Session, canonical_name: str) -> None:
    """Merge shopping list items that share the same name+unit after a rename."""
    items = session.exec(
        select(ShoppingListItem).where(
            func.lower(ShoppingListItem.name) == canonical_name.lower()
        )
    ).all()

    groups: dict[tuple[uuid.UUID, str], list[ShoppingListItem]] = {}
    for item in items:
        key = (item.shopping_list_id, item.unit)
        groups.setdefault(key, []).append(item)

    for group_items in groups.values():
        if len(group_items) <= 1:
            continue
        keeper = group_items[0]
        keeper.quantity = sum(i.quantity for i in group_items)
        keeper.quantity_at_home = sum(i.quantity_at_home for i in group_items)
        session.add(keeper)
        for dup in group_items[1:]:
            session.delete(dup)


def rename_ingredient_references(
    session: Session, old_name: str, new_name: str
) -> None:
    """Update all recipe and shopping list references from old_name to new_name."""
    session.execute(
        update(RecipeIngredient)
        .where(func.lower(RecipeIngredient.ingredient_name) == old_name.lower())
        .values(ingredient_name=new_name)
    )
    session.execute(
        update(ShoppingListItem)
        .where(func.lower(ShoppingListItem.name) == old_name.lower())
        .values(name=new_name)
    )
    session.flush()
    _merge_duplicate_shopping_list_items(session, new_name)
    session.flush()


def delete_ingredient(session: Session, ingredient: Ingredient) -> None:
    obj = session.get(Ingredient, ingredient.id)
    if obj:
        session.delete(obj)
    session.flush()
