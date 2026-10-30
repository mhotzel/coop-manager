from pathlib import Path

from coop_manager.config import load_settings


def test_data_dir_has_default(monkeypatch):
    monkeypatch.delenv("CM_DATA_DIR", raising=False)

    assert load_settings().data_dir == Path("data")


def test_data_dir_comes_from_environment(monkeypatch):
    monkeypatch.setenv("CM_DATA_DIR", "/srv/coop")

    assert load_settings().data_dir == Path("/srv/coop")
