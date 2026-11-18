from datetime import date, timedelta

import pytest

from coop_manager.members.status import APPLICANT, REJECTED
from coop_manager.members.values import NATURAL_PERSON
from coop_manager.users.domain import ACCOUNTING, ACCOUNTING_READONLY, ADMIN

# Erfundene Testdaten.
APPLICATION = {
    "person_type": NATURAL_PERSON,
    "name": {"first_names": "Erika", "last_name": "Muster", "gender": "w"},
    "address": {"street": "Hauptstraße", "house_number": "1", "postal_code": "12345", "city": "Musterstadt"},
    "application_date": "2026-11-02",
    "shares_subscribed": 2,
}
ERIKAS_LINES = ["Frau", "Erika Muster", "Hauptstraße 1", "12345 Musterstadt", "", ""]


@pytest.fixture
def accounting(register, login) -> None:
    """Angemeldet als Buchhaltung, die alles darf."""
    register("erika", ACCOUNTING)
    login("erika")


@pytest.fixture
def member_id(client, accounting) -> str:
    """Ein Antrag, erfasst über die API."""
    return client.post("/api/members/apply", json=APPLICATION).json()["id"]


def test_apply_returns_detail(client, accounting):
    response = client.post("/api/members/apply", json=APPLICATION)

    assert response.status_code == 200
    body = response.json()
    assert body["member_number"] == 1
    assert body["name"] == {
        "company_name": "",
        "title": "",
        "first_names": "Erika",
        "last_name": "Muster",
        "gender": "w",
    }
    assert body["contact"] == {"phone": "", "email": ""}
    assert body["shares_subscribed"] == 2
    assert body["status"] == APPLICANT
    assert body["salutation"] == "Sehr geehrte Frau Muster"
    assert body["address_lines"] == ERIKAS_LINES
    assert body["generated_address_lines"] == ERIKAS_LINES
    assert body["warnings"] == []


def test_apply_reports_domain_error(client, accounting):
    response = client.post("/api/members/apply", json=APPLICATION | {"shares_subscribed": 0})

    assert response.status_code == 400
    assert response.json() == {"detail": "Es muss mindestens ein Anteil gezeichnet werden."}


def test_apply_rejects_missing_fields(client, accounting):
    response = client.post("/api/members/apply", json=APPLICATION | {"address": {"street": "Hauptstraße"}})

    assert response.status_code == 422


def test_get_member(client, member_id):
    response = client.get(f"/api/members/{member_id}")

    assert response.status_code == 200
    assert response.json()["id"] == member_id


def test_get_unknown_member(client, accounting):
    response = client.get("/api/members/member-gibt-es-nicht")

    assert response.status_code == 404
    assert response.json() == {"detail": "Das Mitglied wurde nicht gefunden."}


def test_search(client, member_id):
    response = client.post("/api/members/search", json={"query": "muster haupt"})

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": member_id,
            "member_number": 1,
            "person_type": NATURAL_PERSON,
            "list_name": "Muster, Erika",
            "street": "Hauptstraße 1",
            "postal_code": "12345",
            "city": "Musterstadt",
            "status": APPLICANT,
            "partial_notice": False,
        }
    ]


def test_change_name_warns_about_address_lines(client, member_id):
    name = {"first_names": "Erika", "last_name": "Beispiel", "gender": "w"}

    body = client.post("/api/members/change-name", json={"member_id": member_id, "name": name}).json()

    assert body["address_lines"] == ERIKAS_LINES  # bleiben, wie sie sind
    assert body["generated_address_lines"][1] == "Erika Beispiel"
    assert body["warnings"] == ["Die Adresszeilen passen nicht zu Name und Anschrift."]


def test_saving_generated_lines_removes_warning(client, member_id):
    name = {"first_names": "Erika", "last_name": "Beispiel", "gender": "w"}
    generated = client.post("/api/members/change-name", json={"member_id": member_id, "name": name}).json()[
        "generated_address_lines"
    ]

    body = client.post(
        "/api/members/change-address-lines", json={"member_id": member_id, "address_lines": generated}
    ).json()

    assert body["address_lines"] == generated
    assert body["warnings"] == []


def test_long_address_line_is_saved_with_warning(client, member_id):
    lines = ["Frau", "Erika Maria Musterfrau-Beispielhausen", "Hauptstraße 1", "12345 Musterstadt", "", ""]

    response = client.post("/api/members/change-address-lines", json={"member_id": member_id, "address_lines": lines})

    assert response.status_code == 200
    assert "Adresszeile 2 ist länger als 35 Zeichen." in response.json()["warnings"]


def test_withdraw(client, member_id):
    body = client.post("/api/members/withdraw", json={"member_id": member_id, "withdrawal_date": "2026-11-10"}).json()

    assert body["rejection_date"] == "2026-11-10"
    assert body["withdrawn"] is True
    assert body["status"] == REJECTED


def test_decision_in_the_future_fails(client, member_id):
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    response = client.post("/api/members/reject", json={"member_id": member_id, "decision_date": tomorrow})

    assert response.status_code == 400
    assert response.json() == {"detail": "Das Datum darf nicht in der Zukunft liegen."}


def test_reject_after_admission_fails(client, member_id):
    client.post("/api/members/admit", json={"member_id": member_id, "decision_date": "2026-11-05"})

    response = client.post("/api/members/reject", json={"member_id": member_id, "decision_date": "2026-11-06"})

    assert response.status_code == 400
    assert response.json() == {"detail": "Ein zugelassener Antrag kann nicht mehr abgelehnt werden."}


def test_other_changes(client, member_id):
    client.post("/api/members/change-contact", json={"member_id": member_id, "contact": {"email": "Erika@Example.org"}})
    client.post("/api/members/change-salutation", json={"member_id": member_id, "salutation": "Liebe Erika"})
    client.post("/api/members/change-mail-preference", json={"member_id": member_id, "no_mail": True})
    client.post("/api/members/change-notes", json={"member_id": member_id, "notes": "Ruft lieber an."})
    moved = APPLICATION["address"] | {"street": "Dorfweg"}
    body = client.post("/api/members/change-address", json={"member_id": member_id, "address": moved}).json()

    assert body["contact"] == {"phone": "", "email": "erika@example.org"}
    assert body["salutation_override"] == "Liebe Erika"
    assert body["salutation"] == "Liebe Erika"
    assert body["no_mail"] is True
    assert body["notes"] == "Ruft lieber an."
    assert body["address"]["street"] == "Dorfweg"


# --- Rechte ---


def test_readonly_may_read_but_not_change(client, register, login, member_id):
    register("rita", ACCOUNTING_READONLY, full_name="Rita Lesend")
    login("rita")

    assert client.get(f"/api/members/{member_id}").status_code == 200
    assert client.post("/api/members/search", json={"query": ""}).status_code == 200
    response = client.post("/api/members/change-notes", json={"member_id": member_id, "notes": "x"})
    assert response.status_code == 403


def test_admin_has_no_access(client, register, login, member_id):
    register("chefin", ADMIN, full_name="Clara Chefin")
    login("chefin")

    assert client.get(f"/api/members/{member_id}").status_code == 403
    assert client.post("/api/members/search", json={"query": ""}).status_code == 403
    assert client.post("/api/members/apply", json=APPLICATION).status_code == 403
