"""Kündigung, Teilkündigung, Tod und Ausschluss über die API, mit Hauptbuch und Suche (Projektion)."""

from datetime import date

import pytest

from coop_manager.accounts.services import open_cooperative_account
from coop_manager.members.domain import NOTICE, PARTIAL_NOTICE
from coop_manager.members.status import DECEASED, EXPELLED, MEMBER, NOTICE_GIVEN
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


# --- Ausschluss ---


def test_expel_and_lift(client, member_id):
    response = client.post("/api/members/expel", json={"member_id": member_id, "decision_date": "2026-11-12"})

    assert response.status_code == 200
    body = response.json()
    assert (body["status"], body["expulsion_date"], body["exit_date"]) == (EXPELLED, "2026-11-12", "2026-12-31")
    assert search_status(client) == EXPELLED

    response = client.post("/api/members/lift-expulsion", json={"member_id": member_id, "decision_date": "2026-11-13"})

    assert response.status_code == 200
    body = response.json()
    assert (body["status"], body["expulsion_date"], body["exit_date"]) == (MEMBER, None, None)
    assert search_status(client) == MEMBER


def test_lift_without_expulsion_is_400(client, member_id):
    response = client.post("/api/members/lift-expulsion", json={"member_id": member_id, "decision_date": "2026-11-13"})

    assert response.status_code == 400


def test_readonly_may_not_expel(client, register, login, member_id):
    register("rita", ACCOUNTING_READONLY, full_name="Rita Lesend")
    login("rita")

    command = {"member_id": member_id, "decision_date": "2026-11-12"}
    assert client.post("/api/members/expel", json=command).status_code == 403
    assert client.post("/api/members/lift-expulsion", json=command).status_code == 403


# --- Ausscheiden zum Jahresende (5g) ---

OLD_APPLICATION = APPLICATION | {"application_date": "2025-01-02"}


@pytest.fixture
def leaving_2025(client, db, register, login) -> str:
    """Mitglied seit dem 10.01.2025, gekündigt zum 31.12.2025; 2025 ist immer abgeschlossen."""
    change_share_price(db, 5000, actor="test")
    open_cooperative_account(db, "Musterladen eG", actor="test")
    register("erika", ACCOUNTING)
    login("erika")
    member_id = client.post("/api/members/apply", json=OLD_APPLICATION).json()["id"]
    client.post("/api/members/admit", json={"member_id": member_id, "decision_date": "2025-01-05"})
    client.post("/api/accounts/subscribe", json={"account_number": 1, "shares": 3, "value_date": "2025-01-10"})
    client.post(
        "/api/members/give-notice",
        json={"member_id": member_id, "notice_date": "2025-02-01", "exit_date": "2025-12-31"},
    )
    return member_id


def test_exits_list_and_post(client, leaving_2025):
    [entry] = client.get("/api/accounts/exits/2025").json()
    assert (entry["member_id"], entry["reasons"], entry["shares"], entry["booked"]) == (
        leaving_2025,
        ["notice"],
        3,
        False,
    )

    response = client.post("/api/accounts/post-exits", json={"year": 2025})

    assert response.status_code == 200
    [entry] = response.json()
    assert (entry["booked"], entry["balance"]) == (True, 15000)
    assert client.get("/api/accounts/1").json()["shares"] == 0


def test_current_year_cannot_be_posted(client, leaving_2025):
    response = client.post("/api/accounts/post-exits", json={"year": date.today().year})

    assert response.status_code == 400


def test_readonly_may_list_but_not_post_exits(client, register, login, leaving_2025):
    register("rita", ACCOUNTING_READONLY, full_name="Rita Lesend")
    login("rita")

    assert client.get("/api/accounts/exits/2025").status_code == 200
    assert client.post("/api/accounts/post-exits", json={"year": 2025}).status_code == 403


def test_implausible_year_is_422(client, leaving_2025):
    assert client.get("/api/accounts/exits/0").status_code == 422
    assert client.post("/api/accounts/post-exits", json={"year": 0}).status_code == 422


# --- Auszahlung, Verlustvortrag, Verjährung (5h-1) ---


def test_payout_deduct_and_write_off(client, leaving_2025):
    client.post("/api/accounts/post-exits", json={"year": 2025})
    assert client.get("/api/accounts/1").json()["claim"] == 15000

    response = client.post(
        "/api/accounts/payout", json={"account_number": 1, "amount": 10000, "value_date": "2026-01-15"}
    )
    assert response.status_code == 200
    assert response.json()["account"]["claim"] == 5000

    response = client.post(
        "/api/accounts/deduct-loss", json={"account_number": 1, "amount": 1000, "value_date": "2026-01-15"}
    )
    assert response.json()["account"]["claim"] == 4000

    response = client.post("/api/accounts/write-off", json={"account_number": 1, "value_date": "2026-01-15"})
    account = response.json()["account"]
    assert (account["claim"], account["balance"], account["shares"]) == (0, 0, 0)
    assert [b["kind"] for b in account["bookings"]][-3:] == ["payout", "loss_deduction", "limitation_writeoff"]


