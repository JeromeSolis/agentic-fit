from agentic_fit.backends import DockerBackend, LocalBackend
from agentic_fit.cli import format_category_summary, format_progress_line, select_backend
from agentic_fit.models import RunResult


def test_format_category_summary_lines():
    summary = {
        "http_client": {
            "best": ("requests", 1.0, 259.0),
            "worst": ("urllib3", 1.0, 364.0),
            "success_spread_pp": 0.0,
            "token_ratio": 1.41,
        }
    }
    lines = format_category_summary(summary)
    assert any("http_client" in line for line in lines)
    assert any("1.41" in line for line in lines)
    assert any("requests" in line for line in lines)


def test_format_progress_line_has_key_fields():
    r = RunResult("t", "jinja2", 2, "m", True, 2, 2, 3,
                  input_tokens=1000, output_tokens=240, category="templating")
    line = format_progress_line(3, 45, r, 0.18, 134)
    assert "[  3/45]" in line
    assert "templating/jinja2" in line
    assert "rep=2" in line
    assert "$0.18" in line
    assert "2m14s" in line
    assert "✓" in line and "passed" in line


def test_format_progress_line_marks_failure():
    r = RunResult("t", "urllib3", 0, "m", False, 0, 1, 3,
                  input_tokens=50, output_tokens=10, category="http_client",
                  error="tests failed")
    line = format_progress_line(7, 45, r, 1.20, 60)
    assert "✗" in line
    assert "tests failed" in line


def test_format_progress_line_failure_without_error_says_failed():
    r = RunResult("t", "urllib3", 0, "m", False, 0, 1, 3,
                  input_tokens=50, output_tokens=10, category="http_client")
    line = format_progress_line(7, 45, r, 1.20, 60)
    assert "✗" in line
    assert "failed" in line


def test_select_backend_maps_flag():
    assert isinstance(select_backend("local"), LocalBackend)
    assert isinstance(select_backend("docker"), DockerBackend)
