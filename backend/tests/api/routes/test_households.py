"""Households — who gets in, and crucially who does not.

The isolation tests here are the point of the feature's test suite: a missed
access check is a data leak, not a cosmetic bug.
"""

import uuid
from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models import MealPlanCreate, ShoppingListCreate
from app.models.base import get_datetime_utc
from tests.utils.user import authentication_token_from_email
from tests.utils.utils import random_lower_string

TODAY = date(2026, 5, 4)


class Account:
    """A user plus their auth headers, for readable multi-user tests."""

    def __init__(self, client: TestClient, db: Session) -> None:
        self.email = f"hh-{random_lower_string()}@example.com"
        self.headers = authentication_token_from_email(
            client=client, email=self.email, db=db
        )
        user = crud.get_user_by_email(session=db, email=self.email)
        assert user is not None
        self.user = user
        self.id = user.id


def _make_household(client: TestClient, account: Account, name: str = "Home") -> dict:
    response = client.post(
        f"{settings.API_V1_STR}/households/",
        headers=account.headers,
        json={"name": name},
    )
    assert response.status_code == 200
    return response.json()


def _join(client: TestClient, owner: Account, joiner: Account) -> None:
    """Invite and accept, which is the only supported way in."""
    invited = client.post(
        f"{settings.API_V1_STR}/households/me/invites",
        headers=owner.headers,
        json={"email": joiner.email},
    )
    assert invited.status_code == 200, invited.text
    invite_id = invited.json()["invites"][0]["id"]
    accepted = client.post(
        f"{settings.API_V1_STR}/households/invites/{invite_id}/accept",
        headers=joiner.headers,
    )
    assert accepted.status_code == 200, accepted.text


def _list_for(db: Session, account: Account) -> object:
    return crud.create_shopping_list(
        session=db,
        list_in=ShoppingListCreate(name=random_lower_string()),
        owner_id=account.id,
    )


def _plan_for(db: Session, account: Account) -> object:
    return crud.create_meal_plan(
        session=db,
        plan_in=MealPlanCreate(
            name=random_lower_string(), start_date=TODAY, end_date=TODAY
        ),
        owner_id=account.id,
    )


# --------------------------------------------------------------------------- #
# Creating and joining                                                         #
# --------------------------------------------------------------------------- #


def test_creating_a_household_makes_you_its_owner(
    client: TestClient, db: Session
) -> None:
    owner = Account(client, db)
    body = _make_household(client, owner)
    assert body["owner_id"] == str(owner.id)
    assert len(body["members"]) == 1
    assert body["members"][0]["role"] == "owner"


def test_you_cannot_belong_to_two_households(client: TestClient, db: Session) -> None:
    """Two households would make "who can see this list" ambiguous."""
    owner = Account(client, db)
    _make_household(client, owner)
    second = client.post(
        f"{settings.API_V1_STR}/households/",
        headers=owner.headers,
        json={"name": "Other"},
    )
    assert second.status_code == 409


def test_a_user_with_no_household_gets_404(client: TestClient, db: Session) -> None:
    loner = Account(client, db)
    response = client.get(f"{settings.API_V1_STR}/households/me", headers=loner.headers)
    assert response.status_code == 404


def test_invite_and_accept_adds_a_member(client: TestClient, db: Session) -> None:
    owner = Account(client, db)
    guest = Account(client, db)
    _make_household(client, owner)
    _join(client, owner, guest)

    body = client.get(
        f"{settings.API_V1_STR}/households/me", headers=guest.headers
    ).json()
    assert {m["user_id"] for m in body["members"]} == {str(owner.id), str(guest.id)}


def test_an_invite_is_bound_to_its_email(client: TestClient, db: Session) -> None:
    """Knowing an invite id must not be enough to join someone's household."""
    owner = Account(client, db)
    invited = Account(client, db)
    interloper = Account(client, db)
    _make_household(client, owner)

    response = client.post(
        f"{settings.API_V1_STR}/households/me/invites",
        headers=owner.headers,
        json={"email": invited.email},
    )
    invite_id = response.json()["invites"][0]["id"]

    stolen = client.post(
        f"{settings.API_V1_STR}/households/invites/{invite_id}/accept",
        headers=interloper.headers,
    )
    assert stolen.status_code == 403


