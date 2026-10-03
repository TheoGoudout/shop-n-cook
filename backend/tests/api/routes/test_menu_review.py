"""Reviewing a menu before saving it, batch cooking, and saved preferences."""

import uuid
from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models import RecipeCreate, User
from tests.utils.user import authentication_token_from_email, create_random_user
from tests.utils.utils import random_lower_string

START = date(2026, 4, 6)  # a Monday
API = f"{settings.API_V1_STR}/meal-plans"


def _account(client: TestClient, db: Session) -> tuple[dict[str, str], User]:
    """A user of its own, so the recipe library is exactly what the test adds."""
    email = f"menu-{random_lower_string()}@example.com"
    headers = authentication_token_from_email(client=client, email=email, db=db)
    user = crud.get_user_by_email(session=db, email=email)
    assert user is not None
    return headers, user


def _recipe(
    db: Session,
    owner_id: uuid.UUID,
    *,
    title: str | None = None,
    vegan: bool = False,
    public: bool = False,
) -> uuid.UUID:
    recipe = crud.create_recipe(
        session=db,
        recipe_in=RecipeCreate(
            title=title or random_lower_string(),
            servings=2,
            is_vegan=vegan,
            is_public=public,
            ingredients=[],
        ),
        owner_id=owner_id,
    )
    return recipe.id


def _base(**extra: object) -> dict[str, object]:
    return {
        "start_date": START.isoformat(),
        "days": 4,
        "servings": 2,
        "include_public": False,
        **extra,
    }


def _slot(offset: int, meal_type: str = "dinner") -> dict[str, str]:
    return {
        "entry_date": (START + timedelta(days=offset)).isoformat(),
        "meal_type": meal_type,
    }


# --------------------------------------------------------------------------- #
# Preview                                                                      #
# --------------------------------------------------------------------------- #


def test_a_preview_proposes_a_menu_without_saving_it(
    client: TestClient, db: Session
) -> None:
    headers, user = _account(client, db)
    for _ in range(5):
        _recipe(db, user.id)

    response = client.post(f"{API}/generate/preview", headers=headers, json=_base())
    assert response.status_code == 200
    body = response.json()
    assert len(body["meals"]) == 4
    assert body["servings"] == 2
    assert all(len(m["slots"]) == 1 for m in body["meals"])

    plans = client.get(f"{API}/", headers=headers).json()
    assert plans["count"] == 0


def test_a_preview_with_batch_cooking_groups_leftovers(
    client: TestClient, db: Session
) -> None:
    headers, user = _account(client, db)
    for _ in range(5):
        _recipe(db, user.id)

    body = client.post(
        f"{API}/generate/preview", headers=headers, json=_base(batch_portions=2)
    ).json()
    assert [len(m["slots"]) for m in body["meals"]] == [2, 2]
    assert body["meals"][0]["slots"] == [_slot(0), _slot(1)]


def test_replacing_meals_changes_only_those_meals(
    client: TestClient, db: Session
) -> None:
    headers, user = _account(client, db)
    for _ in range(8):
        _recipe(db, user.id)
    proposed = client.post(
        f"{API}/generate/preview", headers=headers, json=_base()
    ).json()["meals"]
    meals = [{"recipe_id": m["recipe_id"], "slots": m["slots"]} for m in proposed]

    response = client.post(
        f"{API}/generate/preview",
        headers=headers,
        json=_base(meals=meals, replace=[0, 2]),
    )
    assert response.status_code == 200
    after = response.json()["meals"]
    assert after[0]["recipe_id"] != meals[0]["recipe_id"]
    assert after[2]["recipe_id"] != meals[2]["recipe_id"]
    assert after[1]["recipe_id"] == meals[1]["recipe_id"]
    assert after[3]["recipe_id"] == meals[3]["recipe_id"]
    assert [m["slots"] for m in after] == [m["slots"] for m in meals]
    # Two replacements made together do not land on the same recipe.
    assert len({m["recipe_id"] for m in after}) == 4


def test_replacements_keep_the_dietary_preferences(
    client: TestClient, db: Session
) -> None:
    headers, user = _account(client, db)
    vegan = {str(_recipe(db, user.id, vegan=True)) for _ in range(3)}
    for _ in range(5):
        _recipe(db, user.id)

    preview = client.post(
        f"{API}/generate/preview",
        headers=headers,
        json=_base(days=1, require_vegan=True),
    ).json()
    meals = [
        {"recipe_id": m["recipe_id"], "slots": m["slots"]} for m in preview["meals"]
    ]
    for _ in range(4):
        swapped = client.post(
            f"{API}/generate/preview",
            headers=headers,
            json=_base(days=1, require_vegan=True, meals=meals, replace=[0]),
        ).json()["meals"]
        assert swapped[0]["recipe_id"] in vegan
        meals = [{"recipe_id": m["recipe_id"], "slots": m["slots"]} for m in swapped]


