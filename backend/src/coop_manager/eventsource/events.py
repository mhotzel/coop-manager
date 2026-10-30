import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class Event:
    """Ein fachliches Ereignis. `subject` benennt den Stream des Aggregats, `version` die Position darin."""

    type: str
    subject: str
    data: dict[str, Any] = field(default_factory=dict)
    version: int = 0
    id: uuid.UUID = field(default_factory=uuid.uuid7)
    time: datetime = field(default_factory=lambda: datetime.now(UTC))
    actor: str | None = None


def on(*event_types: str) -> Callable:
    """Markiert eine Methode eines Aggregats oder Projektors als Handler für die genannten Eventtypen."""

    def decorator(func: Callable) -> Callable:
        func._handles_events = event_types
        return func

    return decorator


def collect_handlers(cls: type) -> dict[str, Callable]:
    """Sammelt die mit `@on` markierten Methoden einer Klasse und ihrer Basisklassen ein."""
    handlers: dict[str, Callable] = {}
    for klass in reversed(cls.__mro__):
        for attr in vars(klass).values():
            for event_type in getattr(attr, "_handles_events", ()):
                handlers[event_type] = attr
    return handlers
