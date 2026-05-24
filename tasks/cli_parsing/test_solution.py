import pytest

from solution import parse


def test_parses_name_and_count():
    assert parse(["--name", "alice", "--count", "3"]) == {"name": "alice", "count": 3}


def test_count_defaults_to_one():
    assert parse(["--name", "bob"]) == {"name": "bob", "count": 1}


def test_missing_required_name_exits():
    with pytest.raises(SystemExit):
        parse(["--count", "2"])
