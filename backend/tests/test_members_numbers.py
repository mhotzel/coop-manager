import pytest

from coop_manager.core import DomainError
from coop_manager.members.numbers import MemberNumbers


def numbers_with(*assigned: int) -> MemberNumbers:
    numbers = MemberNumbers()
    for number in assigned:
        numbers.assign(number, f"member-{number}")
    return numbers


def test_first_number_is_one():
    assert MemberNumbers().next_number() == 1


def test_next_number_is_highest_plus_one():
    assert numbers_with(1, 2, 7).next_number() == 8  # Lücken bleiben frei


def test_9999_is_skipped():
    assert numbers_with(9998).next_number() == 10000


@pytest.mark.parametrize("number, message", [(7, "bereits vergeben"), (9999, "reserviert"), (0, "positiv")])
def test_assign_checks_number(number, message):
    with pytest.raises(DomainError, match=message):
        numbers_with(7).assign(number, "member-x")


def test_numbers_are_restored_from_events():
    numbers = numbers_with(3, 5)

    restored = MemberNumbers.from_events(numbers.subject, numbers.uncommitted_events)

    assert restored.assigned == {3: "member-3", 5: "member-5"}
