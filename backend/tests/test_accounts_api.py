import pytest

from coop_manager.accounts.domain import COOPERATIVE_ACCOUNT, COOPERATIVE_ACCOUNT_NUMBER, MEMBER_ACCOUNT
from coop_manager.accounts.services import open_cooperative_account
from coop_manager.members.status import MEMBER
from coop_manager.members.values import NATURAL_PERSON
from coop_manager.system_settings.services import change_share_price
from coop_manager.users.domain import ACCOUNTING, ACCOUNTING_READONLY

# Erfundene Testdaten.
APPLICATION = {
    "person_type": NATURAL_PERSON,
    "name": {"first_names": "Erika", "last_name": "Muster", "gender": "w"},
    "address": {"street": "Hauptstraße", "house_number": "1", "postal_code": "12345", "city": "Musterstadt"},
    "application_date": "2026-11-02",
    "shares_subscribed": 2,
}
COOP = COOPERATIVE_ACCOUNT_NUMBER


@pytest.fixture
def setup(db) -> None:
    """Ersteinrichtung wie per CLI: Anteilspreis 50,00 € und Genossenschaftskonto."""
    change_share_price(db, 5000, actor="test")
    open_cooperative_account(db, "Musterladen eG", actor="test")


@pytest.fixture
def accounting(setup, register, login) -> None:
    """Angemeldet als Buchhaltung, die alles darf."""
    register("erika", ACCOUNTING)
    login("erika")


@pytest.fixture
def member(client, accounting) -> dict:
    """Ein Antrag über 2 Anteile, erfasst über die API; Mitglieds- und Kontonummer 1."""
    return client.post("/api/members/apply", json=APPLICATION).json()


def booking(account_number: int = 1, shares: int = 2, value_date: str = "2026-11-10", **overrides) -> dict:
    return {"account_number": account_number, "shares": shares, "value_date": value_date} | overrides


def test_subscribe(client, member):
    response = client.post("/api/accounts/subscribe", json=booking())

    assert response.status_code == 200
    body = response.json()
    assert body["warning"] is None
    account = body["account"]
    assert (account["number"], account["kind"], account["member_id"]) == (1, MEMBER_ACCOUNT, member["id"])
    assert (account["balance"], account["shares"], account["share_price"]) == (10000, 2, 5000)
    [posted] = account["bookings"]
    assert posted["kind"] == "subscription"
    assert (posted["debit"], posted["credit"], posted["amount"], posted["shares"]) == (COOP, 1, 10000, 2)
    assert (posted["text"], posted["value_date"]) == ("Eintritt", "2026-11-10")

    detail = client.get(f"/api/members/{member['id']}").json()
    assert detail["payment_date"] == "2026-11-10"
    assert detail["entry_date"] is None  # noch nicht zugelassen


def test_member_after_subscription_and_admission(client, member):
    client.post("/api/accounts/subscribe", json=booking(value_date="2026-11-10"))
    client.post("/api/members/admit", json={"member_id": member["id"], "decision_date": "2026-11-12"})

    detail = client.get(f"/api/members/{member['id']}").json()
    assert (detail["status"], detail["entry_date"]) == (MEMBER, "2026-11-12")


def test_partial_payment_warns(client, member):
    response = client.post("/api/accounts/subscribe", json=booking(shares=1))

    assert response.status_code == 200
    assert response.json()["warning"] == "1 von 2 gezeichneten Anteilen eingezahlt."


def test_amount_cannot_be_given(client, member):
    """Den Betrag berechnet immer der Service; ein mitgeschickter Betrag wird ignoriert."""
    response = client.post("/api/accounts/subscribe", json=booking(amount=1))

    assert response.json()["account"]["balance"] == 10000


def test_own_text(client, member):
    response = client.post("/api/accounts/subscribe", json=booking(text="Eintritt Barzahlung"))

    assert response.json()["account"]["bookings"][0]["text"] == "Eintritt Barzahlung"


def test_refund_after_rejection(client, member):
    client.post("/api/members/reject", json={"member_id": member["id"], "decision_date": "2026-11-05"})
    warning = client.post("/api/accounts/subscribe", json=booking()).json()["warning"]
    assert "zurückgezahlt" in warning

    response = client.post("/api/accounts/refund", json=booking(value_date="2026-11-12"))

    assert response.status_code == 200
    account = response.json()["account"]
    assert (account["balance"], account["shares"]) == (0, 0)
    assert account["bookings"][1]["text"] == "Rückzahlung"


def test_domain_error_is_400(client, member):
    client.post("/api/accounts/subscribe", json=booking())

    response = client.post("/api/accounts/refund", json=booking())

    assert response.status_code == 400
    assert "Zurückgezahlt wird nur" in response.json()["detail"]


def test_booking_on_cooperative_account_is_400(client, member):
    response = client.post("/api/accounts/subscribe", json=booking(account_number=COOP))

    assert response.status_code == 400
    assert response.json()["detail"] == f"Konto {COOP} ist kein Mitgliedskonto."


def test_unknown_account_is_404(client, member):
    assert client.get("/api/accounts/7").status_code == 404
    assert client.post("/api/accounts/subscribe", json=booking(account_number=7)).status_code == 404


def test_get_account(client, member):
    client.post("/api/accounts/subscribe", json=booking())

    account = client.get("/api/accounts/1").json()

    assert (account["balance"], account["shares"], len(account["bookings"])) == (10000, 2, 1)


def test_get_cooperative_account(client, member):
    client.post("/api/accounts/subscribe", json=booking())

    account = client.get(f"/api/accounts/{COOP}").json()

    assert (account["kind"], account["member_id"]) == (COOPERATIVE_ACCOUNT, None)
    assert (account["balance"], account["shares"]) == (-10000, -2)


def test_readonly_may_read_but_not_book(client, register, login, member):
    register("rita", ACCOUNTING_READONLY, full_name="Rita Lesend")
    login("rita")

    assert client.get("/api/accounts/1").status_code == 200
    assert client.post("/api/accounts/subscribe", json=booking()).status_code == 403
    assert client.post("/api/accounts/refund", json=booking()).status_code == 403


def test_not_logged_in(client, setup):
    assert client.get("/api/accounts/1").status_code == 401
    assert client.post("/api/accounts/subscribe", json=booking()).status_code == 401