def test_an_expired_invite_is_refused(client: TestClient, db: Session) -> None:
    owner = Account(client, db)
    guest = Account(client, db)
    _make_household(client, owner)
    client.post(
        f"{settings.API_V1_STR}/households/me/invites",
        headers=owner.headers,
        json={"email": guest.email},
    )
    household = crud.get_household_for_user(session=db, user_id=owner.id)
    assert household is not None
    invite = household.invites[0]
    invite.expires_at = get_datetime_utc() - timedelta(hours=1)
    db.add(invite)
    db.commit()

    response = client.post(
        f"{settings.API_V1_STR}/households/invites/{invite.id}/accept",
        headers=guest.headers,
    )
    assert response.status_code == 409


def test_an_invite_cannot_be_accepted_twice(client: TestClient, db: Session) -> None:
    owner = Account(client, db)
    guest = Account(client, db)
    _make_household(client, owner)
    invited = client.post(
        f"{settings.API_V1_STR}/households/me/invites",
        headers=owner.headers,
        json={"email": guest.email},
    )
    invite_id = invited.json()["invites"][0]["id"]
    client.post(
        f"{settings.API_V1_STR}/households/invites/{invite_id}/accept",
        headers=guest.headers,
    )
    again = client.post(
        f"{settings.API_V1_STR}/households/invites/{invite_id}/accept",
        headers=guest.headers,
    )
    assert again.status_code == 409


def test_inviting_an_existing_member_is_refused(
    client: TestClient, db: Session
) -> None:
    owner = Account(client, db)
    guest = Account(client, db)
    _make_household(client, owner)
    _join(client, owner, guest)

    again = client.post(
        f"{settings.API_V1_STR}/households/me/invites",
        headers=owner.headers,
        json={"email": guest.email},
    )
    assert again.status_code == 409


def test_a_duplicate_pending_invite_is_refused(client: TestClient, db: Session) -> None:
    owner = Account(client, db)
    guest = Account(client, db)
    _make_household(client, owner)
    for _ in range(1):
        client.post(
            f"{settings.API_V1_STR}/households/me/invites",
            headers=owner.headers,
            json={"email": guest.email},
        )
    again = client.post(
        f"{settings.API_V1_STR}/households/me/invites",
        headers=owner.headers,
        json={"email": guest.email},
    )
    assert again.status_code == 409


def test_the_member_cap_counts_pending_invites(client: TestClient, db: Session) -> None:
    """Otherwise five outstanding invites would let a sixth person in."""
    owner = Account(client, db)
    _make_household(client, owner)

    # Owner already holds one seat, so MAX - 1 invites fill the household.
    for _ in range(settings.MAX_HOUSEHOLD_MEMBERS - 1):
        response = client.post(
            f"{settings.API_V1_STR}/households/me/invites",
            headers=owner.headers,
            json={"email": f"pending-{random_lower_string()}@example.com"},
        )
        assert response.status_code == 200

    overflow = client.post(
        f"{settings.API_V1_STR}/households/me/invites",
        headers=owner.headers,
        json={"email": f"one-too-many-{random_lower_string()}@example.com"},
    )
    assert overflow.status_code == 409
    assert response.json()["seats_remaining"] == 0


def test_revoking_an_invite_frees_its_seat(client: TestClient, db: Session) -> None:
    owner = Account(client, db)
    _make_household(client, owner)
    invited = client.post(
        f"{settings.API_V1_STR}/households/me/invites",
        headers=owner.headers,
        json={"email": f"x-{random_lower_string()}@example.com"},
    ).json()
    before = invited["seats_remaining"]

    client.delete(
        f"{settings.API_V1_STR}/households/me/invites/{invited['invites'][0]['id']}",
        headers=owner.headers,
    )
    after = client.get(
        f"{settings.API_V1_STR}/households/me", headers=owner.headers
    ).json()
    assert after["seats_remaining"] == before + 1


# --------------------------------------------------------------------------- #
# Sharing — what a household member gains                                      #
# --------------------------------------------------------------------------- #


