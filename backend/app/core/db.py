from sqlmodel import Session, create_engine, select

from app import crud
from app.core.config import settings
from app.core.stores_seed import default_store_payloads
from app.models import User, UserCreate

engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))


# make sure all SQLModel models are imported (app.models) before initializing DB
# otherwise, SQLModel might fail to initialize relationships properly
# for more details: https://github.com/fastapi/full-stack-fastapi-template/issues/28


def init_db(session: Session) -> None:
    # Tables should be created with Alembic migrations
    # But if you don't want to use migrations, create
    # the tables un-commenting the next lines
    # from sqlmodel import SQLModel

    # This works because the models are already imported and registered from app.models
    # SQLModel.metadata.create_all(engine)

    user = session.exec(
        select(User).where(User.email == settings.FIRST_SUPERUSER)
    ).first()
    if not user:
        user_in = UserCreate(
            email=settings.FIRST_SUPERUSER,
            password=settings.FIRST_SUPERUSER_PASSWORD,
            is_superuser=True,
        )
        user = crud.create_user(session=session, user_create=user_in)

    seed_stores(session)


def seed_stores(session: Session) -> int:
    """Ensure the default retailers exist. Returns how many were created.

    Matched on slug and only ever inserted, never updated, so an operator who
    retunes a store's price index does not have it reset on the next restart.
    """
    created = 0
    for payload in default_store_payloads():
        if crud.get_store_by_slug(session=session, slug=payload.slug) is None:
            crud.create_store(session=session, store_in=payload)
            created += 1
    return created
