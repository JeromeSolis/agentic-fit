import pytest

from solution import call_with_retry


def test_returns_value_on_first_success():
    assert call_with_retry(lambda: 42) == 42


def test_retries_until_success():
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise ValueError("not yet")
        return "ok"

    assert call_with_retry(flaky) == "ok"
    assert calls["n"] == 3


def test_reraises_after_exhausting_attempts():
    def always_fail():
        raise ValueError("nope")

    with pytest.raises(ValueError):
        call_with_retry(always_fail)
