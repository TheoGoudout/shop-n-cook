import uuid

from sqlmodel import Session, select

from app.models.user_settings import UserSettings, UserSettingsUpdate


def get_user_settings(*, session: Session, user_id: uuid.UUID) -> UserSettings | None:
    return session.exec(
        select(UserSettings).where(UserSettings.user_id == user_id)
    ).first()


def get_or_create_user_settings(
    *, session: Session, user_id: uuid.UUID
) -> UserSettings:
    settings = get_user_settings(session=session, user_id=user_id)
    if settings is None:
        settings = UserSettings(user_id=user_id)
        session.add(settings)
        session.commit()
        session.refresh(settings)
    return settings


def update_user_settings(
    *,
    session: Session,
    settings: UserSettings,
    update_in: UserSettingsUpdate,
) -> UserSettings:
    update_data = update_in.model_dump(exclude_unset=True)
    settings.sqlmodel_update(update_data)
    session.add(settings)
    session.commit()
    session.refresh(settings)
    return settings
