from solution import render


def test_renders_title_and_items():
    out = render("Shopping", ["milk", "eggs"])
    lines = [ln for ln in out.splitlines() if ln.strip()]
    assert lines[0].strip() == "Shopping"
    assert "- milk" in out
    assert "- eggs" in out


def test_empty_items_is_just_title():
    out = render("Empty", [])
    nonblank = [ln for ln in out.splitlines() if ln.strip()]
    assert nonblank == ["Empty"]
