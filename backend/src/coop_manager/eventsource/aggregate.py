from collections.abc import Callable, Iterable
from typing import Any, ClassVar, Self

from .events import Event, collect_handlers


class UnknownEventError(Exception):
    """Das Aggregate hat keine Methode, die diesen Eventtyp anwendet."""


class Aggregate:
    """Basisklasse für Fachobjekte, deren Zustand aus Events entsteht.

    Der Zustand ändert sich nur, indem ein Event aufgezeichnet wird. Zu jedem Eventtyp gehört ein
    mit ``@on("<typ>")`` markierter Handler, der das Event auf den Zustand anwendet.
    """

    _handlers: ClassVar[dict[str, Callable]] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Sammelt beim Definieren einer Unterklasse deren ``@on``-Handler ein, einmal pro Klasse statt bei jedem Objekt."""
        super().__init_subclass__(**kwargs)
        cls._handlers = collect_handlers(cls)

    def __init__(self, subject: str) -> None:
        """Leeres Aggregat ohne Events, Version 0."""
        self.subject = subject
        self.version = 0
        self._uncommitted: list[Event] = []

    @classmethod
    def from_events(cls, subject: str, events: Iterable[Event]) -> Self:
        """Stellt den Zustand wieder her, indem die gespeicherten Events der Reihe nach angewendet werden."""
        aggregate = cls(subject)
        for event in events:
            aggregate._apply(event)
        return aggregate

    def _record(self, event_type: str, **data: Any) -> None:
        """Erzeugt ein neues Event mit der nächsten Version, wendet es an und merkt es zum Speichern vor."""
        event = Event(type=event_type, subject=self.subject, data=data, version=self.version + 1)
        self._apply(event)
        self._uncommitted.append(event)

    def _apply(self, event: Event) -> None:
        """Ruft den Handler für den Eventtyp auf und übernimmt die Version des Events.

        Gibt es keinen Handler, kommt ein ``UnknownEventError``.
        """
        handler = self._handlers.get(event.type)
        if handler is None:
            raise UnknownEventError(f"{type(self).__name__} hat keinen Handler für '{event.type}'")
        handler(self, event)
        self.version = event.version

    @property
    def uncommitted_events(self) -> list[Event]:
        """Die aufgezeichneten, noch nicht gespeicherten Events (als Kopie der Liste)."""
        return list(self._uncommitted)

    def mark_committed(self) -> None:
        """Vergisst die vorgemerkten Events, nachdem der Event Store sie gespeichert hat."""
        self._uncommitted.clear()
