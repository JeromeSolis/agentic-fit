from solution import load_merged


def test_deep_merge_override_wins():
    base = "a: 1\nb:\n  x: 1\n  y: 2\n"
    override = "b:\n  y: 20\n  z: 30\nc: 3\n"
    result = load_merged(base, override)
    assert result == {"a": 1, "b": {"x": 1, "y": 20, "z": 30}, "c": 3}


def test_disjoint_keys_combine():
    result = load_merged("a: 1\n", "b: 2\n")
    assert result == {"a": 1, "b": 2}
