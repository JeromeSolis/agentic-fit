import pytest

from solution import to_iso_utc


def test_parses_iso_like():
    assert to_iso_utc("2026-03-05 14:30") == "2026-03-05T14:30:00"


def test_parses_human():
    assert to_iso_utc("March 5, 2026 2:30 PM") == "2026-03-05T14:30:00"


def test_raises_on_garbage():
    with pytest.raises(ValueError):
        to_iso_utc("not a date")