def test_replacing_with_no_alternative_is_refused(
    client: TestClient, db: Session
) -> None:
    headers, user = _account(client, db)
    only = _recipe(db, user.id)
    response = client.post(
        f"{API}/generate/preview",
        headers=headers,
        json=_base(meals=[{"recipe_id": str(only), "slots": [_slot(0)]}], replace=[0]),
    )
    assert response.status_code == 422


def test_replacing_a_meal_that_does_not_exist_is_refused(
    client: TestClient, db: Session
) -> None:
    headers, user = _account(client, db)
    recipe = _recipe(db, user.id)
    response = client.post(
        f"{API}/generate/preview",
        headers=headers,
        json=_base(
            meals=[{"recipe_id": str(recipe), "slots": [_slot(0)]}], replace=[3]
        ),
    )
    assert response.status_code == 422


def test_a_recipe_chosen_by_hand_is_kept_and_described(
    client: TestClient, db: Session
) -> None:
    headers, user = _account(client, db)
    chosen = _recipe(db, user.id, title="Grandma's stew")
    response = client.post(
        f"{API}/generate/preview",
        headers=headers,
        json=_base(meals=[{"recipe_id": str(chosen), "slots": [_slot(0), _slot(1)]}]),
    )
    assert response.status_code == 200
    meal = response.json()["meals"][0]
    assert meal["recipe_title"] == "Grandma's stew"
    assert meal["slots"] == [_slot(0), _slot(1)]


def test_someone_elses_private_recipe_cannot_be_chosen(
    client: TestClient, db: Session
) -> None:
    headers, _ = _account(client, db)
    stranger = create_random_user(db)
    private = _recipe(db, stranger.id)
    response = client.post(
        f"{API}/generate/preview",
        headers=headers,
        json=_base(meals=[{"recipe_id": str(private), "slots": [_slot(0)]}]),
    )
    assert response.status_code == 403


def test_a_meal_outside_the_plan_is_refused(client: TestClient, db: Session) -> None:
    headers, user = _account(client, db)
    recipe = _recipe(db, user.id)
    response = client.post(
        f"{API}/generate/preview",
        headers=headers,
        json=_base(meals=[{"recipe_id": str(recipe), "slots": [_slot(9)]}]),
    )
    assert response.status_code == 422


def test_a_recipe_twice_in_one_slot_is_refused(client: TestClient, db: Session) -> None:
    headers, user = _account(client, db)
    recipe = str(_recipe(db, user.id))
    response = client.post(
        f"{API}/generate",
        headers=headers,
        json=_base(
            meals=[
                {"recipe_id": recipe, "slots": [_slot(0)]},
                {"recipe_id": recipe, "slots": [_slot(0)]},
            ]
        ),
    )
    assert response.status_code == 422


# --------------------------------------------------------------------------- #
# Choosing by hand                                                             #
# --------------------------------------------------------------------------- #


def test_options_only_offer_recipes_matching_the_preferences(
    client: TestClient, db: Session
) -> None:
    headers, user = _account(client, db)
    vegan = _recipe(db, user.id, title="Lentil curry", vegan=True)
    _recipe(db, user.id, title="Beef curry")
    _recipe(db, user.id, title="Tofu bowl", vegan=True)

    response = client.post(
        f"{API}/generate/options",
        headers=headers,
        json=_base(require_vegan=True, search="curry"),
    )
    assert response.status_code == 200
    assert [o["id"] for o in response.json()] == [str(vegan)]


# --------------------------------------------------------------------------- #
# Saving                                                                       #
# --------------------------------------------------------------------------- #


def test_saving_a_reviewed_menu_keeps_its_meals_and_batches(
    client: TestClient, db: Session
) -> None:
    headers, user = _account(client, db)
    stew, salad = str(_recipe(db, user.id)), str(_recipe(db, user.id))

    response = client.post(
        f"{API}/generate",
        headers=headers,
        json=_base(
            days=4,
            batch_portions=3,
            meals=[
                {"recipe_id": stew, "slots": [_slot(0), _slot(1), _slot(2)]},
                {"recipe_id": salad, "slots": [_slot(3)]},
            ],
        ),
    )
    assert response.status_code == 200
    entries = response.json()["entries"]
    assert len(entries) == 4
    cooked = next(e for e in entries if e["entry_date"] == START.isoformat())
    leftovers = [e for e in entries if e["batch_of_id"] == cooked["id"]]
    assert cooked["batch_of_id"] is None
    assert {e["entry_date"] for e in leftovers} == {
        _slot(1)["entry_date"],
        _slot(2)["entry_date"],
    }
    assert all(e["recipe_id"] == stew for e in leftovers)


