import re
import unicodedata
import uuid
from typing import Self

from pwdlib import PasswordHash

from ..core import DomainError
from ..eventsource import Aggregate, Event, on

ADMIN = "admin"
ACCOUNTING = "accounting"
ACCOUNTING_READONLY = "accounting_readonly"
ROLES = {ADMIN: "Admin", ACCOUNTING: "Buchhaltung", ACCOUNTING_READONLY: "Buchhaltung lesend"}

_USERNAME = re.compile(r"[\w.-]{3,50}")

# Argon2 mit den empfohlenen Einstellungen von pwdlib.
_password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Erzeugt den Hash; derselbe Text ergibt jedes Mal einen anderen Hash (zufälliges Salz)."""
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _password_hash.verify(password, password_hash)


def normalize_username(raw: str) -> str:
    """Benutzernamen ohne Leerzeichen am Rand und klein geschrieben, damit „Anna“ und „anna“ gleich sind."""
    return raw.strip().lower()


def normalize_full_name(raw: str) -> str:
    """Einheitliche Unicode-Form (NFC) und einfache Leerzeichen zwischen den Wörtern."""
    return " ".join(unicodedata.normalize("NFC", raw).split())


def validate_username(username: str) -> None:
    if not _USERNAME.fullmatch(username):
        raise DomainError(
            "Der Benutzername muss 3 bis 50 Zeichen lang sein und darf nur Buchstaben, "
            "Ziffern, Punkt, Unterstrich und Bindestrich enthalten."
        )


def validate_full_name(full_name: str) -> None:
    allowed = all(
        c.isspace() or c in ".'-" or unicodedata.category(c)[0] in "LM" or unicodedata.category(c) == "Nd"
        for c in full_name
    )
    if not (1 <= len(full_name) <= 100 and allowed and any(c.isalpha() for c in full_name)):
        raise DomainError(
            "Der Name muss 1 bis 100 Zeichen lang sein, mindestens einen Buchstaben enthalten "
            "und darf nur Buchstaben, Ziffern, Leerzeichen, Punkt, Apostroph und Bindestrich enthalten."
        )


def validate_password(password: str) -> None:
    rules = (
        len(password) >= 8,
        any(c.islower() for c in password),
        any(c.isupper() for c in password),
        any(c.isnumeric() for c in password),
        any(unicodedata.category(c)[0] in "PS" for c in password),
    )
    if not all(rules):
        raise DomainError(
            "Das Kennwort muss mindestens 8 Zeichen lang sein und Klein- und Großbuchstaben, "
            "eine Ziffer und ein Sonderzeichen enthalten."
        )


def validate_role(role: str) -> None:
    if role not in ROLES:
        raise DomainError(f"Die Rolle '{role}' ist nicht zulässig.")


class User(Aggregate):
    """Ein Benutzerkonto mit genau einer Rolle.

    Das Kennwort selbst wird nie gespeichert, nur sein Hash. Ob der Benutzername noch frei ist,
    kann das Aggregat nicht wissen; das prüft später der Service anhand der Projektion.
    """

    def __init__(self, subject: str) -> None:
        super().__init__(subject)
        self.username = ""
        self.full_name = ""
        self.password_hash = ""
        self.role = ""
        self.active = False
        self.terminated = False

    @classmethod
    def register(cls, username: str, full_name: str, password: str, role: str) -> Self:
        """Legt einen neuen, aktiven Benutzer an."""
        username = normalize_username(username)
        full_name = normalize_full_name(full_name)
        validate_username(username)
        validate_full_name(full_name)
        validate_password(password)
        validate_role(role)
        user = cls(f"user-{uuid.uuid7()}")
        user._record(
            "user.registered",
            username=username,
            full_name=full_name,
            password_hash=hash_password(password),
            role=role,
        )
        return user

    def check_password(self, password: str) -> bool:
        return verify_password(password, self.password_hash)

    def change_full_name(self, full_name: str) -> None:
        """Ist der Name gleich geblieben, entsteht kein Event."""
        self._ensure_not_terminated()
        full_name = normalize_full_name(full_name)
        validate_full_name(full_name)
        if full_name != self.full_name:
            self._record("user.name-changed", full_name=full_name)

    def change_password(self, password: str) -> None:
        self._ensure_not_terminated()
        validate_password(password)
        self._record("user.password-changed", password_hash=hash_password(password))

    def change_role(self, role: str) -> None:
        self._ensure_not_terminated()
        validate_role(role)
        if role == self.role:
            raise DomainError(f"Der Benutzer hat die Rolle '{ROLES[role]}' bereits.")
        self._record("user.role-changed", role=role)

    def deactivate(self) -> None:
        self._ensure_not_terminated()
        if not self.active:
            raise DomainError("Der Benutzer ist bereits deaktiviert.")
        self._record("user.deactivated")

    def reactivate(self) -> None:
        self._ensure_not_terminated()
        if self.active:
            raise DomainError("Der Benutzer ist bereits aktiv.")
        self._record("user.reactivated")

    def terminate(self) -> None:
        """Löscht den Benutzer endgültig. Die Events bleiben erhalten, damit `actor` nachvollziehbar bleibt."""
        self._ensure_not_terminated()
        if self.active:
            raise DomainError("Nur deaktivierte Benutzer können gelöscht werden.")
        self._record("user.terminated")

    def _ensure_not_terminated(self) -> None:
        if self.terminated:
            raise DomainError("Der Benutzer wurde gelöscht.")

    @on("user.registered")
    def _registered(self, event: Event) -> None:
        self.username = event.data["username"]
        self.full_name = event.data["full_name"]
        self.password_hash = event.data["password_hash"]
        self.role = event.data["role"]
        self.active = True

    @on("user.name-changed")
    def _name_changed(self, event: Event) -> None:
        self.full_name = event.data["full_name"]

    @on("user.password-changed")
    def _password_changed(self, event: Event) -> None:
        self.password_hash = event.data["password_hash"]

    @on("user.role-changed")
    def _role_changed(self, event: Event) -> None:
        self.role = event.data["role"]

    @on("user.deactivated", "user.reactivated")
    def _activation_changed(self, event: Event) -> None:
        self.active = event.type == "user.reactivated"

    @on("user.terminated")
    def _terminated(self, event: Event) -> None:
        self.terminated = True
        self.active = False
