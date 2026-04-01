import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from tests.utils.user import create_random_user, user_authentication_headers
from tests.utils.utils import random_lower_string


def _new_user_headers(client: TestClient, db: Session) -> tuple:
    """Create a fresh user and return (user, headers)."""
    user = create_random_user(db)
    from app import crud
    from app.models import UserUpdate
    pw = random_lower_string()
    crud.update_user(session=db, db_user=user, user_in=UserUpdate(password=pw))
    headers = user_authentication_headers(client=client, email=user.email, password=pw)
    return user, headers


def _create_household(client: TestClient, headers: dict, name: str = "My Home") -> dict:
    r = client.post(
        f"{settings.API_V1_STR}/households/",
        headers=headers,
        json={"name": name},
    )
    assert r.status_code == 200
    return r.json()


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

def test_create_household(client: TestClient, db: Session) -> None:
    _, headers = _new_user_headers(client, db)
    content = _create_household(client, headers, name="Family Home")
    assert content["name"] == "Family Home"
    assert "id" in content
    assert content["member_count"] == 1  # owner auto-added


def test_create_household_missing_name(client: TestClient, db: Session) -> None:
    _, headers = _new_user_headers(client, db)
    r = client.post(
        f"{settings.API_V1_STR}/households/",
        headers=headers,
        json={},
    )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Read list
# ---------------------------------------------------------------------------

def test_read_households_empty(client: TestClient, db: Session) -> None:
    _, headers = _new_user_headers(client, db)
    r = client.get(f"{settings.API_V1_STR}/households/", headers=headers)
    assert r.status_code == 200
    assert r.json()["data"] == []


def test_read_households_returns_owned(client: TestClient, db: Session) -> None:
    _, headers = _new_user_headers(client, db)
    _create_household(client, headers, name="Test House")
    r = client.get(f"{settings.API_V1_STR}/households/", headers=headers)
    assert r.status_code == 200
    names = [h["name"] for h in r.json()["data"]]
    assert "Test House" in names


# ---------------------------------------------------------------------------
# Read single
# ---------------------------------------------------------------------------