def test_a_member_sees_the_households_shopping_lists(
    client: TestClient, db: Session
) -> None:
    owner = Account(client, db)
    guest = Account(client, db)
    _make_household(client, owner)
    _join(client, owner, guest)
    owners_list = _list_for(db, owner)

    listed = client.get(
        f"{settings.API_V1_STR}/shopping-lists/", headers=guest.headers
    ).json()
    assert str(owners_list.id) in {sl["id"] for sl in listed["data"]}  # type: ignore[attr-defined]

    fetched = client.get(
        f"{settings.API_V1_STR}/shopping-lists/{owners_list.id}",  # type: ignore[attr-defined]
        headers=guest.headers,
    )
    assert fetched.status_code == 200


def test_a_member_can_edit_the_households_shopping_list(
    client: TestClient, db: Session
) -> None:
    """Sharing that is read-only would not be sharing a shopping list."""
    owner = Account(client, db)
    guest = Account(client, db)
    _make_household(client, owner)
    _join(client, owner, guest)
    owners_list = _list_for(db, owner)

    response = client.post(
        f"{settings.API_V1_STR}/shopping-lists/{owners_list.id}/items",  # type: ignore[attr-defined]
        headers=guest.headers,
        json={"name": "milk", "quantity": 1, "unit": "L"},
    )
    assert response.status_code == 200


def test_a_member_sees_the_households_meal_plans(
    client: TestClient, db: Session
) -> None:
    owner = Account(client, db)
    guest = Account(client, db)
    _make_household(client, owner)
    _join(client, owner, guest)
    owners_plan = _plan_for(db, owner)

    listed = client.get(
        f"{settings.API_V1_STR}/meal-plans/", headers=guest.headers
    ).json()
    assert str(owners_plan.id) in {p["id"] for p in listed["data"]}  # type: ignore[attr-defined]


# --------------------------------------------------------------------------- #
# Isolation — what a non-member must never gain                                #
# --------------------------------------------------------------------------- #


def test_a_stranger_cannot_read_a_households_list(
    client: TestClient, db: Session
) -> None:
    owner = Account(client, db)
    stranger = Account(client, db)
    _make_household(client, owner)
    owners_list = _list_for(db, owner)

    response = client.get(
        f"{settings.API_V1_STR}/shopping-lists/{owners_list.id}",  # type: ignore[attr-defined]
        headers=stranger.headers,
    )
    assert response.status_code == 403


def test_a_stranger_cannot_write_to_a_households_list(
    client: TestClient, db: Session
) -> None:
    owner = Account(client, db)
    stranger = Account(client, db)
    _make_household(client, owner)
    owners_list = _list_for(db, owner)

    response = client.post(
        f"{settings.API_V1_STR}/shopping-lists/{owners_list.id}/items",  # type: ignore[attr-defined]
        headers=stranger.headers,
        json={"name": "milk", "quantity": 1, "unit": "L"},
    )
    assert response.status_code == 403


def test_a_members_of_another_household_are_kept_apart(
    client: TestClient, db: Session
) -> None:
    """Two households must not leak into one another."""
    owner_a = Account(client, db)
    owner_b = Account(client, db)
    _make_household(client, owner_a, "A")
    _make_household(client, owner_b, "B")
    list_a = _list_for(db, owner_a)

    response = client.get(
        f"{settings.API_V1_STR}/shopping-lists/{list_a.id}",  # type: ignore[attr-defined]
        headers=owner_b.headers,
    )
    assert response.status_code == 403


def test_leaving_a_household_ends_the_sharing(client: TestClient, db: Session) -> None:
    owner = Account(client, db)
    guest = Account(client, db)
    _make_household(client, owner)
    _join(client, owner, guest)
    owners_list = _list_for(db, owner)

    assert (
        client.get(
            f"{settings.API_V1_STR}/shopping-lists/{owners_list.id}",  # type: ignore[attr-defined]
            headers=guest.headers,
        ).status_code
        == 200
    )

    client.post(f"{settings.API_V1_STR}/households/me/leave", headers=guest.headers)

    assert (
        client.get(
            f"{settings.API_V1_STR}/shopping-lists/{owners_list.id}",  # type: ignore[attr-defined]
            headers=guest.headers,
        ).status_code
        == 403
    )


