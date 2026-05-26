from agentic_fit.models import RunResult


def test_runresult_total_tokens():
    r = RunResult(
        task_id="t", library="httpx", rep=0, model="m", success=True,
        tests_passed=3, tests_total=3, iterations=1,
        input_tokens=100, output_tokens=50,
    )
    assert r.total_tokens == 150


def test_runresult_json_round_trip():
    r = RunResult(
        task_id="t", library="httpx", rep=0, model="m", success=False,
        tests_passed=1, tests_total=3, iterations=3,
        input_tokens=10, output_tokens=20, error="boom",
    )
    assert RunResult.from_json(r.to_json()) == r


def test_runresult_carries_category_version_chosen():
    r = RunResult(
        task_id="t", library="httpx", rep=0, model="m", success=True,
        tests_passed=3, tests_total=3, iterations=1,
        input_tokens=10, output_tokens=20,
        category="http_client", version="0.27.0", status="passed",
    )
    assert r.category == "http_client"
    assert r.version == "0.27.0"
    assert r.chosen_library is None
    assert r.status == "passed"
    assert RunResult.from_json(r.to_json()) == r


def test_runresult_from_json_tolerates_legacy_line():
    legacy = (
        '{"task_id":"t","library":"requests","rep":0,"model":"m","success":true,'
        '"tests_passed":1,"tests_total":1,"iterations":1,'
        '"input_tokens":5,"output_tokens":5,"error":null}'
    )
    r = RunResult.from_json(legacy)
    assert r.category == ""
    assert r.version is None
    assert r.chosen_library is None
    assert r.status == ""


def test_runresult_roundtrips_cost_and_provider():
    from agentic_fit.models import RunResult
    r = RunResult(
        task_id="t", library="l", rep=0, model="m", success=True,
        tests_passed=1, tests_total=1, iterations=1, input_tokens=10, output_tokens=5,
        category="c", version="v", status="passed", cost_usd=0.0012, provider="openrouter",
    )
    back = RunResult.from_json(r.to_json())
    assert back == r
    assert back.cost_usd == 0.0012
    assert back.provider == "openrouter"


def test_runresult_defaults_cost_and_provider():
    from agentic_fit.models import RunResult
    r = RunResult("t", "l", 0, "m", True, 1, 1, 1, 10, 5)
    assert r.cost_usd is None
    assert r.provider == ""
