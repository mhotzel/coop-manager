import json
import logging
import sys
from datetime import UTC, datetime

# `color_message` setzt uvicorn für seine farbige Textausgabe, im JSON hat es keinen Nutzen.
_STANDARD_ATTRS = set(vars(logging.makeLogRecord({}))) | {"message", "asctime", "taskName", "color_message"}


class JsonFormatter(logging.Formatter):
    """Ein JSON-Objekt pro Zeile; Werte aus `extra=` werden zu eigenen Feldern."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        entry.update({k: v for k, v in vars(record).items() if k not in _STANDARD_ATTRS})
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False, default=str)


def init_logging(level: str) -> None:
    """Logs der App und von uvicorn gehen als JSON-Zeilen nach stdout."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    for name in ("coop_manager", "uvicorn", "uvicorn.access"):
        logging.getLogger(name).handlers = [handler]
    logging.getLogger("coop_manager").setLevel(level)
