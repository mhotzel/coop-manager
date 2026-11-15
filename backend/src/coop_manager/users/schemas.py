from pydantic import BaseModel, Field

from .projections import UserView

# Obergrenzen, damit niemand riesige Texte schickt, z. B. durch den absichtlich langsamen Hash.
# Die fachlichen Regeln (Länge, erlaubte Zeichen) prüft das Aggregat.
Username = Field(max_length=100)
FullName = Field(max_length=200)
Password = Field(max_length=200)
UserId = Field(max_length=100)


class LoginRequest(BaseModel):
    """Zugangsdaten für `POST /api/login`."""

    username: str = Username
    password: str = Password


class UserOut(BaseModel):
    """Was das Frontend über einen Benutzer erfährt; der Kennwort-Hash gehört nicht dazu."""

    id: str
    username: str
    full_name: str
    role: str
    active: bool

    @classmethod
    def from_view(cls, user: UserView) -> UserOut:
        """Übernimmt die Felder aus der Projektion, ohne den Kennwort-Hash."""
        return cls(id=user.id, username=user.username, full_name=user.full_name, role=user.role, active=user.active)


class Me(BaseModel):
    """Der angemeldete Benutzer und das CSRF-Token für schreibende Anfragen."""

    user: UserOut
    csrf_token: str


class ChangeOwnPassword(BaseModel):
    """Befehl: eigenes Kennwort ändern, mit dem bisherigen zur Bestätigung."""

    current_password: str = Password
    new_password: str = Password


class RoleOut(BaseModel):
    """Eine Rolle: Wert im Code und deutscher Name."""

    value: str
    label: str


# --- Befehle: je einer pro fachlicher Aktion, alle Daten im Body ---


class RegisterUser(BaseModel):
    """Befehl: Benutzer anlegen."""

    username: str = Username
    full_name: str = FullName
    password: str = Password
    role: str = Field(max_length=50)


class UserCommand(BaseModel):
    """Befehl, der nur den betroffenen Benutzer braucht (deactivate, reactivate, terminate)."""

    user_id: str = UserId


class ChangeFullName(UserCommand):
    """Befehl: Namen eines Benutzers ändern."""

    full_name: str = FullName


class ChangeRole(UserCommand):
    """Befehl: Rolle eines Benutzers ändern."""

    role: str = Field(max_length=50)


class ChangePassword(UserCommand):
    """Befehl: Kennwort eines Benutzers neu setzen (durch den Admin)."""

    password: str = Password
