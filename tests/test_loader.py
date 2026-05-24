from pathlib import Path

from agentic_fit.loader import load_tasks

FIXTURES = Path(__file__).parent / "fixtures"


def test_load_tasks_reads_yaml_and_resolves_test_path():
    tasks = load_tasks(FIXTURES)
    assert len(tasks) == 1
    t = tasks[0]
    assert t.id == "sample__add"
    assert t.category == "sample"
    assert t.candidate_libraries == ("math",)
    assert Path(t.test_path).name == "test_solution.py"
    assert Path(t.test_path).exists()
    assert Path(t.test_path).is_absolute()


def test_load_tasks_reads_difficulty():
    tasks = load_tasks(FIXTURES)
    assert tasks[0].difficulty == "medium"
