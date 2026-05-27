"""Tests for the ingredient catalog API, including deduplication."""

import json
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models.ingredient import Ingredient
from app.models.shopping_list import ShoppingListItem
from app.models import ShoppingListCreate, Unit


def _llm_response(groups: list[list[str]]) -> MagicMock:
    msg = MagicMock()
    msg.content = json.dumps(groups)
    return msg


def _make_ingredient(db: Session, name: str) -> Ingredient:
    ing, _ = crud.get_or_create_ingredient(session=db, name=name)
    return ing


# ---------------------------------------------------------------------------
# CRUD unit tests
# ---------------------------------------------------------------------------


def test_delete_ingredient(db: Session) -> None:
    ing = _make_ingredient(db, "test_delete_me_xyz")
    crud.delete_ingredient(session=db, ingredient=ing)
    assert crud.get_ingredient_by_name(session=db, name="test_delete_me_xyz") is None


def test_rename_ingredient_references_no_match(db: Session) -> None:
    # Renaming a nonexistent name is a no-op but must not raise.
    crud.rename_ingredient_references(
        session=db,
        old_name="test_nonexistent_old_zzz",
        new_name="test_nonexistent_new_zzz",
    )


def test_rename_merges_duplicate_shopping_list_items(db: Session) -> None:
    """After renaming, shopping list items with the same name+unit are merged."""
    superuser = crud.get_user_by_email(session=db, email=settings.FIRST_SUPERUSER)
    sl = crud.create_shopping_list(
        session=db,
        list_in=ShoppingListCreate(name="test_merge_sl"),
        owner_id=superuser.id,  # type: ignore[union-attr]
    )
    item_a = ShoppingListItem(
        shopping_list_id=sl.id,
        name="Tomato",
        quantity=100.0,
        unit=Unit.GRAM,
    )
    item_b = ShoppingListItem(
        shopping_list_id=sl.id,
        name="Tomate",
        quantity=200.0,
        unit=Unit.GRAM,
    )
    db.add(item_a)
    db.add(item_b)
    db.commit()

    crud.rename_ingredient_references(session=db, old_name="Tomate", new_name="Tomato")

    db.refresh(sl)
    items = [i for i in sl.items if i.unit == Unit.GRAM and i.name.lower() == "tomato"]
    assert len(items) == 1
    assert items[0].quantity == 300.0


def test_get_duplicate_groups_too_few() -> None:
    # When the DB has fewer than 2 ingredients, the function returns [] immediately
    # without calling the LLM.  We stub exec() to simulate that case.
    from unittest.mock import MagicMock as MM

    mock_session = MM(spec=Session)
    mock_session.exec.return_value.all.return_value = [Ingredient(name="only_one")]

    result = crud.get_duplicate_groups(session=mock_session)
    assert result == []


def test_get_duplicate_groups_empty_llm_response(db: Session) -> None:
    ing_a = _make_ingredient(db, "test_empty_llm_a_xyz")
    ing_b = _make_ingredient(db, "test_empty_llm_b_xyz")

    llm_mock = MagicMock()
    msg = MagicMock()
    msg.content = ""
    llm_mock.invoke.return_value = msg

    with patch("app.services.recipe_import.llm.get_llm", return_value=llm_mock):
        groups = crud.get_duplicate_groups(session=db)

    assert groups == []

    crud.delete_ingredient(session=db, ingredient=ing_a)
    crud.delete_ingredient(session=db, ingredient=ing_b)


def test_get_duplicate_groups_content_block_response(db: Session) -> None:
    ing_a = _make_ingredient(db, "test_block_a_xyz")
    ing_b = _make_ingredient(db, "test_block_a_xyz variant")

    llm_mock = MagicMock()
    msg = MagicMock()
    msg.content = [
        {
            "type": "text",
            "text": json.dumps([["test_block_a_xyz", "test_block_a_xyz variant"]]),
        }
    ]
    llm_mock.invoke.return_value = msg

    with patch("app.services.recipe_import.llm.get_llm", return_value=llm_mock):
        groups = crud.get_duplicate_groups(session=db)

    names_in_groups = {i.name for group in groups for i in group}
    assert "test_block_a_xyz" in names_in_groups
    assert "test_block_a_xyz variant" in names_in_groups

    crud.delete_ingredient(session=db, ingredient=ing_a)
    crud.delete_ingredient(session=db, ingredient=ing_b)


