class DomainError(Exception):
    """Eine fachliche Regel ist verletzt; die Meldung ist für den Benutzer bestimmt (deutsch)."""


class NotFoundError(DomainError):
    """Das gesuchte Objekt gibt es nicht (mehr)."""