def test_read_household(client: TestClient, db: Session) -> None:
    _, headers = _new_user_headers(client, db)
    created = _create_household(client, headers)
    r = client.get(
        f"{settings.API_V1_STR}/households/{created['id']}",
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["id"] == created["id"]


def test_read_household_not_found(client: TestClient, db: Session) -> None:
    _, headers = _new_user_headers(client, db)
    r = client.get(
        f"{settings.API_V1_STR}/households/{uuid.uuid4()}",
        headers=headers,
    )
    assert r.status_code == 404


def test_read_household_not_member(client: TestClient, db: Session) -> None:
    _, headers_a = _new_user_headers(client, db)
    _, headers_b = _new_user_headers(client, db)
    created = _create_household(client, headers_a)

    r = client.get(
        f"{settings.API_V1_STR}/households/{created['id']}",
        headers=headers_b,
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

def test_update_household(client: TestClient, db: Session) -> None:
    _, headers = _new_user_headers(client, db)
    created = _create_household(client, headers, name="Old Name")

    r = client.put(
        f"{settings.API_V1_STR}/households/{created['id']}",
        headers=headers,
        json={"name": "New Name"},
    )
    assert r.status_code == 200
    assert r.json()["name"] == "New Name"


def test_update_household_not_found(client: TestClient, db: Session) -> None:
    _, headers = _new_user_headers(client, db)
    r = client.put(
        f"{settings.API_V1_STR}/households/{uuid.uuid4()}",
        headers=headers,
        json={"name": "x"},
    )
    assert r.status_code == 404


def test_update_household_not_owner(client: TestClient, db: Session) -> None:
    _, headers_a = _new_user_headers(client, db)
    user_b, headers_b = _new_user_headers(client, db)
    created = _create_household(client, headers_a)

    # Add B as member
    client.post(
        f"{settings.API_V1_STR}/households/{created['id']}/members",
        headers=headers_a,
        json={"user_email": user_b.email},
    )

    r = client.put(
        f"{settings.API_V1_STR}/households/{created['id']}",
        headers=headers_b,
        json={"name": "hijack"},
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

def test_delete_household(client: TestClient, db: Session) -> None:
    _, headers = _new_user_headers(client, db)
    created = _create_household(client, headers)

    r = client.delete(
        f"{settings.API_V1_STR}/households/{created['id']}",
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["message"] == "Household deleted successfully"

    r2 = client.get(
        f"{settings.API_V1_STR}/households/{created['id']}",
        headers=headers,
    )
    assert r2.status_code == 404


def test_delete_household_not_found(client: TestClient, db: Session) -> None:
    _, headers = _new_user_headers(client, db)
    r = client.delete(
        f"{settings.API_V1_STR}/households/{uuid.uuid4()}",
        headers=headers,
    )
    assert r.status_code == 404


def test_delete_household_not_owner(client: TestClient, db: Session) -> None:
    _, headers_a = _new_user_headers(client, db)
    user_b, headers_b = _new_user_headers(client, db)
    created = _create_household(client, headers_a)

    client.post(
        f"{settings.API_V1_STR}/households/{created['id']}/members",
        headers=headers_a,
        json={"user_email": user_b.email},
    )

    r = client.delete(
        f"{settings.API_V1_STR}/households/{created['id']}",
        headers=headers_b,
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Members
# ---------------------------------------------------------------------------

def test_add_member(client: TestClient, db: Session) -> None:
    _, headers_a = _new_user_headers(client, db)
    user_b, _ = _new_user_headers(client, db)
    created = _create_household(client, headers_a)

    r = client.post(
        f"{settings.API_V1_STR}/households/{created['id']}/members",
        headers=headers_a,
        params={"user_email": user_b.email},
    )
    assert r.status_code == 200
    emails = [m["user_email"] for m in r.json()["members"]]
    assert user_b.email in emails


def test_add_member_user_not_found(client: TestClient, db: Session) -> None:
    _, headers = _new_user_headers(client, db)
    created = _create_household(client, headers)
    r = client.post(
        f"{settings.API_V1_STR}/households/{created['id']}/members",
        headers=headers,
        params={"user_email": "nonexistent@example.com"},
    )
    assert r.status_code == 404


def test_add_member_already_member(client: TestClient, db: Session) -> None:
    _, headers_a = _new_user_headers(client, db)
    user_b, _ = _new_user_headers(client, db)
    created = _create_household(client, headers_a)

    client.post(
        f"{settings.API_V1_STR}/households/{created['id']}/members",
        headers=headers_a,
        params={"user_email": user_b.email},
    )
    r = client.post(
        f"{settings.API_V1_STR}/households/{created['id']}/members",
        headers=headers_a,
        params={"user_email": user_b.email},
    )
    assert r.status_code == 400


def test_add_member_not_owner(client: TestClient, db: Session) -> None:
    _, headers_a = _new_user_headers(client, db)
    user_b, headers_b = _new_user_headers(client, db)
    user_c, _ = _new_user_headers(client, db)
    created = _create_household(client, headers_a)

    client.post(
        f"{settings.API_V1_STR}/households/{created['id']}/members",
        headers=headers_a,
        params={"user_email": user_b.email},
    )
    r = client.post(
        f"{settings.API_V1_STR}/households/{created['id']}/members",
        headers=headers_b,
        params={"user_email": user_c.email},
    )
    assert r.status_code == 403


def test_remove_member(client: TestClient, db: Session) -> None:
    _, headers_a = _new_user_headers(client, db)
    user_b, _ = _new_user_headers(client, db)
    created = _create_household(client, headers_a)

    client.post(
        f"{settings.API_V1_STR}/households/{created['id']}/members",
        headers=headers_a,
        params={"user_email": user_b.email},
    )
    r = client.delete(
        f"{settings.API_V1_STR}/households/{created['id']}/members/{user_b.id}",
        headers=headers_a,
    )
    assert r.status_code == 200
    emails = [m["user_email"] for m in r.json()["members"]]
    assert user_b.email not in emails


def test_remove_member_cannot_remove_owner(client: TestClient, db: Session) -> None:
    user_a, headers_a = _new_user_headers(client, db)
    created = _create_household(client, headers_a)
    r = client.delete(
        f"{settings.API_V1_STR}/households/{created['id']}/members/{user_a.id}",
        headers=headers_a,
    )
    assert r.status_code == 400


def test_remove_member_not_found(client: TestClient, db: Session) -> None:
    _, headers_a = _new_user_headers(client, db)
    created = _create_household(client, headers_a)
    r = client.delete(
        f"{settings.API_V1_STR}/households/{created['id']}/members/{uuid.uuid4()}",
        headers=headers_a,
    )
    assert r.status_code == 404


def test_member_can_read_household(client: TestClient, db: Session) -> None:
    """A non-owner member should be able to read the household."""
    _, headers_a = _new_user_headers(client, db)
    user_b, headers_b = _new_user_headers(client, db)
    created = _create_household(client, headers_a)

    client.post(
        f"{settings.API_V1_STR}/households/{created['id']}/members",
        headers=headers_a,
        params={"user_email": user_b.email},
    )
    r = client.get(
        f"{settings.API_V1_STR}/households/{created['id']}",
        headers=headers_b,
    )
    assert r.status_code == 200


def test_member_household_appears_in_list(client: TestClient, db: Session) -> None:
    """A user who is a member (not owner) should see the household in their list."""
    _, headers_a = _new_user_headers(client, db)
    user_b, headers_b = _new_user_headers(client, db)
    created = _create_household(client, headers_a, name="Shared House")

    client.post(
        f"{settings.API_V1_STR}/households/{created['id']}/members",
        headers=headers_a,
        params={"user_email": user_b.email},
    )
    r = client.get(f"{settings.API_V1_STR}/households/", headers=headers_b)
    ids = [h["id"] for h in r.json()["data"]]
    assert created["id"] in ids
