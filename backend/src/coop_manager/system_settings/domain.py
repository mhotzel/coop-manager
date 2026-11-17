from ..core import DomainError
from ..eventsource import Aggregate, Event, on

SUBJECT = "system-settings"


class SystemSettings(Aggregate):
    """Die Systemeinstellungen, als ein einziger Stream.

    Jede Änderung ist ein Event; so ist nachvollziehbar, wer wann welchen Wert gesetzt hat. Nicht
    zu verwechseln mit `config.Settings`, der technischen Konfiguration aus der `.env`.
    """

    def __init__(self, subject: str = SUBJECT) -> None:
        """Ohne Events ist noch nichts festgelegt."""
        super().__init__(subject)
        self.share_price: int | None = None  # Anteilspreis in Cent

    def change_share_price(self, share_price: int) -> None:
        """Setzt den Anteilspreis (in Cent). Er gilt nur für neue Buchungen (siehe Plan)."""
        if share_price <= 0:
            raise DomainError("Der Anteilspreis muss größer als 0 sein.")
        if share_price == self.share_price:
            return  # nichts geändert, also kein Event
        self._record("settings.share-price-changed", share_price=share_price)

    @on("settings.share-price-changed")
    def _share_price_changed(self, event: Event) -> None:
        self.share_price = event.data["share_price"]
