import uuid
from datetime import datetime

from pydantic import EmailStr
from sqlalchemy import DateTime
from sqlmodel import Field, Relationship, SQLModel

from app.models.base import get_datetime_utc

# --------------------------------------------------------------------------- #
# Auth / token schemas                                                         #
# --------------------------------------------------------------------------- #


class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(SQLModel):
    sub: str | None = None


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


# --------------------------------------------------------------------------- #
# User schemas                                                                 #
# --------------------------------------------------------------------------- #


class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserRegister(SQLModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


class UserUpdate(UserBase):
    email: EmailStr | None = Field(default=None, max_length=255)  # type: ignore
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


# --------------------------------------------------------------------------- #
# User table model                                                             #
# --------------------------------------------------------------------------- #


class User(UserBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    # Forward references — related models are defined in other modules, loaded via __init__
    recipes: list["Recipe"] = Relationship(back_populates="owner", cascade_delete=True)  # type: ignore[name-defined]  # noqa: F821
    shopping_lists: list["ShoppingList"] = Relationship(  # type: ignore[name-defined]  # noqa: F821
        back_populates="owner", cascade_delete=True
    )
    settings: "UserSettings" = Relationship(back_populates="owner", cascade_delete=True)  # type: ignore[name-defined]  # noqa: F821


# --------------------------------------------------------------------------- #
# User response schemas                                                        #
# --------------------------------------------------------------------------- #


class UserPublic(UserBase):
    id: uuid.UUID
    created_at: datetime | None = None


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int
