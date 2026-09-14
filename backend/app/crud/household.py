"""Households, and the one function that decides who may see a shared resource.

Every ownership check on a shopping list or meal plan goes through
:func:`user_can_access`. Keeping it in one place is the whole point: a second
copy of this rule that drifts is a data leak, not a style problem.
"""

import uuid
from datetime import timedelta

from sqlmodel import Session, col, select

from app.core.config import settings
from app.models.base import get_datetime_utc
from app.models.household import (
    Household,
    HouseholdCreate,
    HouseholdInvite,
    HouseholdInvitePublic,
    HouseholdMember,
    HouseholdMemberPublic,
    HouseholdPublic,
    HouseholdRole,
    HouseholdUpdate,
)
from app.models.user import User


def household_to_public(household: Household) -> HouseholdPublic:
    members = [
        HouseholdMemberPublic(
            id=m.id,
            user_id=m.user_id,
            email=m.user.email,
            full_name=m.user.full_name,
            role=m.role,
            joined_at=m.joined_at,
        )
        for m in sorted(household.members, key=lambda m: (m.role.value, m.id.hex))
    ]
    pending = [
        HouseholdInvitePublic(
            id=i.id,
            email=i.email,
            expires_at=i.expires_at,
            accepted_at=i.accepted_at,
        )
        for i in household.invites
        if i.accepted_at is None
    ]
    used = len(members) + len(pending)
    return HouseholdPublic(
        id=household.id,
        name=household.name,
        owner_id=household.owner_id,
        created_at=household.created_at,
        members=members,
        invites=pending,
        seats_remaining=max(0, settings.MAX_HOUSEHOLD_MEMBERS - used),
    )


# --------------------------------------------------------------------------- #
# Membership lookups                                                           #
# --------------------------------------------------------------------------- #


def get_household(*, session: Session, household_id: uuid.UUID) -> Household | None:
    return session.get(Household, household_id)


def get_membership(*, session: Session, user_id: uuid.UUID) -> HouseholdMember | None:
    """The household this user belongs to, if any.

    A user is in at most one household: sharing a shopping list with two
    different families at once has no sensible meaning, and allowing it would
    make "who can see this list" ambiguous.
    """
    return session.exec(
        select(HouseholdMember).where(HouseholdMember.user_id == user_id)
    ).first()


def get_household_for_user(*, session: Session, user_id: uuid.UUID) -> Household | None:
    membership = get_membership(session=session, user_id=user_id)
    return membership.household if membership else None


def household_member_ids(*, session: Session, user_id: uuid.UUID) -> set[uuid.UUID]:
    """Everyone whose resources this user may see — always including themselves."""
    membership = get_membership(session=session, user_id=user_id)
    if membership is None:
        return {user_id}
    rows = session.exec(
        select(HouseholdMember.user_id).where(
            HouseholdMember.household_id == membership.household_id
        )
    ).all()
    return set(rows) | {user_id}


def user_can_access(*, session: Session, user: User, owner_id: uuid.UUID) -> bool:
    """Whether ``user`` may read and edit a resource owned by ``owner_id``.

    The single rule: your own things, your household's things, or anything at
    all if you are a superuser. Every shopping-list and meal-plan check calls
    this rather than comparing ids itself.
    """
    if user.is_superuser or owner_id == user.id:
        return True
    return owner_id in household_member_ids(session=session, user_id=user.id)


# --------------------------------------------------------------------------- #
# Households                                                                   #
# --------------------------------------------------------------------------- #


def create_household(
    *, session: Session, household_in: HouseholdCreate, owner: User
) -> Household:
    """Create a household with its creator as the first member and owner."""
    household = Household(name=household_in.name, owner_id=owner.id)
    session.add(household)
    session.flush()
    session.add(
        HouseholdMember(
            household_id=household.id,
            user_id=owner.id,
            role=HouseholdRole.OWNER,
        )
    )
    session.commit()
    session.refresh(household)
    return household


def update_household(
    *, session: Session, household: Household, update_in: HouseholdUpdate
) -> Household:
    household.sqlmodel_update(update_in.model_dump(exclude_unset=True))
    session.add(household)
    session.commit()
    session.refresh(household)
    return household


def delete_household(*, session: Session, household: Household) -> None:
    session.delete(household)
    session.commit()


def remove_member(*, session: Session, member: HouseholdMember) -> None:
    session.delete(member)
    session.commit()


def get_member(*, session: Session, member_id: uuid.UUID) -> HouseholdMember | None:
    return session.get(HouseholdMember, member_id)


def seats_used(*, household: Household) -> int:
    """Members plus outstanding invites — a pending invite holds a seat."""
    pending = sum(1 for i in household.invites if i.accepted_at is None)
    return len(household.members) + pending


# --------------------------------------------------------------------------- #
# Invites                                                                      #
# --------------------------------------------------------------------------- #


def get_invite(*, session: Session, invite_id: uuid.UUID) -> HouseholdInvite | None:
    return session.get(HouseholdInvite, invite_id)


def get_pending_invite_by_email(
    *, session: Session, household_id: uuid.UUID, email: str
) -> HouseholdInvite | None:
    return session.exec(
        select(HouseholdInvite).where(
            HouseholdInvite.household_id == household_id,
            col(HouseholdInvite.email) == email.strip().lower(),
            col(HouseholdInvite.accepted_at).is_(None),
        )
    ).first()


def create_invite(
    *, session: Session, household: Household, email: str
) -> HouseholdInvite:
    invite = HouseholdInvite(
        household_id=household.id,
        email=email.strip().lower(),
        expires_at=get_datetime_utc()
        + timedelta(hours=settings.HOUSEHOLD_INVITE_EXPIRE_HOURS),
    )
    session.add(invite)
    session.commit()
    session.refresh(invite)
    return invite


def delete_invite(*, session: Session, invite: HouseholdInvite) -> None:
    session.delete(invite)
    session.commit()


def accept_invite(
    *, session: Session, invite: HouseholdInvite, user: User
) -> HouseholdMember:
    """Turn an invite into a membership."""
    member = HouseholdMember(
        household_id=invite.household_id,
        user_id=user.id,
        role=HouseholdRole.MEMBER,
    )
    invite.accepted_at = get_datetime_utc()
    session.add(member)
    session.add(invite)
    session.commit()
    session.refresh(member)
    return member
