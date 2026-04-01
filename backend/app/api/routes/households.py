import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import select

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    Household,
    HouseholdCreate,
    HouseholdMember,
    HouseholdMemberPublic,
    HouseholdPublic,
    HouseholdsPublic,
    HouseholdUpdate,
    Message,
    User,
)

router = APIRouter(prefix="/households", tags=["households"])


def _to_public(household: Household, session: SessionDep) -> HouseholdPublic:
    members: list[HouseholdMemberPublic] = []
    for m in household.members:
        user = session.get(User, m.user_id)
        if user:
            members.append(
                HouseholdMemberPublic(
                    user_id=user.id,
                    user_email=user.email,
                    user_full_name=user.full_name,
                )
            )
    return HouseholdPublic(
        id=household.id,
        name=household.name,
        owner_id=household.owner_id,
        created_at=household.created_at,
        members=members,
        member_count=len(members),
    )


@router.get("/", response_model=HouseholdsPublic)
def read_households(session: SessionDep, current_user: CurrentUser) -> Any:
    """Return households the user owns or belongs to."""
    owned = session.exec(
        select(Household).where(Household.owner_id == current_user.id)
    ).all()

    member_of_ids = session.exec(
        select(HouseholdMember.household_id).where(
            HouseholdMember.user_id == current_user.id
        )
    ).all()

    extra: list[Household] = []
    for hid in member_of_ids:
        h = session.get(Household, hid)
        if h and h.owner_id != current_user.id:
            extra.append(h)

    all_households = list(owned) + extra
    data = [_to_public(h, session) for h in all_households]
    return HouseholdsPublic(data=data, count=len(data))


@router.get("/{id}", response_model=HouseholdPublic)
def read_household(session: SessionDep, current_user: CurrentUser, id: uuid.UUID) -> Any:
    household = session.get(Household, id)
    if not household:
        raise HTTPException(status_code=404, detail="Household not found")
    _assert_access(household, current_user, session)
    return _to_public(household, session)


@router.post("/", response_model=HouseholdPublic)
def create_household(
    *, session: SessionDep, current_user: CurrentUser, household_in: HouseholdCreate
) -> Any:
    household = Household(name=household_in.name, owner_id=current_user.id)
    session.add(household)
    session.flush()
    # Owner is automatically a member
    member = HouseholdMember(household_id=household.id, user_id=current_user.id)
    session.add(member)
    session.commit()
    session.refresh(household)
    return _to_public(household, session)


@router.put("/{id}", response_model=HouseholdPublic)
def update_household(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    household_in: HouseholdUpdate,
) -> Any:
    household = session.get(Household, id)
    if not household:
        raise HTTPException(status_code=404, detail="Household not found")
    if household.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    if household_in.name is not None:
        household.name = household_in.name
    session.add(household)
    session.commit()
    session.refresh(household)
    return _to_public(household, session)


@router.delete("/{id}")
def delete_household(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Message:
    household = session.get(Household, id)
    if not household:
        raise HTTPException(status_code=404, detail="Household not found")
    if household.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    session.delete(household)
    session.commit()
    return Message(message="Household deleted successfully")


@router.post("/{id}/members")
def add_member(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    user_email: str,
) -> HouseholdPublic:
    household = session.get(Household, id)
    if not household:
        raise HTTPException(status_code=404, detail="Household not found")
    if household.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    user = session.exec(select(User).where(User.email == user_email)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    existing = session.exec(
        select(HouseholdMember)
        .where(HouseholdMember.household_id == id)
        .where(HouseholdMember.user_id == user.id)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="User already a member")

    member = HouseholdMember(household_id=id, user_id=user.id)
    session.add(member)
    session.commit()
    session.refresh(household)
    return _to_public(household, session)


@router.delete("/{id}/members/{user_id}")
def remove_member(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    user_id: uuid.UUID,
) -> HouseholdPublic:
    household = session.get(Household, id)
    if not household:
        raise HTTPException(status_code=404, detail="Household not found")
    if household.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot remove the owner")

    member = session.exec(
        select(HouseholdMember)
        .where(HouseholdMember.household_id == id)
        .where(HouseholdMember.user_id == user_id)
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    session.delete(member)
    session.commit()
    session.refresh(household)
    return _to_public(household, session)


def _assert_access(household: Household, current_user: Any, session: SessionDep) -> None:
    if household.owner_id == current_user.id:
        return
    member = session.exec(
        select(HouseholdMember)
        .where(HouseholdMember.household_id == household.id)
        .where(HouseholdMember.user_id == current_user.id)
    ).first()
    if not member:
        raise HTTPException(status_code=403, detail="Not enough permissions")
