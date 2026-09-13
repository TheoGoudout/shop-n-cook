import uuid
from decimal import Decimal
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
    #: Spending cap for one ``shopping_frequency`` period. ``None`` means the
    #: user has not set a budget and nothing should be reported as over it.
    budget_amount: Decimal | None = Field(
        default=None, max_digits=10, decimal_places=2, ge=0
    )
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    #: Which retailer's prices to cost recipes and lists against. ``None``
    #: means the catalog's own reference prices are used unadjusted.
    preferred_store_id: uuid.UUID | None = Field(default=None)


class UserSettingsUpdate(SQLModel):
    household_size: int | None = Field(default=None, ge=1)
    shopping_frequency: ShoppingFrequency | None = None
    budget_amount: Decimal | None = Field(
        default=None, max_digits=10, decimal_places=2, ge=0
    )
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    preferred_store_id: uuid.UUID | None = None


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
    preferred_store_id: uuid.UUID | None = Field(
        default=None, foreign_key="store.id", ondelete="SET NULL"
    )
    owner: "User" = Relationship(back_populates="settings")
