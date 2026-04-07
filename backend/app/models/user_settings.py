import uuid
from enum import Enum
from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.user import User


class ShoppingFrequency(str, Enum):
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"


# --------------------------------------------------------------------------- #
# UserSettings schemas                                                         #
# --------------------------------------------------------------------------- #


class UserSettingsBase(SQLModel):
    household_size: int = Field(default=2, ge=1)
    shopping_frequency: ShoppingFrequency = Field(default=ShoppingFrequency.WEEKLY)


class UserSettingsUpdate(SQLModel):
    household_size: int | None = Field(default=None, ge=1)
    shopping_frequency: ShoppingFrequency | None = None


class UserSettingsPublic(UserSettingsBase):
    id: uuid.UUID
    user_id: uuid.UUID


# --------------------------------------------------------------------------- #
# UserSettings table model                                                     #
# --------------------------------------------------------------------------- #


class UserSettings(UserSettingsBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE", unique=True
    )
    owner: "User" = Relationship(back_populates="settings")