def test_saving_an_empty_menu_is_refused(client: TestClient, db: Session) -> None:
    headers, user = _account(client, db)
    _recipe(db, user.id)
    response = client.post(f"{API}/generate", headers=headers, json=_base(meals=[]))
    assert response.status_code == 422


def test_a_batch_is_bought_for_every_meal_it_covers(
    client: TestClient, db: Session
) -> None:
    headers, user = _account(client, db)
    stew = str(_recipe(db, user.id))
    plan = client.post(
        f"{API}/generate",
        headers=headers,
        json=_base(days=2, meals=[{"recipe_id": stew, "slots": [_slot(0), _slot(1)]}]),
    ).json()
    assert sum(e["servings"] for e in plan["entries"]) == 4


# --------------------------------------------------------------------------- #
# After saving                                                                 #
# --------------------------------------------------------------------------- #


def _batch_plan(
    client: TestClient, headers: dict[str, str], recipe: str, **extra: object
) -> list[dict[str, object]]:
    plan = client.post(
        f"{API}/generate",
        headers=headers,
        json=_base(
            days=3,
            meals=[{"recipe_id": recipe, "slots": [_slot(0), _slot(1), _slot(2)]}],
            **extra,
        ),
    ).json()
    entries: list[dict[str, object]] = sorted(
        plan["entries"], key=lambda e: str(e["entry_date"])
    )
    return entries


def test_swapping_a_leftover_swaps_its_whole_batch(
    client: TestClient, db: Session
) -> None:
    headers, user = _account(client, db)
    first = str(_recipe(db, user.id))
    _recipe(db, user.id)
    entries = _batch_plan(client, headers, first)
    plan_id = entries[0]["meal_plan_id"]

    response = client.post(
        f"{API}/{plan_id}/entries/{entries[2]['id']}/swap", headers=headers
    )
    assert response.status_code == 200
    plan = client.get(f"{API}/{plan_id}", headers=headers).json()
    recipes = {e["recipe_id"] for e in plan["entries"]}
    assert len(recipes) == 1
    assert recipes != {first}


def test_a_swap_after_saving_keeps_the_saved_preferences(
    client: TestClient, db: Session
) -> None:
    headers, user = _account(client, db)
    vegan = {str(_recipe(db, user.id, vegan=True)) for _ in range(2)}
    for _ in range(4):
        _recipe(db, user.id)
    plan = client.post(
        f"{API}/generate",
        headers=headers,
        json=_base(days=1, require_vegan=True),
    ).json()
    entry = plan["entries"][0]
    assert entry["recipe_id"] in vegan

    swapped = client.post(
        f"{API}/{plan['id']}/entries/{entry['id']}/swap", headers=headers
    )
    assert swapped.status_code == 200
    assert swapped.json()["recipe_id"] in vegan - {entry["recipe_id"]}


def test_changing_a_cooked_meal_changes_its_leftovers(
    client: TestClient, db: Session
) -> None:
    headers, user = _account(client, db)
    entries = _batch_plan(client, headers, str(_recipe(db, user.id)))
    other = str(_recipe(db, user.id))
    plan_id = entries[0]["meal_plan_id"]

    client.patch(
        f"{API}/{plan_id}/entries/{entries[0]['id']}",
        headers=headers,
        json={"recipe_id": other},
    )
    plan = client.get(f"{API}/{plan_id}", headers=headers).json()
    assert {e["recipe_id"] for e in plan["entries"]} == {other}


def test_changing_a_leftover_takes_it_out_of_the_batch(
    client: TestClient, db: Session
) -> None:
    headers, user = _account(client, db)
    first = str(_recipe(db, user.id))
    entries = _batch_plan(client, headers, first)
    other = str(_recipe(db, user.id))

    updated = client.patch(
        f"{API}/{entries[0]['meal_plan_id']}/entries/{entries[1]['id']}",
        headers=headers,
        json={"recipe_id": other},
    ).json()
    assert updated["recipe_id"] == other
    assert updated["batch_of_id"] is None


def test_removing_a_cooked_meal_keeps_its_leftovers(
    client: TestClient, db: Session
) -> None:
    headers, user = _account(client, db)
    entries = _batch_plan(client, headers, str(_recipe(db, user.id)))
    plan_id = entries[0]["meal_plan_id"]

    client.delete(f"{API}/{plan_id}/entries/{entries[0]['id']}", headers=headers)
    plan = client.get(f"{API}/{plan_id}", headers=headers).json()
    assert len(plan["entries"]) == 2
    assert all(e["batch_of_id"] is None for e in plan["entries"])