def test_get_duplicate_groups_llm(db: Session) -> None:
    ing_a = _make_ingredient(db, "test_dup_a_xyz")
    ing_b = _make_ingredient(db, "test_dup_a_xyz variant")

    llm_mock = MagicMock()
    llm_mock.invoke.return_value = _llm_response(
        [["test_dup_a_xyz", "test_dup_a_xyz variant"]]
    )

    with patch("app.services.recipe_import.llm.get_llm", return_value=llm_mock):
        groups = crud.get_duplicate_groups(session=db)

    names_in_groups = {i.name for group in groups for i in group}
    assert "test_dup_a_xyz" in names_in_groups
    assert "test_dup_a_xyz variant" in names_in_groups

    crud.delete_ingredient(session=db, ingredient=ing_a)
    crud.delete_ingredient(session=db, ingredient=ing_b)


def test_get_duplicate_groups_strips_markdown_fence(db: Session) -> None:
    ing_a = _make_ingredient(db, "test_fence_a_xyz")
    ing_b = _make_ingredient(db, "test_fence_a_xyz alt")

    llm_mock = MagicMock()
    msg = MagicMock()
    msg.content = (
        "```json\n"
        + json.dumps([["test_fence_a_xyz", "test_fence_a_xyz alt"]])
        + "\n```"
    )
    llm_mock.invoke.return_value = msg

    with patch("app.services.recipe_import.llm.get_llm", return_value=llm_mock):
        groups = crud.get_duplicate_groups(session=db)

    names_in_groups = {i.name for group in groups for i in group}
    assert "test_fence_a_xyz" in names_in_groups

    crud.delete_ingredient(session=db, ingredient=ing_a)
    crud.delete_ingredient(session=db, ingredient=ing_b)


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------


def test_deduplicate_dry_run(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    """dry_run=true returns groups but makes no DB changes."""
    ing1 = _make_ingredient(db, "test_dry_base_xyz")
    ing2 = _make_ingredient(db, "test_dry_base_xyz long")

    with patch(
        "app.api.routes.ingredients.crud.get_duplicate_groups",
        return_value=[[ing1, ing2]],
    ):
        response = client.post(
            f"{settings.API_V1_STR}/ingredients/deduplicate?dry_run=true",
            headers=superuser_token_headers,
        )

    assert response.status_code == 200
    data = response.json()
    assert data["dry_run"] is True
    assert data["removed_count"] == 0
    assert len(data["groups"]) == 1
    assert data["groups"][0]["kept"] == "test_dry_base_xyz"
    assert "test_dry_base_xyz long" in data["groups"][0]["removed"]

    # Nothing deleted.
    assert crud.get_ingredient_by_name(session=db, name="test_dry_base_xyz") is not None
    assert (
        crud.get_ingredient_by_name(session=db, name="test_dry_base_xyz long")
        is not None
    )

    crud.delete_ingredient(session=db, ingredient=ing1)
    crud.delete_ingredient(session=db, ingredient=ing2)


def test_deduplicate_apply(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    """dry_run=false removes duplicates and returns the correct count."""
    ing1 = _make_ingredient(db, "test_apply_base_xyz")
    ing2 = _make_ingredient(db, "test_apply_base_xyz long")

    with patch(
        "app.api.routes.ingredients.crud.get_duplicate_groups",
        return_value=[[ing1, ing2]],
    ):
        response = client.post(
            f"{settings.API_V1_STR}/ingredients/deduplicate?dry_run=false",
            headers=superuser_token_headers,
        )

    assert response.status_code == 200
    data = response.json()
    assert data["dry_run"] is False
    assert data["removed_count"] == 1
    assert data["groups"][0]["kept"] == "test_apply_base_xyz"

    # Shorter name kept; longer removed.
    assert (
        crud.get_ingredient_by_name(session=db, name="test_apply_base_xyz") is not None
    )
    assert (
        crud.get_ingredient_by_name(session=db, name="test_apply_base_xyz long") is None
    )

    remaining = crud.get_ingredient_by_name(session=db, name="test_apply_base_xyz")
    if remaining:
        crud.delete_ingredient(session=db, ingredient=remaining)


def test_deduplicate_no_duplicates(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """When the LLM finds no duplicates the response groups list is empty."""
    with patch(
        "app.api.routes.ingredients.crud.get_duplicate_groups",
        return_value=[],
    ):
        response = client.post(
            f"{settings.API_V1_STR}/ingredients/deduplicate",
            headers=superuser_token_headers,
        )

    assert response.status_code == 200
    data = response.json()
    assert data["groups"] == []
    assert data["removed_count"] == 0
