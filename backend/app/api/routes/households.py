import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app import crud
from app.api.deps import CurrentUser, SessionDep
from app.core.config import settings
from app.models import Message, User
from app.models.base import get_datetime_utc
from app.models.household import (
    Household,
    HouseholdCreate,
    HouseholdInviteCreate,
    HouseholdPublic,
    HouseholdRole,
    HouseholdUpdate,
)
from app.utils import generate_household_invite_email, send_email

router = APIRouter(prefix="/households", tags=["households"])


def _require_membership(*, session: SessionDep, current_user: User) -> Household:
    household = crud.get_household_for_user(session=session, user_id=current_user.id)
    if household is None:
        raise HTTPException(status_code=404, detail="You are not in a household")
    return household


def _require_owner(*, session: SessionDep, current_user: User) -> Household:
    """Membership changes are the owner's to make."""
    household = _require_membership(session=session, current_user=current_user)
    membership = crud.get_membership(session=session, user_id=current_user.id)
    if membership is None or membership.role is not HouseholdRole.OWNER:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return household


@router.get("/me", response_model=HouseholdPublic)
def read_my_household(session: SessionDep, current_user: CurrentUser) -> Any:
    """The household this user belongs to, with its members and open invites."""
    household = _require_membership(session=session, current_user=current_user)
    return crud.household_to_public(household)


@router.post("/", response_model=HouseholdPublic)
def create_household(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    household_in: HouseholdCreate,
) -> Any:
    """Start a household, becoming its first member and owner."""
    if crud.get_membership(session=session, user_id=current_user.id) is not None:
        raise HTTPException(status_code=409, detail="You already belong to a household")
    household = crud.create_household(
        session=session, household_in=household_in, owner=current_user
    )
    return crud.household_to_public(household)


@router.patch("/me", response_model=HouseholdPublic)
def update_my_household(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    update_in: HouseholdUpdate,
) -> Any:
    """Rename the household. Owner only."""
    household = _require_owner(session=session, current_user=current_user)
    household = crud.update_household(
        session=session, household=household, update_in=update_in
    )
    return crud.household_to_public(household)


@router.delete("/me")
def delete_my_household(session: SessionDep, current_user: CurrentUser) -> Message:
    """Disband the household. Owner only.

    Members' own recipes, lists and plans are untouched — only the sharing
    between them ends.
    """
    household = _require_owner(session=session, current_user=current_user)
    crud.delete_household(session=session, household=household)
    return Message(message="Household deleted successfully")


@router.post("/me/leave")
def leave_my_household(session: SessionDep, current_user: CurrentUser) -> Message:
    """Leave the household.

    The owner cannot leave — they disband it instead, which makes the outcome
    explicit rather than silently orphaning everyone else.
    """
    _require_membership(session=session, current_user=current_user)
    membership = crud.get_membership(session=session, user_id=current_user.id)
    assert membership is not None
    if membership.role is HouseholdRole.OWNER:
        raise HTTPException(
            status_code=409,
            detail="The owner cannot leave; delete the household instead",
        )
    crud.remove_member(session=session, member=membership)
    return Message(message="You have left the household")


# --------------------------------------------------------------------------- #
# Members and invites                                                          #
# --------------------------------------------------------------------------- #


@router.delete("/me/members/{member_id}")
def remove_member(
    session: SessionDep, current_user: CurrentUser, member_id: uuid.UUID
) -> Message:
    """Remove someone from the household. Owner only."""
    household = _require_owner(session=session, current_user=current_user)
    member = crud.get_member(session=session, member_id=member_id)
    if not member or member.household_id != household.id:
        raise HTTPException(status_code=404, detail="Member not found")
    if member.user_id == current_user.id:
        raise HTTPException(
            status_code=409, detail="Use leave or delete instead of removing yourself"
        )
    crud.remove_member(session=session, member=member)
    return Message(message="Member removed successfully")


@router.post("/me/invites", response_model=HouseholdPublic)
def invite_member(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    invite_in: HouseholdInviteCreate,
    background_tasks: BackgroundTasks,
) -> Any:
    """Invite someone by email. Owner only.

    A pending invite holds a seat, so inviting five people and waiting does not
    let a sixth in through the gap.
    """
    household = _require_owner(session=session, current_user=current_user)
    email = invite_in.email.strip().lower()

    if email == current_user.email.lower():
        raise HTTPException(status_code=409, detail="You are already a member")
    if any(m.user.email.lower() == email for m in household.members):
        raise HTTPException(status_code=409, detail="Already a member")
    if crud.get_pending_invite_by_email(
        session=session, household_id=household.id, email=email
    ):
        raise HTTPException(status_code=409, detail="Already invited")
    if crud.seats_used(household=household) >= (settings.MAX_HOUSEHOLD_MEMBERS):
        raise HTTPException(
            status_code=409,
            detail=(
                f"A household holds at most {settings.MAX_HOUSEHOLD_MEMBERS} people"
            ),
        )

    invite = crud.create_invite(session=session, household=household, email=email)

    if settings.emails_enabled:
        data = generate_household_invite_email(
            inviter=current_user.full_name or current_user.email.split("@")[0],
            household_name=household.name,
            invite_id=str(invite.id),
        )
        background_tasks.add_task(
            send_email,
            email_to=email,
            subject=data.subject,
            html_content=data.html_content,
        )

    session.refresh(household)
    return crud.household_to_public(household)


@router.delete("/me/invites/{invite_id}")
def revoke_invite(
    session: SessionDep, current_user: CurrentUser, invite_id: uuid.UUID
) -> Message:
    """Withdraw an invitation that has not been accepted. Owner only."""
    household = _require_owner(session=session, current_user=current_user)
    invite = crud.get_invite(session=session, invite_id=invite_id)
    if not invite or invite.household_id != household.id:
        raise HTTPException(status_code=404, detail="Invite not found")
    crud.delete_invite(session=session, invite=invite)
    return Message(message="Invite revoked successfully")


@router.post("/invites/{invite_id}/accept", response_model=HouseholdPublic)
def accept_invite(
    session: SessionDep, current_user: CurrentUser, invite_id: uuid.UUID
) -> Any:
    """Join a household you were invited to.

    The invite is checked against the *logged-in user's own email*, so knowing
    an invite id is not enough to join someone else's household.
    """
    invite = crud.get_invite(session=session, invite_id=invite_id)
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    if invite.accepted_at is not None:
        raise HTTPException(status_code=409, detail="Invite already accepted")
    if invite.expires_at < get_datetime_utc():
        raise HTTPException(status_code=409, detail="Invite has expired")
    if invite.email.lower() != current_user.email.lower():
        raise HTTPException(status_code=403, detail="This invite is not for you")
    if crud.get_membership(session=session, user_id=current_user.id) is not None:
        raise HTTPException(status_code=409, detail="You already belong to a household")

    household = crud.get_household(session=session, household_id=invite.household_id)
    if household is None:
        raise HTTPException(status_code=404, detail="Household not found")
    if crud.seats_used(household=household) > (settings.MAX_HOUSEHOLD_MEMBERS):
        raise HTTPException(status_code=409, detail="This household is full")

    crud.accept_invite(session=session, invite=invite, user=current_user)
    session.refresh(household)
    return crud.household_to_public(household)
