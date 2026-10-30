from collections.abc import Callable, Iterable
from typing import Any, ClassVar, Self

from .events import Event, collect_handlers


class UnknownEventError(Exception):
    pass


class Aggregate:
    """Basisklasse für Fachobjekte, deren Zustand aus Events entsteht.

    Der Zustand ändert sich nur, indem ein Event aufgezeichnet wird. Zu jedem Eventtyp gehört ein
    mit ``@on("<typ>")`` markierter Handler, der das Event auf den Zustand anwendet.
    """

    _handlers: ClassVar[dict[str, Callable]] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        cls._handlers = collect_handlers(cls)

    def __init__(self, subject: str) -> None:
        self.subject = subject
        self.version = 0
        self._uncommitted: list[Event] = []

    @classmethod
    def from_events(cls, subject: str, events: Iterable[Event]) -> Self:
        aggregate = cls(subject)
        for event in events:
            aggregate._apply(event)
        return aggregate

    def _record(self, event_type: str, **data: Any) -> None:
        event = Event(type=event_type, subject=self.subject, data=data, version=self.version + 1)
        self._apply(event)
        self._uncommitted.append(event)

    def _apply(self, event: Event) -> None:
        handler = self._handlers.get(event.type)
        if handler is None:
            raise UnknownEventError(f"{type(self).__name__} hat keinen Handler für '{event.type}'")
        handler(self, event)
        self.version = event.version

    @property
    def uncommitted_events(self) -> list[Event]:
        return list(self._uncommitted)

    def mark_committed(self) -> None:
        self._uncommitted.clear()
