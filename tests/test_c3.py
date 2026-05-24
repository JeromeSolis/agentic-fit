from agentic_fit.c3 import arm_mode_and_out


def test_arm_mode_and_out_maps_arm():
    mode, out = arm_mode_and_out("unconstrained", "claude-haiku-4-5")
    assert mode == "free_unconstrained"
    assert "unconstrained" in out and "haiku" in out
    mode2, out2 = arm_mode_and_out("constrained", "claude-sonnet-4-6")
    assert mode2 == "free_constrained"
    assert "constrained" in out2 and "sonnet" in out2
