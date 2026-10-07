import uuid
from collections.abc import Generator
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from sqlmodel import Session

from app import crud
from app.core import security
from app.core.config import settings
from app.core.db import engine
from app.models import MealPlan, Recipe, ShoppingList, TokenPayload, User
from app.services.pricing import PriceBook

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token"
)


def get_db() -> Generator[Session, None, None]:
    """One session, and one transaction, per request.

    The transaction is committed once the endpoint has returned and its
    response is serialized, and rolled back if anything raised: a request's
    writes land all together or not at all. CRUD functions therefore only
    flush, never commit.

    ``scope="function"`` is what makes this safe: it closes the dependency
    *before* the response is sent, so a failed commit is a 500 rather than a
    200 for data that was never saved.
    """
    with Session(engine) as session:
        yield session
        session.commit()


SessionDep = Annotated[Session, Depends(get_db, scope="function")]
TokenDep = Annotated[str, Depends(reusable_oauth2)]


def get_current_user(session: SessionDep, token: TokenDep) -> User:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except (InvalidTokenError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )
    user = session.get(User, token_data.sub)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_current_active_superuser(current_user: CurrentUser) -> User:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )
    return current_user


def get_price_book(session: SessionDep, current_user: CurrentUser) -> PriceBook:
    """Prices for this request, at the caller's chosen store and currency.

    Loads the catalog once per request so that pricing a list of recipes costs
    a single query rather than one per ingredient.
    """
    user_settings = crud.get_or_create_user_settings(
        session=session, user_id=current_user.id
    )
    store = (
        crud.get_store(session=session, store_id=user_settings.preferred_store_id)
        if user_settings.preferred_store_id
        else None
    )
    return PriceBook.for_catalog(
        session=session, currency=user_settings.currency, store=store
    )


PriceBookDep = Annotated[PriceBook, Depends(get_price_book)]


def get_anonymous_price_book(session: SessionDep) -> PriceBook:
    """Reference prices for routes with no authenticated user."""
    return PriceBook.for_catalog(session=session)


AnonPriceBookDep = Annotated[PriceBook, Depends(get_anonymous_price_book)]


# --------------------------------------------------------------------------- #
# Access to one resource                                                       #
#                                                                              #
# Each rule is decided by a ``crud.user_can_*`` function; these only turn a    #
# missing resource into a 404 and a refusal into a 403, so every route        #
# answers both the same way.                                                   #
# --------------------------------------------------------------------------- #


def forbid_unless(allowed: bool) -> None:
    if not allowed:
        raise HTTPException(status_code=403, detail="Not enough permissions")


def readable_recipe(*, session: Session, user: User, recipe_id: uuid.UUID) -> Recipe:
    """A recipe ``user`` may read, cook or plan: their own, or a public one."""
    recipe = crud.get_recipe(session=session, recipe_id=recipe_id)
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    forbid_unless(crud.user_can_read_recipe(user=user, recipe=recipe))
    return recipe


def shared_shopping_list(
    *, session: Session, user: User, shopping_list_id: uuid.UUID
) -> ShoppingList:
    """A shopping list ``user`` may read and edit: their household's, or theirs."""
    shopping_list = crud.get_shopping_list(
        session=session, shopping_list_id=shopping_list_id
    )
    if shopping_list is None:
        raise HTTPException(status_code=404, detail="Shopping list not found")
    forbid_unless(
        crud.user_can_access(
            session=session, user=user, owner_id=shopping_list.owner_id
        )
    )
    return shopping_list


def get_readable_recipe(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Recipe:
    return readable_recipe(session=session, user=current_user, recipe_id=id)


def get_editable_recipe(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Recipe:
    recipe = crud.get_recipe(session=session, recipe_id=id)
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    forbid_unless(crud.user_can_edit_recipe(user=current_user, recipe=recipe))
    return recipe


def get_shared_shopping_list(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> ShoppingList:
    return shared_shopping_list(session=session, user=current_user, shopping_list_id=id)


def get_shared_meal_plan(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> MealPlan:
    """A meal plan the user may read and edit: their household's, or theirs."""
    plan = crud.get_meal_plan(session=session, plan_id=id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Meal plan not found")
    forbid_unless(
        crud.user_can_access(session=session, user=current_user, owner_id=plan.owner_id)
    )
    return plan


#: The recipe at ``/{id}``, if the caller may read it.
ReadableRecipe = Annotated[Recipe, Depends(get_readable_recipe)]
#: The recipe at ``/{id}``, if the caller may change or delete it.
EditableRecipe = Annotated[Recipe, Depends(get_editable_recipe)]
#: The shopping list at ``/{id}``, if the caller's household shares it.
SharedShoppingList = Annotated[ShoppingList, Depends(get_shared_shopping_list)]
#: The meal plan at ``/{id}``, if the caller's household shares it.
SharedMealPlan = Annotated[MealPlan, Depends(get_shared_meal_plan)]
