import pytest

from solution import parse_user


def _get(obj, attr):
    return obj[attr] if isinstance(obj, dict) else getattr(obj, attr)


def test_valid_record_coerces_age():
    u = parse_user({"name": "Ada", "age": "42", "email": "a@b.com"})
    assert _get(u, "name") == "Ada"
    assert _get(u, "age") == 42
    assert _get(u, "email") == "a@b.com"


def test_missing_email_raises():
    with pytest.raises(ValueError):
        parse_user({"name": "Ada", "age": "42"})


def test_negative_age_raises():
    with pytest.raises(ValueError):
        parse_user({"name": "Ada", "age": "-1", "email": "a@b.com"})
