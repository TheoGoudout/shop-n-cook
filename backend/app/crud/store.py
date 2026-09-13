import uuid

from sqlmodel import Session, col, func, select

from app.models.ingredient import Ingredient
from app.models.store import (
    IngredientPrice,
    IngredientPriceCreate,
    IngredientPricePublic,
    IngredientPriceUpdate,
    Store,
    StoreCreate,
    StorePublic,
    StoreUpdate,
)


def store_to_public(store: Store) -> StorePublic:
    return StorePublic.model_validate(store, from_attributes=True)


def ingredient_price_to_public(price: IngredientPrice) -> IngredientPricePublic:
    return IngredientPricePublic(
        id=price.id,
        ingredient_id=price.ingredient_id,
        store_id=price.store_id,
        store_name=price.store.name if price.store else None,
        price_amount=price.price_amount,
        price_quantity=price.price_quantity,
        price_unit=price.price_unit,
        updated_at=price.updated_at,
    )


# --------------------------------------------------------------------------- #
# Stores                                                                       #
# --------------------------------------------------------------------------- #


def get_store(*, session: Session, store_id: uuid.UUID) -> Store | None:
    return session.get(Store, store_id)


def get_store_by_slug(*, session: Session, slug: str) -> Store | None:
    return session.exec(select(Store).where(Store.slug == slug)).first()


def get_stores(
    *,
    session: Session,
    active_only: bool = True,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[Store], int]:
    query = select(Store)
    count_query = select(func.count()).select_from(Store)
    if active_only:
        query = query.where(Store.is_active == True)  # noqa: E712
        count_query = count_query.where(Store.is_active == True)  # noqa: E712

    count = session.exec(count_query).one()
    stores = session.exec(
        query.order_by(col(Store.name)).offset(skip).limit(limit)
    ).all()
    return list(stores), count


def create_store(*, session: Session, store_in: StoreCreate) -> Store:
    store = Store(**store_in.model_dump())
    session.add(store)
    session.commit()
    session.refresh(store)
    return store


def update_store(*, session: Session, store: Store, update_in: StoreUpdate) -> Store:
    store.sqlmodel_update(update_in.model_dump(exclude_unset=True))
    session.add(store)
    session.commit()
    session.refresh(store)
    return store


def delete_store(*, session: Session, store: Store) -> None:
    session.delete(store)
    session.commit()


# --------------------------------------------------------------------------- #
# Per-store ingredient prices                                                  #
# --------------------------------------------------------------------------- #


def get_ingredient_prices(
    *, session: Session, ingredient_id: uuid.UUID
) -> list[IngredientPrice]:
    return list(
        session.exec(
            select(IngredientPrice).where(
                IngredientPrice.ingredient_id == ingredient_id
            )
        ).all()
    )


def get_ingredient_price(
    *, session: Session, ingredient_id: uuid.UUID, store_id: uuid.UUID
) -> IngredientPrice | None:
    return session.exec(
        select(IngredientPrice).where(
            IngredientPrice.ingredient_id == ingredient_id,
            IngredientPrice.store_id == store_id,
        )
    ).first()


def upsert_ingredient_price(
    *,
    session: Session,
    ingredient: Ingredient,
    price_in: IngredientPriceCreate,
) -> IngredientPrice:
    """Set this ingredient's price at one store, replacing any existing row.

    Upsert rather than insert because (ingredient, store) is unique — an admin
    correcting a price should not have to delete the old one first.
    """
    existing = get_ingredient_price(
        session=session, ingredient_id=ingredient.id, store_id=price_in.store_id
    )
    if existing is not None:
        existing.price_amount = price_in.price_amount
        existing.price_quantity = price_in.price_quantity
        existing.price_unit = price_in.price_unit
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    price = IngredientPrice(
        ingredient_id=ingredient.id,
        store_id=price_in.store_id,
        price_amount=price_in.price_amount,
        price_quantity=price_in.price_quantity,
        price_unit=price_in.price_unit,
    )
    session.add(price)
    session.commit()
    session.refresh(price)
    return price


def update_ingredient_price(
    *, session: Session, price: IngredientPrice, update_in: IngredientPriceUpdate
) -> IngredientPrice:
    price.sqlmodel_update(update_in.model_dump(exclude_unset=True))
    session.add(price)
    session.commit()
    session.refresh(price)
    return price


def delete_ingredient_price(*, session: Session, price: IngredientPrice) -> None:
    session.delete(price)
    session.commit()
