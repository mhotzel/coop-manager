import json
import logging

import pytest

from coop_manager.logs import init_logging


def output_lines(capsys) -> list[dict]:
    return [json.loads(line) for line in capsys.readouterr().out.splitlines()]


def test_writes_one_json_object_per_line(capsys):
    init_logging("INFO")

    logging.getLogger("coop_manager.test").info("hallo %s", "Welt")

    [entry] = output_lines(capsys)
    assert entry["level"] == "INFO"
    assert entry["logger"] == "coop_manager.test"
    assert entry["message"] == "hallo Welt"
    assert entry["time"].endswith("+00:00")


def test_extra_values_become_fields(capsys):
    init_logging("INFO")

    logging.getLogger("coop_manager.test").info("login", extra={"username": "erika"})

    [entry] = output_lines(capsys)
    assert entry["username"] == "erika"


def test_exception_is_logged(capsys):
    init_logging("INFO")

    try:
        raise ValueError("kaputt")
    except ValueError:
        logging.getLogger("coop_manager.test").exception("fehlgeschlagen")

    [entry] = output_lines(capsys)
    assert "ValueError: kaputt" in entry["exception"]


def test_messages_below_level_are_dropped(capsys):
    init_logging("WARNING")

    logging.getLogger("coop_manager.test").info("zu unwichtig")

    assert output_lines(capsys) == []


def test_repeated_init_does_not_duplicate_lines(capsys):
    init_logging("INFO")
    init_logging("INFO")

    logging.getLogger("coop_manager.test").info("nur einmal")

    assert len(output_lines(capsys)) == 1


def test_uvicorn_logs_are_json(capsys):
    init_logging("INFO")

    # warning, weil uvicorn sein Level INFO erst beim echten Start setzt
    logging.getLogger("uvicorn.error").warning("server läuft", extra={"color_message": "bunt"})

    [entry] = output_lines(capsys)
    assert entry["message"] == "server läuft"
    assert "color_message" not in entry


def test_unknown_level_stops_the_start():
    with pytest.raises(ValueError):
        init_logging("LAUT")
