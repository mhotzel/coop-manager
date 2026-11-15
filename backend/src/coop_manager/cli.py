"""Befehle für die Kommandozeile, z. B. ``uv run coop-manager create-admin``."""

import argparse
import getpass
import sys

from .app import PROJECTORS, SCHEMAS
from .config import load_settings
from .core import DomainError
from .db import Database, prepare
from .users import services
from .users.domain import ADMIN


def create_admin(username: str, full_name: str) -> None:
    """Legt einen Benutzer mit der Rolle Admin an; das Kennwort wird verdeckt abgefragt."""
    password = getpass.getpass("Kennwort: ")
    if getpass.getpass("Kennwort wiederholen: ") != password:
        sys.exit("Die Kennwörter stimmen nicht überein.")

    settings = load_settings()
    prepare(settings.data_dir, PROJECTORS, SCHEMAS)
    db = Database(settings.data_dir, PROJECTORS)
    try:
        user = services.register_user(db, username, full_name, password, ADMIN, actor="cli")
    except DomainError as exc:
        sys.exit(str(exc))
    finally:
        db.close()
    print(f"Admin '{user.username}' angelegt.")


def main() -> None:
    """Einstiegspunkt für `coop-manager`: liest den Unterbefehl und führt ihn aus."""
    parser = argparse.ArgumentParser(prog="coop-manager")
    commands = parser.add_subparsers(dest="command", required=True)

    admin = commands.add_parser("create-admin", help="Benutzer mit der Rolle Admin anlegen")
    admin.add_argument("--username", default="admin")
    admin.add_argument("--full-name", default="Administrator")

    args = parser.parse_args()
    if args.command == "create-admin":
        create_admin(args.username, args.full_name)