def test_being_removed_ends_the_sharing(client: TestClient, db: Session) -> None:
    owner = Account(client, db)
    guest = Account(client, db)
    _make_household(client, owner)
    _join(client, owner, guest)
    owners_list = _list_for(db, owner)

    household = client.get(
        f"{settings.API_V1_STR}/households/me", headers=owner.headers
    ).json()
    member_id = next(
        m["id"] for m in household["members"] if m["user_id"] == str(guest.id)
    )
    removed = client.delete(
        f"{settings.API_V1_STR}/households/me/members/{member_id}",
        headers=owner.headers,
    )
    assert removed.status_code == 200

    assert (
        client.get(
            f"{settings.API_V1_STR}/shopping-lists/{owners_list.id}",  # type: ignore[attr-defined]
            headers=guest.headers,
        ).status_code
        == 403
    )


def test_disbanding_ends_the_sharing_but_keeps_the_lists(
    client: TestClient, db: Session
) -> None:
    owner = Account(client, db)
    guest = Account(client, db)
    _make_household(client, owner)
    _join(client, owner, guest)
    owners_list = _list_for(db, owner)

    client.delete(f"{settings.API_V1_STR}/households/me", headers=owner.headers)

    # The guest loses access ...
    assert (
        client.get(
            f"{settings.API_V1_STR}/shopping-lists/{owners_list.id}",  # type: ignore[attr-defined]
            headers=guest.headers,
        ).status_code
        == 403
    )
    # ... but the owner's own list is untouched.
    assert (
        client.get(
            f"{settings.API_V1_STR}/shopping-lists/{owners_list.id}",  # type: ignore[attr-defined]
            headers=owner.headers,
        ).status_code
        == 200
    )


# --------------------------------------------------------------------------- #
# Roles                                                                        #
# --------------------------------------------------------------------------- #


def test_a_plain_member_cannot_invite(client: TestClient, db: Session) -> None:
    owner = Account(client, db)
    guest = Account(client, db)
    _make_household(client, owner)
    _join(client, owner, guest)

    response = client.post(
        f"{settings.API_V1_STR}/households/me/invites",
        headers=guest.headers,
        json={"email": f"x-{random_lower_string()}@example.com"},
    )
    assert response.status_code == 403


def test_a_plain_member_cannot_rename_or_disband(
    client: TestClient, db: Session
) -> None:
    owner = Account(client, db)
    guest = Account(client, db)
    _make_household(client, owner)
    _join(client, owner, guest)

    assert (
        client.patch(
            f"{settings.API_V1_STR}/households/me",
            headers=guest.headers,
            json={"name": "Hijacked"},
        ).status_code
        == 403
    )
    assert (
        client.delete(
            f"{settings.API_V1_STR}/households/me", headers=guest.headers
        ).status_code
        == 403
    )


def test_the_owner_cannot_leave_only_disband(client: TestClient, db: Session) -> None:
    """Leaving would silently orphan everyone else; disbanding is explicit."""
    owner = Account(client, db)
    _make_household(client, owner)
    response = client.post(
        f"{settings.API_V1_STR}/households/me/leave", headers=owner.headers
    )
    assert response.status_code == 409


def test_the_owner_cannot_remove_themselves(client: TestClient, db: Session) -> None:
    owner = Account(client, db)
    household = _make_household(client, owner)
    member_id = household["members"][0]["id"]
    response = client.delete(
        f"{settings.API_V1_STR}/households/me/members/{member_id}",
        headers=owner.headers,
    )
    assert response.status_code == 409


def test_a_member_from_another_household_cannot_be_removed(
    client: TestClient, db: Session
) -> None:
    owner_a = Account(client, db)
    owner_b = Account(client, db)
    _make_household(client, owner_a, "A")
    b = _make_household(client, owner_b, "B")

    response = client.delete(
        f"{settings.API_V1_STR}/households/me/members/{b['members'][0]['id']}",
        headers=owner_a.headers,
    )
    assert response.status_code == 404


def test_unknown_ids_give_404s(client: TestClient, db: Session) -> None:
    owner = Account(client, db)
    _make_household(client, owner)
    missing = uuid.uuid4()

    assert (
        client.delete(
            f"{settings.API_V1_STR}/households/me/invites/{missing}",
            headers=owner.headers,
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"{settings.API_V1_STR}/households/invites/{missing}/accept",
            headers=owner.headers,
        ).status_code
        == 404
    )