def test_payout_above_claim_is_400(client, leaving_2025):
    client.post("/api/accounts/post-exits", json={"year": 2025})

    response = client.post(
        "/api/accounts/payout", json={"account_number": 1, "amount": 99999, "value_date": "2026-01-15"}
    )

    assert response.status_code == 400


def test_readonly_may_not_pay_out(client, register, login, leaving_2025):
    register("rita", ACCOUNTING_READONLY, full_name="Rita Lesend")
    login("rita")
    command = {"account_number": 1, "amount": 100, "value_date": "2026-01-15"}

    assert client.post("/api/accounts/payout", json=command).status_code == 403
    assert client.post("/api/accounts/deduct-loss", json=command).status_code == 403
    assert client.post("/api/accounts/write-off", json=command).status_code == 403


# --- Offene Ansprüche (5h-2) ---


def test_open_claims(client, leaving_2025):
    assert client.get("/api/accounts/claims").json() == []
    client.post("/api/accounts/post-exits", json={"year": 2025})

    response = client.get("/api/accounts/claims")

    assert response.status_code == 200
    [entry] = response.json()
    assert (entry["member_id"], entry["exit_date"], entry["claim"]) == (leaving_2025, "2025-12-31", 15000)


def test_readonly_may_read_claims(client, register, login, leaving_2025):
    register("rita", ACCOUNTING_READONLY, full_name="Rita Lesend")
    login("rita")

    assert client.get("/api/accounts/claims").status_code == 200


def test_donate_over_api(client, member_id):
    response = client.post("/api/accounts/donate", json={"account_number": 1, "value_date": "2026-11-15"})

    assert response.status_code == 200
    account = response.json()["account"]
    assert (account["balance"], account["shares"]) == (0, 0)
    assert account["bookings"][-1]["kind"] == "share_donation"
    detail = client.get(f"/api/members/{member_id}").json()
    assert (detail["donation_date"], detail["exit_date"], detail["status"]) == ("2026-11-15", "2026-11-15", "exited")
    assert search_status(client) == "exited"


def test_donate_twice_is_400(client, member_id):
    client.post("/api/accounts/donate", json={"account_number": 1, "value_date": "2026-11-15"})

    response = client.post("/api/accounts/donate", json={"account_number": 1, "value_date": "2026-11-16"})

    assert response.status_code == 400


def test_readonly_may_not_donate(client, register, login, member_id):
    register("max", ACCOUNTING_READONLY, "Max Muster")
    login("max")

    response = client.post("/api/accounts/donate", json={"account_number": 1, "value_date": "2026-11-15"})

    assert response.status_code == 403


def test_transfer_over_api(client, member_id):
    heir_id = client.post("/api/members/apply", json=APPLICATION).json()["id"]  # Konto 2
    client.post("/api/members/admit", json={"member_id": heir_id, "decision_date": "2026-11-12"})
    body = {"account_number": 1, "target_account_number": 2, "shares": 3, "value_date": "2026-11-15"}

    response = client.post("/api/accounts/transfer", json=body)

    assert response.status_code == 200
    account = response.json()["account"]
    assert (account["number"], account["shares"], account["bookings"][-1]["kind"]) == (1, 0, "transfer")
    source = client.get(f"/api/members/{member_id}").json()
    assert (source["transfer_date"], source["exit_date"], source["status"]) == ("2026-11-15", "2026-11-15", "exited")
    assert client.get(f"/api/members/{heir_id}").json()["status"] == "member"


def test_transfer_to_unknown_account_is_404(client, member_id):
    body = {"account_number": 1, "target_account_number": 42, "shares": 1, "value_date": "2026-11-15"}

    assert client.post("/api/accounts/transfer", json=body).status_code == 404


def test_additional_shares_over_api(client, member_id):
    body = {"member_id": member_id, "shares": 2, "decision_date": "2026-11-12"}
    detail = client.post("/api/members/subscribe-additional-shares", json=body).json()
    assert detail["additional_shares_open"] == 2
    [subscription] = detail["additional_subscriptions"]
    assert (subscription["shares"], subscription["decision_date"]) == (2, "2026-11-12")

    payment = {"account_number": 1, "shares": 2, "value_date": "2026-11-13"}
    response = client.post("/api/accounts/pay-additional-shares", json=payment)

    assert response.status_code == 200
    assert response.json()["account"]["shares"] == 5
    assert client.get(f"/api/members/{member_id}").json()["additional_shares_open"] == 0
    revoke = {"member_id": member_id, "subscription_id": subscription["id"]}
    assert client.post("/api/members/revoke-additional-shares", json=revoke).status_code == 400
