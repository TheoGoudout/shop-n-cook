import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

from app.models.base import get_datetime_utc
from app.models.recipe import MealType, Recipe

if TYPE_CHECKING:
    from app.models.user import User


# --------------------------------------------------------------------------- #
# MealPlanEntry schemas                                                        #
# --------------------------------------------------------------------------- #


class MealPlanEntryBase(SQLModel):
    entry_date: date
    meal_type: MealType = Field(default=MealType.DINNER)
    servings: int = Field(default=2, ge=1)


class MealPlanEntryCreate(MealPlanEntryBase):
    recipe_id: uuid.UUID


class MealPlanEntryUpdate(SQLModel):
    entry_date: date | None = None
    meal_type: MealType | None = None
    servings: int | None = Field(default=None, ge=1)
    recipe_id: uuid.UUID | None = None


class MealPlanEntryPublic(MealPlanEntryBase):
    id: uuid.UUID
    meal_plan_id: uuid.UUID
    recipe_id: uuid.UUID
    recipe_title: str
    recipe_image_url: str | None = None
    recipe_servings: int | None = None
    prep_time_minutes: int | None = None
    cook_time_minutes: int | None = None
    #: Cost of this entry at ``servings``, or ``None`` when unpriced.
    estimated_cost: Decimal | None = None
    estimated_cost_per_serving: Decimal | None = None


# --------------------------------------------------------------------------- #
# MealPlanEntry table model                                                    #
# --------------------------------------------------------------------------- #


class MealPlanEntry(MealPlanEntryBase, table=True):
    __table_args__ = (
        # One recipe per slot. Two different recipes on the same evening are a
        # legitimate thing to want, so the constraint includes the recipe.
        UniqueConstraint(
            "meal_plan_id",
            "entry_date",
            "meal_type",
            "recipe_id",
            name="uq_meal_plan_slot_recipe",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    meal_plan_id: uuid.UUID = Field(
        foreign_key="mealplan.id", nullable=False, ondelete="CASCADE", index=True
    )
    recipe_id: uuid.UUID = Field(
        foreign_key="recipe.id", nullable=False, ondelete="CASCADE"
    )
    meal_plan: "MealPlan" = Relationship(back_populates="entries")
    recipe: Recipe = Relationship(sa_relationship_kwargs={"lazy": "selectin"})


# --------------------------------------------------------------------------- #
# MealPlan schemas                                                             #
# --------------------------------------------------------------------------- #


class MealPlanBase(SQLModel):
    name: str = Field(min_length=1, max_length=255)
    start_date: date
    end_date: date


class MealPlanCreate(MealPlanBase):
    pass


class MealPlanUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    start_date: date | None = None
    end_date: date | None = None


class MealPlanPublic(MealPlanBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime | None = None
    #: Set once a shopping list has been generated from this plan, so the UI
    #: can link to it instead of offering to generate a second one.
    shopping_list_id: uuid.UUID | None = None
    entries: list[MealPlanEntryPublic] = []
    estimated_total: Decimal | None = None
    unpriced_entry_count: int = 0
    currency: str = "EUR"


class MealPlansPublic(SQLModel):
    data: list[MealPlanPublic]
    count: int


# --------------------------------------------------------------------------- #
# MealPlan table model                                                         #
# --------------------------------------------------------------------------- #


class MealPlan(MealPlanBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE", index=True
    )
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore[call-overload]
    )
    shopping_list_id: uuid.UUID | None = Field(
        default=None, foreign_key="shoppinglist.id", ondelete="SET NULL"
    )
    owner: "User" = Relationship(back_populates="meal_plans")
    entries: list[MealPlanEntry] = Relationship(
        back_populates="meal_plan",
        cascade_delete=True,
        sa_relationship_kwargs={"lazy": "selectin"},
    )
