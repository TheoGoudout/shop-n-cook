from sqlmodel import Session, create_engine

from app import crud
from app.core.config import settings
from app.core.stores_seed import default_store_payloads
from app.models import UserCreate

engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))


# make sure all SQLModel models are imported (app.models) before initializing DB
# otherwise, SQLModel might fail to initialize relationships properly
# for more details: https://github.com/fastapi/full-stack-fastapi-template/issues/28


def init_db(session: Session) -> None:
    """Seed the first superuser and the default stores, in one transaction.

    Tables themselves are created by the Alembic migrations.
    """
    if not crud.get_user_by_email(session=session, email=settings.FIRST_SUPERUSER):
        crud.create_user(
            session=session,
            user_create=UserCreate(
                email=settings.FIRST_SUPERUSER,
                password=settings.FIRST_SUPERUSER_PASSWORD,
                is_superuser=True,
            ),
        )

    seed_stores(session)
    session.commit()


def seed_stores(session: Session) -> int:
    """Ensure the default retailers exist. Returns how many were created.

    Matched on slug and only ever inserted, so an operator who retunes a
    store's price index does not have it reset on the next restart.

    ``provider_slug`` is the one exception and is reconciled every time.
    Unlike the price index it is not a setting anyone tunes — it is derived
    from which providers this build registers, so leaving it stale would mean
    a store that has an integration in the code and none in the database.
    Existing deployments seeded before providers existed pick theirs up here.
    """
    created = 0
    for payload in default_store_payloads():
        existing = crud.get_store_by_slug(session=session, slug=payload.slug)
        if existing is None:
            crud.create_store(session=session, store_in=payload)
            created += 1
        elif existing.provider_slug != payload.provider_slug:
            existing.provider_slug = payload.provider_slug
            session.add(existing)
    return created
