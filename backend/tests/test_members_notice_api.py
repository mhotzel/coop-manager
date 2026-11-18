"""Kündigung, Teilkündigung und Tod über die API, mit Hauptbuch und Suche (Projektion)."""

import pytest

from coop_manager.accounts.services import open_cooperative_account
from coop_manager.members.domain import NOTICE, PARTIAL_NOTICE
from coop_manager.members.status import DECEASED, MEMBER, NOTICE_GIVEN
from coop_manager.members.values import NATURAL_PERSON
from coop_manager.system_settings.services import change_share_price
from coop_manager.users.domain import ACCOUNTING, ACCOUNTING_READONLY

# Erfundene Testdaten.
APPLICATION = {
    "person_type": NATURAL_PERSON,
    "name": {"first_names": "Erika", "last_name": "Muster", "gender": "w"},
    "address": {"street": "Hauptstraße", "house_number": "1", "postal_code": "12345", "city": "Musterstadt"},
    "application_date": "2026-11-02",
    "shares_subscribed": 3,
}


@pytest.fixture
def member_id(client, db, register, login) -> str:
    """Mitglied seit dem 10.11.2026 mit 3 eingezahlten Anteilen, angemeldet als Buchhaltung."""
    change_share_price(db, 5000, actor="test")
    open_cooperative_account(db, "Musterladen eG", actor="test")
    register("erika", ACCOUNTING)
    login("erika")
    member_id = client.post("/api/members/apply", json=APPLICATION).json()["id"]
    client.post("/api/members/admit", json={"member_id": member_id, "decision_date": "2026-11-05"})
    client.post("/api/accounts/subscribe", json={"account_number": 1, "shares": 3, "value_date": "2026-11-10"})
    return member_id


def search_row(client) -> dict:
    [row] = client.post("/api/members/search", json={"query": "muster"}).json()
    return row


def search_status(client) -> str:
    return search_row(client)["status"]


def test_give_notice_with_default_exit_date(client, member_id):
    response = client.post("/api/members/give-notice", json={"member_id": member_id, "notice_date": "2026-11-12"})

    assert response.status_code == 200
    body = response.json()
    assert (body["status"], body["notice_date"], body["exit_date"]) == (NOTICE_GIVEN, "2026-11-12", "2028-12-31")
    [notice] = body["notices"]
    assert (notice["kind"], notice["shares"]) == (NOTICE, None)
    assert search_status(client) == NOTICE_GIVEN


def test_give_notice_with_own_exit_date(client, member_id):
    body = client.post(
        "/api/members/give-notice",
        json={"member_id": member_id, "notice_date": "2026-11-12", "exit_date": "2027-12-31"},
    ).json()

    assert body["exit_date"] == "2027-12-31"


def test_partial_notice_uses_shares_from_ledger(client, member_id):
    response = client.post(
        "/api/members/give-partial-notice", json={"member_id": member_id, "notice_date": "2026-11-12", "shares": 2}
    )

    assert response.status_code == 200
    body = response.json()
    assert (body["status"], body["notice_date"], body["exit_date"]) == (MEMBER, None, None)
    [notice] = body["notices"]
    assert (notice["kind"], notice["shares"], notice["exit_date"]) == (PARTIAL_NOTICE, 2, "2028-12-31")
    assert search_status(client) == MEMBER

    response = client.post(
        "/api/members/give-partial-notice", json={"member_id": member_id, "notice_date": "2026-11-12", "shares": 1}
    )
    assert response.status_code == 400
    assert "höchstens 0 von 1" in response.json()["detail"]


def test_withdraw_notice(client, member_id):
    notice = client.post("/api/members/give-notice", json={"member_id": member_id, "notice_date": "2026-11-12"}).json()[
        "notices"
    ][0]

    response = client.post("/api/members/withdraw-notice", json={"member_id": member_id, "notice_id": notice["id"]})

    assert response.status_code == 200
    body = response.json()
    assert (body["status"], body["notices"], body["exit_date"]) == (MEMBER, [], None)
    assert search_status(client) == MEMBER


