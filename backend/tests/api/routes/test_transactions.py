"""A request is one transaction: its writes land all together or not at all."""

from datetime import date, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlmodel import Session, select

from app import crud
from app.core.config import settings
from app.core.db import engine
from app.crud import meal_plan as meal_plan_crud
from app.models import (
    Household,
    HouseholdCreate,
    HouseholdMember,
    HouseholdRole,
    MealPlan,
    MealPlanCreate,
    MealPlanEntryCreate,
    RecipeCreate,
    RecipeIngredientCreate,
    ShoppingList,
    Unit,
    UserCreate,
)
from tests.utils.utils import random_lower_string

TODAY = date(2026, 3, 2)


def test_a_request_that_fails_midway_saves_nothing(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    """Generating a list writes the list, then each recipe: a failure on the
    second recipe must not leave a half-filled list behind."""
    me = crud.get_user_by_email(session=db, email=settings.EMAIL_TEST_USER)
    assert me is not None
    plan = crud.create_meal_plan(
        session=db,
        plan_in=MealPlanCreate(
            name=random_lower_string(),
            start_date=TODAY,
            end_date=TODAY + timedelta(days=6),
        ),
        owner_id=me.id,
    )
    for offset in (0, 1):
        recipe = crud.create_recipe(
            session=db,
            recipe_in=RecipeCreate(
                title=random_lower_string(),
                ingredients=[
                    RecipeIngredientCreate(
                        ingredient_name=random_lower_string(),
                        quantity=1,
                        unit=Unit.PIECE,
                    )
                ],
            ),
            owner_id=me.id,
        )
        crud.add_entry(
            session=db,
            plan=plan,
            entry_in=MealPlanEntryCreate(
                recipe_id=recipe.id, entry_date=TODAY + timedelta(days=offset)
            ),
        )

    real = meal_plan_crud.add_recipe_to_shopping_list
    calls = 0

    def fail_on_second(**kwargs: object) -> object:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("the database went away")
        return real(**kwargs)  # type: ignore[arg-type]

    with (
        patch.object(
            meal_plan_crud,
            "add_recipe_to_shopping_list",
            side_effect=fail_on_second,
        ),
        pytest.raises(RuntimeError),
    ):
        client.post(
            f"{settings.API_V1_STR}/meal-plans/{plan.id}/shopping-list",
            headers=normal_user_token_headers,
        )
    assert calls == 2

    db.expire_all()
    assert (
        db.exec(select(ShoppingList).where(ShoppingList.name == plan.name)).all() == []
    )
    reread = db.get(MealPlan, plan.id)
    assert reread is not None
    assert reread.shopping_list_id is None


def test_a_refused_request_saves_nothing(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    """An HTTP error raised after a write rolls that write back too."""
    name = random_lower_string()

    def refuse(*_args: object, **_kwargs: object) -> None:
        from fastapi import HTTPException

        raise HTTPException(status_code=409, detail="no")

    with patch(
        "app.api.routes.shopping_lists.crud.shopping_list_to_public",
        side_effect=refuse,
    ):
        response = client.post(
            f"{settings.API_V1_STR}/shopping-lists/",
            headers=normal_user_token_headers,
            json={"name": name},
        )
    assert response.status_code == 409
    assert db.exec(select(ShoppingList).where(ShoppingList.name == name)).all() == []


def test_seat_checks_lock_the_household(db: Session) -> None:
    """While one transaction checks a household's free seats, another cannot.

    Otherwise two invites sent, or accepted, at the same moment could both
    take the last seat.
    """
    owner = crud.create_user(
        session=db,
        user_create=UserCreate(
            email=f"{random_lower_string()}@example.com", password="a-password-1"
        ),
    )
    household = crud.create_household(
        session=db, household_in=HouseholdCreate(name="Locked"), owner=owner
    )
    with Session(engine) as first, Session(engine) as second:
        crud.lock_household(
            session=first,
            household=first.get(Household, household.id),  # type: ignore[arg-type]
        )
        with pytest.raises(OperationalError):
            second.exec(
                select(Household)
                .where(Household.id == household.id)
                .with_for_update(nowait=True)
            ).one()


def test_the_database_refuses_a_second_household_for_one_user(db: Session) -> None:
    user = crud.create_user(
        session=db,
        user_create=UserCreate(
            email=f"{random_lower_string()}@example.com", password="a-password-1"
        ),
    )
    crud.create_household(
        session=db, household_in=HouseholdCreate(name="First"), owner=user
    )
    other = crud.create_user(
        session=db,
        user_create=UserCreate(
            email=f"{random_lower_string()}@example.com", password="a-password-1"
        ),
    )
    second = crud.create_household(
        session=db, household_in=HouseholdCreate(name="Second"), owner=other
    )
    with Session(engine) as session:
        session.add(
            HouseholdMember(
                household_id=second.id, user_id=user.id, role=HouseholdRole.MEMBER
            )
        )
        with pytest.raises(IntegrityError):
            session.flush()
