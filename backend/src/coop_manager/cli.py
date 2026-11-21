"""Befehle für die Kommandozeile, z. B. ``uv run coop-manager create-admin``."""

import argparse
import getpass
import sqlite3
import sys
from datetime import date
from pathlib import Path

from .accounts import services as accounts
from .app import PROJECTORS, SCHEMAS
from .config import load_settings
from .core import DomainError
from .core.money import format_euro, parse_euro
from .db import EVENTSTORE_DB, Database, backup_event_store, prepare
from .migration import check, run
from .migration.plan import make_plan
from .migration.source import load_decisions, load_legacy
from .system_settings import services as system_settings
from .users import services
from .users.domain import ADMIN


def create_admin(username: str, full_name: str) -> None:
    """Legt einen Benutzer mit der Rolle Admin an; das Kennwort wird verdeckt abgefragt."""
    password = getpass.getpass("Kennwort: ")
    if getpass.getpass("Kennwort wiederholen: ") != password:
        sys.exit("Die Kennwörter stimmen nicht überein.")

    db = open_db()
    try:
        user = services.register_user(db, username, full_name, password, ADMIN, actor="cli")
    except DomainError as exc:
        sys.exit(str(exc))
    finally:
        db.close()
    print(f"Admin '{user.username}' angelegt.")


def open_db() -> Database:
    """Öffnet die Datenbank im konfigurierten Datenverzeichnis (legt sie bei Bedarf an)."""
    settings = load_settings()
    prepare(settings.data_dir, PROJECTORS, SCHEMAS)
    return Database(settings.data_dir, PROJECTORS)


def set_share_price(amount: str) -> None:
    """Setzt den Anteilspreis; der Betrag kommt in Euro, z. B. „50“ oder „50,00“."""
    db = open_db()
    try:
        share_price = parse_euro(amount)
        system_settings.change_share_price(db, share_price, actor="cli")
    except DomainError as exc:
        sys.exit(str(exc))
    finally:
        db.close()
    print(f"Anteilspreis auf {format_euro(share_price)} gesetzt.")


def show_settings() -> None:
    """Zeigt die aktuellen Systemeinstellungen."""
    db = open_db()
    try:
        share_price = system_settings.get_system_settings(db).share_price
    finally:
        db.close()
    print(f"Anteilspreis: {'nicht festgelegt' if share_price is None else format_euro(share_price)}")


def create_cooperative_account() -> None:
    """Eröffnet einmalig das Konto der Genossenschaft; die Bezeichnung kommt aus der Konfiguration."""
    name = load_settings().cooperative_account_name
    db = open_db()
    try:
        account = accounts.open_cooperative_account(db, name, actor="cli")
    except DomainError as exc:
        sys.exit(str(exc))
    finally:
        db.close()
    print(f"Genossenschaftskonto {account.number} „{account.name}“ angelegt.")


def backup(target: Path | None) -> None:
    """Sichert den Event Store, ohne Ziel nach <Datenverzeichnis>/backup/eventstore.sqlite.

    Die Projektionen brauchen keine Sicherung, die App baut sie beim Start aus den Events neu auf.
    """
    data_dir = load_settings().data_dir
    target = target or data_dir / "backup" / EVENTSTORE_DB
    try:
        count = backup_event_store(data_dir, target)
    except (OSError, RuntimeError, sqlite3.Error) as exc:
        sys.exit(f"Sicherung fehlgeschlagen: {exc}")
    print(f"Event Store mit {count} Events nach {target} gesichert.")


def migrate(csv_dir: Path, decisions_path: Path, dry_run: bool) -> None:
    """Übernimmt die Altdaten (Schritt 7, siehe Plan); mit `dry_run` wird nichts geschrieben.

    Ablauf: Plan rechnen, im Speicher aufbauen, Salden abgleichen, Bericht ausgeben, speichern.
    Bei Problemen, Fehlern oder Abweichungen bricht der Befehl vor dem Speichern ab.
    """
    try:
        decisions = load_decisions(decisions_path)
        legacy = load_legacy(csv_dir, decisions.corrections)
    except (OSError, ValueError, KeyError) as exc:
        sys.exit(f"Altdaten nicht lesbar: {exc!r}")
    plan = make_plan(legacy, decisions)
    if plan.problems:
        _fail("Probleme im Migrationsplan", plan.problems)

    today = date.today()
    db = open_db()
    try:
        try:
            built = run.build(db, plan, today)
        except DomainError as exc:
            sys.exit(str(exc))
        if built.errors:
            _fail("Fehler beim Aufbau", built.errors)
        differences = check.compare(legacy, built.ledger)
        if differences:
            _fail("Abweichungen zwischen Altsystem und App", differences)
        print("\n".join(check.summary(plan, built, today)))
        if dry_run:
            print("Probelauf: nichts geschrieben.")
            return
        count = run.save(db, built)
    finally:
        db.close()
    print(f"Migration gespeichert: {count} Events.")


def _fail(title: str, items: list[str]) -> None:
    """Bricht mit einer Liste ab (Ausgabe auf stderr, Rückgabecode 1)."""
    sys.exit("\n".join([f"{title}:", *(f"  {item}" for item in items)]))


def main() -> None:
    """Einstiegspunkt für `coop-manager`: liest den Unterbefehl und führt ihn aus."""
    parser = argparse.ArgumentParser(prog="coop-manager")
    commands = parser.add_subparsers(dest="command", required=True)

    admin = commands.add_parser("create-admin", help="Benutzer mit der Rolle Admin anlegen")
    admin.add_argument("--username", default="admin")
    admin.add_argument("--full-name", default="Administrator")

    price = commands.add_parser("set-share-price", help="Anteilspreis in Euro festlegen")
    price.add_argument("amount", help="Betrag in Euro, z. B. 50 oder 50,00")

    commands.add_parser("show-settings", help="Systemeinstellungen anzeigen")

    commands.add_parser("create-cooperative-account", help="Konto der Genossenschaft anlegen (einmalig)")

    backup_parser = commands.add_parser("backup", help="Event Store sichern (stimmige Kopie, auch im Betrieb)")
    backup_parser.add_argument(
        "target", nargs="?", type=Path, help="Zieldatei, Standard: <Datenverzeichnis>/backup/eventstore.sqlite"
    )

    migrate_parser = commands.add_parser("migrate", help="Altdaten aus dem Altsystem übernehmen (einmalig)")
    migrate_parser.add_argument(
        "csv_dir", type=Path, help="Ordner mit mitglieder.csv, mitglieder_hist.csv und buchungen.csv"
    )
    migrate_parser.add_argument("decisions", type=Path, help="Einzelfälle, z. B. Altdaten/migration.toml")
    migrate_parser.add_argument("--dry-run", action="store_true", help="Probelauf: alles prüfen, nichts schreiben")

    args = parser.parse_args()
    if args.command == "create-admin":
        create_admin(args.username, args.full_name)
    elif args.command == "set-share-price":
        set_share_price(args.amount)
    elif args.command == "show-settings":
        show_settings()
    elif args.command == "create-cooperative-account":
        create_cooperative_account()
    elif args.command == "backup":
        backup(args.target)
    elif args.command == "migrate":
        migrate(args.csv_dir, args.decisions, args.dry_run)
