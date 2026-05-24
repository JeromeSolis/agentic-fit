import pytest

from solution import parse_order

VALID = {
    "customer": {"name": "Al", "email": "al@example.com"},
    "items": [{"sku": "A", "qty": "2"}, {"sku": "B", "qty": 3}],
}


def test_valid_order_coerces_qty_to_int():
    order = parse_order(VALID)
    assert order["items"][0]["qty"] == 2
    assert isinstance(order["items"][0]["qty"], int)
    assert order["items"][1]["qty"] == 3
    assert order["customer"]["email"] == "al@example.com"


def test_bad_email_raises_valueerror():
    bad = {"customer": {"name": "Al", "email": "nope"},
           "items": [{"sku": "A", "qty": 1}]}
    with pytest.raises(ValueError):
        parse_order(bad)


def test_nonpositive_qty_raises_valueerror():
    bad = {"customer": {"name": "Al", "email": "al@example.com"},
           "items": [{"sku": "A", "qty": 0}]}
    with pytest.raises(ValueError):
        parse_order(bad)
