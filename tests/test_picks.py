from agentic_fit.picks import effective_pick, kind

STDLIB = {"os", "sys", "dataclasses", "argparse", "datetime", "re", "json", "typing"}
CANDS = {"pydantic", "marshmallow", "dataclasses"}


def test_effective_pick_third_party():
    assert effective_pick(["pydantic", "os"], CANDS, STDLIB) == "pydantic"


def test_effective_pick_names_stdlib_candidate():
    assert effective_pick(["dataclasses", "typing"], CANDS, STDLIB) == "dataclasses"


def test_effective_pick_pure_stdlib_is_none():
    assert effective_pick(["os", "re"], CANDS, STDLIB) is None


def test_effective_pick_compound_sorted():
    assert effective_pick(["yaml", "deepmerge"], set(), STDLIB) == "deepmerge+yaml"


def test_effective_pick_fallback_when_imports_none():
    assert effective_pick(None, CANDS, STDLIB, fallback="pydantic") == "pydantic"
    assert effective_pick(None, CANDS, STDLIB) is None


def test_kind_classifies_builtin_vs_community():
    assert kind(None, STDLIB) == "builtin"
    assert kind("dataclasses", STDLIB) == "builtin"
    assert kind("pydantic", STDLIB) == "community"
    assert kind("deepmerge+yaml", STDLIB) == "community"
