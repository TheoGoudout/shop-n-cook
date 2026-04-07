from typing import Any

from fastapi import APIRouter

from app import crud
from app.api.deps import CurrentUser, SessionDep
from app.models.user_settings import UserSettingsPublic, UserSettingsUpdate

router = APIRouter(prefix="/users/me/settings", tags=["user-settings"])


@router.get("/", response_model=UserSettingsPublic)
def read_user_settings(session: SessionDep, current_user: CurrentUser) -> Any:
    """Get the current user's household settings. Created with defaults if not yet set."""
    return crud.get_or_create_user_settings(session=session, user_id=current_user.id)


@router.put("/", response_model=UserSettingsPublic)
def update_user_settings(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    update_in: UserSettingsUpdate,
) -> Any:
    """Update the current user's household settings."""
    settings = crud.get_or_create_user_settings(
        session=session, user_id=current_user.id
    )
    return crud.update_user_settings(
        session=session, settings=settings, update_in=update_in
    )
