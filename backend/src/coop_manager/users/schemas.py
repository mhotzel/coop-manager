from pydantic import BaseModel, Field

from .projections import UserView


class LoginRequest(BaseModel):
    # Obergrenzen, damit niemand riesige Texte durch den (absichtlich langsamen) Hash schickt.
    username: str = Field(max_length=100)
    password: str = Field(max_length=200)


class UserOut(BaseModel):
    """Was das Frontend über einen Benutzer erfährt; der Kennwort-Hash gehört nicht dazu."""

    id: str
    username: str
    full_name: str
    role: str

    @classmethod
    def from_view(cls, user: UserView) -> UserOut:
        return cls(id=user.id, username=user.username, full_name=user.full_name, role=user.role)


class Me(BaseModel):
    """Der angemeldete Benutzer und das CSRF-Token für schreibende Anfragen."""

    user: UserOut
    csrf_token: str
