import sqlite3
from datetime import UTC, datetime, timedelta

from ..eventsource import transaction

# Liegt in projections.sqlite, wird aber nicht aus Events aufgebaut: Fehlversuche sind kein
# fachliches Ereignis, das man dauerhaft speichern müsste.
SCHEMA = """
CREATE TABLE IF NOT EXISTS login_attempts (
    username     TEXT PRIMARY KEY,
    attempts     INTEGER NOT NULL,
    last_attempt TEXT NOT NULL
);
"""


class LoginAttempts:
    """Zählt fehlgeschlagene Anmeldungen je Benutzername, auch für unbekannte Namen.

    So verrät eine Sperre nicht, welche Benutzernamen es gibt. Nach `max_attempts` Fehlversuchen
    ist der Name gesperrt, bis seit dem letzten Versuch `lockout_seconds` vergangen sind.
    """

    def __init__(self, conn: sqlite3.Connection, max_attempts: int, lockout_seconds: int) -> None:
        self.conn = conn
        self.max_attempts = max_attempts
        self.lockout = timedelta(seconds=lockout_seconds)

    def is_locked(self, username: str) -> bool:
        row = self._row(username)
        return row is not None and row[0] >= self.max_attempts and not self._expired(row[1])

    def record_failure(self, username: str) -> None:
        """Zählt einen Fehlversuch; ist die Sperrzeit abgelaufen, beginnt die Zählung neu."""
        with transaction(self.conn):
            row = self._row(username)
            attempts = 1 if row is None or self._expired(row[1]) else row[0] + 1
            self.conn.execute(
                "INSERT INTO login_attempts (username, attempts, last_attempt) VALUES (?, ?, ?)"
                " ON CONFLICT (username) DO UPDATE SET"
                " attempts = excluded.attempts, last_attempt = excluded.last_attempt",
                (username, attempts, datetime.now(UTC).isoformat()),
            )

    def reset(self, username: str) -> None:
        """Nach erfolgreicher Anmeldung zählt es wieder von vorn."""
        self.conn.execute("DELETE FROM login_attempts WHERE username = ?", (username,))

    def _row(self, username: str) -> tuple[int, datetime] | None:
        row = self.conn.execute(
            "SELECT attempts, last_attempt FROM login_attempts WHERE username = ?", (username,)
        ).fetchone()
        return (row["attempts"], datetime.fromisoformat(row["last_attempt"])) if row else None

    def _expired(self, last_attempt: datetime) -> bool:
        return datetime.now(UTC) - last_attempt >= self.lockout
