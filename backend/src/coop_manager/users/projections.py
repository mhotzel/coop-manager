import sqlite3
from dataclasses import dataclass

from ..eventsource import Event, Projector, on


@dataclass(frozen=True, slots=True)
class UserView:
    """Ein Benutzer, wie ihn die Lesetabelle liefert."""

    id: str
    username: str
    full_name: str
    password_hash: str
    role: str
    active: bool


class UserList(Projector):
    """Alle nicht gelöschten Benutzer; Grundlage für Login und Benutzerverwaltung."""

    schema = """
    CREATE TABLE IF NOT EXISTS users (
        user_id       TEXT PRIMARY KEY,
        username      TEXT NOT NULL UNIQUE,
        full_name     TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        role          TEXT NOT NULL,
        active        INTEGER NOT NULL
    );
    """
    tables = ("users",)

    @on("user.registered")
    def _registered(self, conn: sqlite3.Connection, event: Event) -> None:
        conn.execute(
            "INSERT INTO users (user_id, username, full_name, password_hash, role, active) VALUES (?, ?, ?, ?, ?, 1)",
            (
                event.subject,
                event.data["username"],
                event.data["full_name"],
                event.data["password_hash"],
                event.data["role"],
            ),
        )

    @on("user.name-changed")
    def _name_changed(self, conn: sqlite3.Connection, event: Event) -> None:
        conn.execute("UPDATE users SET full_name = ? WHERE user_id = ?", (event.data["full_name"], event.subject))

    @on("user.password-changed")
    def _password_changed(self, conn: sqlite3.Connection, event: Event) -> None:
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE user_id = ?", (event.data["password_hash"], event.subject)
        )

    @on("user.role-changed")
    def _role_changed(self, conn: sqlite3.Connection, event: Event) -> None:
        conn.execute("UPDATE users SET role = ? WHERE user_id = ?", (event.data["role"], event.subject))

    @on("user.deactivated", "user.reactivated")
    def _activation_changed(self, conn: sqlite3.Connection, event: Event) -> None:
        active = event.type == "user.reactivated"
        conn.execute("UPDATE users SET active = ? WHERE user_id = ?", (active, event.subject))

    @on("user.terminated")
    def _terminated(self, conn: sqlite3.Connection, event: Event) -> None:
        conn.execute("DELETE FROM users WHERE user_id = ?", (event.subject,))


def get_user(conn: sqlite3.Connection, user_id: str) -> UserView | None:
    """Ein Benutzer nach ID; None, wenn es ihn nicht (mehr) gibt."""
    users = _query(conn, "WHERE user_id = ?", (user_id,))
    return users[0] if users else None


def find_by_username(conn: sqlite3.Connection, username: str) -> UserView | None:
    """Ein Benutzer nach (normalisiertem) Benutzernamen; None, wenn es ihn nicht gibt."""
    users = _query(conn, "WHERE username = ?", (username,))
    return users[0] if users else None


def list_users(conn: sqlite3.Connection) -> list[UserView]:
    """Alle nicht gelöschten Benutzer, nach Benutzername sortiert."""
    return _query(conn, "", ())


def _query(conn: sqlite3.Connection, where: str, params: tuple) -> list[UserView]:
    rows = conn.execute(f"SELECT * FROM users {where} ORDER BY username", params)
    return [
        UserView(
            id=row["user_id"],
            username=row["username"],
            full_name=row["full_name"],
            password_hash=row["password_hash"],
            role=row["role"],
            active=bool(row["active"]),
        )
        for row in rows
    ]
