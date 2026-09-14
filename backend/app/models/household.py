import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

from app.models.base import get_datetime_utc

if TYPE_CHECKING:
    from app.models.user import User


class HouseholdRole(str, Enum):
    """What a member may do.

    ``OWNER`` can rename the household, invite, and remove members;
    ``MEMBER`` can see and edit the shared lists and plans but not the
    membership itself.
    """

    OWNER = "owner"
    MEMBER = "member"


# --------------------------------------------------------------------------- #
# Household schemas                                                            #
# --------------------------------------------------------------------------- #


class HouseholdBase(SQLModel):
    name: str = Field(min_length=1, max_length=255)


class HouseholdCreate(HouseholdBase):
    pass


class HouseholdUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)


class HouseholdMemberPublic(SQLModel):
    id: uuid.UUID
    user_id: uuid.UUID
    email: str
    full_name: str | None = None
    role: HouseholdRole
    joined_at: datetime | None = None


class HouseholdInvitePublic(SQLModel):
    id: uuid.UUID
    email: str
    expires_at: datetime
    accepted_at: datetime | None = None

    @property
    def is_pending(self) -> bool:
        return self.accepted_at is None


class HouseholdPublic(HouseholdBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime | None = None
    members: list[HouseholdMemberPublic] = []
    invites: list[HouseholdInvitePublic] = []
    #: How many more people may be invited, so the UI can disable the form
    #: rather than letting the user discover the cap by hitting it.
    seats_remaining: int = 0


class HouseholdInviteCreate(SQLModel):
    email: str = Field(min_length=3, max_length=255)


# --------------------------------------------------------------------------- #
# Table models                                                                 #
# --------------------------------------------------------------------------- #


class Household(HouseholdBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE", index=True
    )
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore[call-overload]
    )
    members: list["HouseholdMember"] = Relationship(
        back_populates="household",
        cascade_delete=True,
        sa_relationship_kwargs={"lazy": "selectin"},
    )
    invites: list["HouseholdInvite"] = Relationship(
        back_populates="household",
        cascade_delete=True,
        sa_relationship_kwargs={"lazy": "selectin"},
    )


class HouseholdMember(SQLModel, table=True):
    __table_args__ = (
        # A user belongs to a household at most once, and — enforced in CRUD —
        # to at most one household overall.
        UniqueConstraint("household_id", "user_id", name="uq_household_member"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    household_id: uuid.UUID = Field(
        foreign_key="household.id", nullable=False, ondelete="CASCADE", index=True
    )
    user_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE", index=True
    )
    role: HouseholdRole = Field(default=HouseholdRole.MEMBER)
    joined_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore[call-overload]
    )
    household: Household = Relationship(back_populates="members")
    user: "User" = Relationship(sa_relationship_kwargs={"lazy": "selectin"})


class HouseholdInvite(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    household_id: uuid.UUID = Field(
        foreign_key="household.id", nullable=False, ondelete="CASCADE", index=True
    )
    email: str = Field(max_length=255, index=True)
    expires_at: datetime = Field(
        sa_type=DateTime(timezone=True),  # type: ignore[call-overload]
    )
    accepted_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore[call-overload]
    )
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore[call-overload]
    )
    household: Household = Relationship(back_populates="invites")
