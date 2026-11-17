import pytest

from coop_manager.core import DomainError
from coop_manager.system_settings import services
from coop_manager.system_settings.domain import SUBJECT, SystemSettings


def test_share_price_is_not_set_at_first():
    assert SystemSettings().share_price is None


def test_change_share_price():
    settings = SystemSettings()
    settings.change_share_price(5000)
    settings.change_share_price(6000)

    reloaded = SystemSettings.from_events(SUBJECT, settings.uncommitted_events)
    assert reloaded.share_price == 6000
    assert [e.data["share_price"] for e in settings.uncommitted_events] == [5000, 6000]


def test_same_share_price_records_no_event():
    settings = SystemSettings()
    settings.change_share_price(5000)
    settings.change_share_price(5000)

    assert len(settings.uncommitted_events) == 1


@pytest.mark.parametrize("share_price", [0, -100])
def test_share_price_must_be_positive(share_price):
    with pytest.raises(DomainError, match="größer als 0"):
        SystemSettings().change_share_price(share_price)


def test_service_saves_and_loads(db):
    services.change_share_price(db, 5000, actor="admin")

    assert services.get_system_settings(db).share_price == 5000
    assert db.store.read_stream(SUBJECT)[0].actor == "admin"
