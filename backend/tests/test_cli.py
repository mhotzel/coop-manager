import sys

import pytest

from coop_manager import cli
from coop_manager.app import PROJECTORS
from coop_manager.db import Database
from coop_manager.users import projections
from coop_manager.users.domain import ADMIN


def run_cli(monkeypatch, tmp_path, args: list[str], passwords: list[str]) -> None:
    """Startet die CLI mit Argumenten; die verdeckten Kennwort-Eingaben kommen aus `passwords`."""
    monkeypatch.setenv("CM_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(sys, "argv", ["coop-manager", *args])
    answers = iter(passwords)
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt: next(answers))
    cli.main()


def test_create_admin(monkeypatch, tmp_path, capsys):
    run_cli(monkeypatch, tmp_path, ["create-admin", "--username", "chefin"], ["Geheim-123", "Geheim-123"])

    db = Database(tmp_path, PROJECTORS)
    user = projections.find_by_username(db.projections.conn, "chefin")
    db.close()
    assert user is not None and user.role == ADMIN
    assert "Admin 'chefin' angelegt." in capsys.readouterr().out


def test_create_admin_rejects_different_passwords(monkeypatch, tmp_path):
    with pytest.raises(SystemExit, match="stimmen nicht überein"):
        run_cli(monkeypatch, tmp_path, ["create-admin"], ["Geheim-123", "Geheim-124"])


def test_create_admin_reports_weak_password(monkeypatch, tmp_path):
    with pytest.raises(SystemExit, match="Kennwort muss"):
        run_cli(monkeypatch, tmp_path, ["create-admin"], ["kurz", "kurz"])


def test_set_and_show_share_price(monkeypatch, tmp_path, capsys):
    run_cli(monkeypatch, tmp_path, ["show-settings"], [])
    assert "Anteilspreis: nicht festgelegt" in capsys.readouterr().out

    run_cli(monkeypatch, tmp_path, ["set-share-price", "50,00"], [])
    assert "Anteilspreis auf 50,00 € gesetzt." in capsys.readouterr().out

    run_cli(monkeypatch, tmp_path, ["show-settings"], [])
    assert "Anteilspreis: 50,00 €" in capsys.readouterr().out


def test_set_share_price_rejects_invalid_amount(monkeypatch, tmp_path):
    with pytest.raises(SystemExit, match="kein gültiger Euro-Betrag"):
        run_cli(monkeypatch, tmp_path, ["set-share-price", "50,005"], [])


def test_set_share_price_rejects_zero(monkeypatch, tmp_path):
    with pytest.raises(SystemExit, match="größer als 0"):
        run_cli(monkeypatch, tmp_path, ["set-share-price", "0"], [])