def test_no_partial_notice_after_full_notice(client, member_id):
    client.post("/api/members/give-notice", json={"member_id": member_id, "notice_date": "2026-11-12"})
    response = client.post(
        "/api/members/give-partial-notice", json={"member_id": member_id, "notice_date": "2026-11-12", "shares": 1}
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Die Mitgliedschaft ist bereits gekündigt."
    assert search_status(client) == NOTICE_GIVEN


def test_applicant_cannot_give_notice(client, member_id):
    other = client.post(
        "/api/members/apply",
        json=APPLICATION | {"name": {"first_names": "Max", "last_name": "Beispiel", "gender": "m"}},
    ).json()["id"]

    response = client.post("/api/members/give-notice", json={"member_id": other, "notice_date": "2026-11-12"})

    assert response.status_code == 400


def test_readonly_may_not_give_notice(client, register, login, member_id):
    register("rita", ACCOUNTING_READONLY, full_name="Rita Lesend")
    login("rita")
    command = {"member_id": member_id, "notice_date": "2026-11-12"}

    assert client.post("/api/members/give-notice", json=command).status_code == 403
    assert client.post("/api/members/give-partial-notice", json=command | {"shares": 1}).status_code == 403
    assert (
        client.post("/api/members/withdraw-notice", json={"member_id": member_id, "notice_id": "x"}).status_code == 403
    )


def test_partial_notice_is_shown_in_search_and_detail(client, member_id):
    assert search_row(client)["partial_notice"] is False

    body = client.post(
        "/api/members/give-partial-notice", json={"member_id": member_id, "notice_date": "2026-11-12", "shares": 1}
    ).json()

    assert body["partial_notice"] is True
    assert (search_row(client)["status"], search_row(client)["partial_notice"]) == (MEMBER, True)

    client.post("/api/members/withdraw-notice", json={"member_id": member_id, "notice_id": body["notices"][0]["id"]})

    assert search_row(client)["partial_notice"] is False
    assert client.get(f"/api/members/{member_id}").json()["partial_notice"] is False


def test_full_notice_is_not_a_partial_notice(client, member_id):
    client.post("/api/members/give-notice", json={"member_id": member_id, "notice_date": "2026-11-12"})

    assert search_row(client)["partial_notice"] is False


# --- Tod ---


def test_record_death(client, member_id):
    response = client.post("/api/members/record-death", json={"member_id": member_id, "date_of_death": "2026-11-12"})

    assert response.status_code == 200
    body = response.json()
    assert (body["status"], body["date_of_death"], body["exit_date"]) == (DECEASED, "2026-11-12", "2026-12-31")
    assert body["salutation"] == "Sehr geehrte Damen und Herren"
    assert search_status(client) == DECEASED


def test_death_after_notice_shows_earlier_exit(client, member_id):
    client.post("/api/members/give-notice", json={"member_id": member_id, "notice_date": "2026-11-12"})

    body = client.post("/api/members/record-death", json={"member_id": member_id, "date_of_death": "2026-11-13"}).json()

    assert (body["notice_date"], body["exit_date"]) == ("2026-11-12", "2026-12-31")
    assert body["notices"][0]["exit_date"] == "2028-12-31"  # bleibt stehen, ist aber gegenstandslos


def test_revoke_death(client, member_id):
    client.post("/api/members/record-death", json={"member_id": member_id, "date_of_death": "2026-11-12"})

    response = client.post("/api/members/revoke-death", json={"member_id": member_id})

    assert response.status_code == 200
    body = response.json()
    assert (body["status"], body["date_of_death"], body["exit_date"]) == (MEMBER, None, None)
    assert body["salutation"] == "Sehr geehrte Frau Muster"
    assert search_status(client) == MEMBER


def test_revoke_death_without_death_is_400(client, member_id):
    assert client.post("/api/members/revoke-death", json={"member_id": member_id}).status_code == 400


def test_readonly_may_not_record_death(client, register, login, member_id):
    register("rita", ACCOUNTING_READONLY, full_name="Rita Lesend")
    login("rita")

    command = {"member_id": member_id, "date_of_death": "2026-11-12"}
    assert client.post("/api/members/record-death", json=command).status_code == 403
    assert client.post("/api/members/revoke-death", json={"member_id": member_id}).status_code == 403
