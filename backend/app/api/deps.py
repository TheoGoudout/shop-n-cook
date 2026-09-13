from collections.abc import Generator
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from sqlmodel import Session

from app.core import security
from app.core.config import settings
from app.core.db import engine
from app.models import TokenPayload, User
from app.services.pricing import PriceBook

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token"
)


def get_db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_db)]
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
    """Reference prices for this request, in the caller's currency.

    Loads the catalog once per request so that pricing a list of recipes costs
    a single query rather than one per ingredient.
    """
    from app import crud

    user_settings = crud.get_or_create_user_settings(
        session=session, user_id=current_user.id
    )
    return PriceBook.for_catalog(session=session, currency=user_settings.currency)


PriceBookDep = Annotated[PriceBook, Depends(get_price_book)]


def get_anonymous_price_book(session: SessionDep) -> PriceBook:
    """Reference prices for routes with no authenticated user."""
    return PriceBook.for_catalog(session=session)


AnonPriceBookDep = Annotated[PriceBook, Depends(get_anonymous_price_book)]
