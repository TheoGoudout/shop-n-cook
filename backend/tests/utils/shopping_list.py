import uuid

from sqlmodel import Session

from app import crud
from app.models import ShoppingListCreate
from tests.utils.utils import random_lower_string


def create_random_shopping_list(db: Session, owner_id: uuid.UUID) -> object:
    name = random_lower_string()
    list_in = ShoppingListCreate(name=name)
    return crud.create_shopping_list(session=db, list_in=list_in, owner_id=owner_id)
