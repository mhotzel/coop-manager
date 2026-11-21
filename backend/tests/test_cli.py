import sqlite3
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


def test_create_cooperative_account(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("CM_COOPERATIVE_ACCOUNT_NAME", "Musterladen eG")

    run_cli(monkeypatch, tmp_path, ["create-cooperative-account"], [])
    assert "Genossenschaftskonto 9999 „Musterladen eG“ angelegt." in capsys.readouterr().out

    with pytest.raises(SystemExit, match="gibt es bereits"):
        run_cli(monkeypatch, tmp_path, ["create-cooperative-account"], [])


def test_backup_writes_a_consistent_single_file(monkeypatch, tmp_path, capsys):
    run_cli(monkeypatch, tmp_path, ["set-share-price", "50"], [])

    run_cli(monkeypatch, tmp_path, ["backup"], [])

    target = tmp_path / "backup" / "eventstore.sqlite"
    assert f"nach {target} gesichert" in capsys.readouterr().out
    assert [p.name for p in target.parent.iterdir()] == ["eventstore.sqlite"]  # kein .partial, kein -wal
    copy = sqlite3.connect(target)
    assert copy.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
    assert copy.execute("SELECT count(*) FROM events").fetchone()[0] == 1
    copy.close()


def test_backup_replaces_an_older_copy_at_given_target(monkeypatch, tmp_path, capsys):
    target = tmp_path / "copy.sqlite"
    run_cli(monkeypatch, tmp_path, ["set-share-price", "50"], [])
    run_cli(monkeypatch, tmp_path, ["backup", str(target)], [])
    run_cli(monkeypatch, tmp_path, ["set-share-price", "60"], [])

    run_cli(monkeypatch, tmp_path, ["backup", str(target)], [])

    assert "Event Store mit 2 Events" in capsys.readouterr().out
    copy = sqlite3.connect(target)
    assert copy.execute("SELECT count(*) FROM events").fetchone()[0] == 2
    copy.close()


def test_backup_without_event_store_fails_and_writes_nothing(monkeypatch, tmp_path):
    with pytest.raises(SystemExit, match="Kein Event Store"):
        run_cli(monkeypatch, tmp_path, ["backup"], [])

    assert not (tmp_path / "eventstore.sqlite").exists()
    assert not (tmp_path / "backup").exists()
