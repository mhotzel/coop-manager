"""Mitglieder-API: Suche und Detailansicht zum Lesen, je ein Endpunkt pro fachlichem Befehl.

Jeder Befehl antwortet mit der Detailansicht, so sieht das Frontend die Warnungen zu den
Adresszeilen direkt nach dem Speichern.
"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends

from ..db import Database, get_db
from ..users.access import require_role
from ..users.domain import ACCOUNTING, ACCOUNTING_READONLY
from ..users.projections import UserView
from . import services
from .domain import Member
from .projections import MemberRow, search_members
from .schemas import (
    ApplyForMembership,
    ChangeAddress,
    ChangeAddressLines,
    ChangeContact,
    ChangeMailPreference,
    ChangeName,
    ChangeNotes,
    ChangeSalutation,
    Decision,
    MemberDetail,
    SearchRequest,
    Withdraw,
)

router = APIRouter(prefix="/api/members")

# Kurzformen für die Parameter: Lesen dürfen beide Buchhaltungsrollen, ändern nur die Buchhaltung.
Db = Annotated[Database, Depends(get_db)]
Reader = Annotated[UserView, Depends(require_role(ACCOUNTING, ACCOUNTING_READONLY))]
Writer = Annotated[UserView, Depends(require_role(ACCOUNTING))]


# --- Abfragen ---


@router.post("/search")
def search(body: SearchRequest, db: Db, user: Reader) -> list[MemberRow]:
    """Mitglieder, auf die jedes Suchwort passt (siehe `search_members`)."""
    return search_members(db.projections.conn, body.query, date.today())


@router.get("/{member_id}")
def get_member(member_id: str, db: Db, user: Reader) -> MemberDetail:
    """Ein Mitglied mit allen Daten; 404, wenn es keines gibt."""
    return _detail(services.get_member(db, member_id))


# --- Befehle ---


@router.post("/apply")
def apply(body: ApplyForMembership, db: Db, user: Writer) -> MemberDetail:
    """Erfasst eine Beitrittserklärung mit der nächsten freien Mitgliedsnummer."""
    member = services.apply_for_membership(
        db,
        body.person_type,
        body.name,
        body.address,
        body.application_date,
        body.shares_subscribed,
        body.contact,
        actor=user.id,
    )
    return _detail(member)


@router.post("/admit")
def admit(body: Decision, db: Db, user: Writer) -> MemberDetail:
    """Zulassung durch den Vorstand."""
    return _detail(services.admit(db, body.member_id, body.decision_date, date.today(), actor=user.id))


@router.post("/reject")
def reject(body: Decision, db: Db, user: Writer) -> MemberDetail:
    """Ablehnung durch den Vorstand."""
    return _detail(services.reject(db, body.member_id, body.decision_date, date.today(), actor=user.id))


@router.post("/withdraw")
def withdraw(body: Withdraw, db: Db, user: Writer) -> MemberDetail:
    """Rücknahme des Antrags durch die Person."""
    return _detail(services.withdraw(db, body.member_id, body.withdrawal_date, date.today(), actor=user.id))


@router.post("/change-name")
def change_name(body: ChangeName, db: Db, user: Writer) -> MemberDetail:
    """Name ändern; die Adresszeilen bleiben, die Detailansicht warnt dann."""
    return _detail(services.change_name(db, body.member_id, body.name, actor=user.id))


@router.post("/change-address")
def change_address(body: ChangeAddress, db: Db, user: Writer) -> MemberDetail:
    """Anschrift ändern; die Adresszeilen bleiben, die Detailansicht warnt dann."""
    return _detail(services.change_address(db, body.member_id, body.address, actor=user.id))


@router.post("/change-contact")
def change_contact(body: ChangeContact, db: Db, user: Writer) -> MemberDetail:
    """Telefon und E-Mail ändern."""
    return _detail(services.change_contact(db, body.member_id, body.contact, actor=user.id))


@router.post("/change-address-lines")
def change_address_lines(body: ChangeAddressLines, db: Db, user: Writer) -> MemberDetail:
    """Die sechs Adresszeilen setzen, von Hand gepflegt oder aus `generated_address_lines`."""
    return _detail(services.change_address_lines(db, body.member_id, body.address_lines, actor=user.id))


@router.post("/change-salutation")
def change_salutation(body: ChangeSalutation, db: Db, user: Writer) -> MemberDetail:
    """Abweichende Briefanrede setzen; leer = wieder erzeugen."""
    return _detail(services.change_salutation(db, body.member_id, body.salutation, actor=user.id))


@router.post("/change-mail-preference")
def change_mail_preference(body: ChangeMailPreference, db: Db, user: Writer) -> MemberDetail:
    """„Keine Post“ setzen oder aufheben."""
    return _detail(services.change_mail_preference(db, body.member_id, body.no_mail, actor=user.id))


@router.post("/change-notes")
def change_notes(body: ChangeNotes, db: Db, user: Writer) -> MemberDetail:
    """Hinweise ändern."""
    return _detail(services.change_notes(db, body.member_id, body.notes, actor=user.id))


def _detail(member: Member) -> MemberDetail:
    """Die Detailansicht mit dem Status von heute."""
    return MemberDetail.from_member(member, date.today())
