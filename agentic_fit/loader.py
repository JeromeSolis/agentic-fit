from __future__ import annotations

from pathlib import Path

import yaml

from .models import Task


def load_tasks(tasks_dir: Path) -> list[Task]:
    tasks: list[Task] = []
    for task_file in sorted(Path(tasks_dir).glob("*/task.yaml")):
        data = yaml.safe_load(task_file.read_text())
        test_path = (task_file.parent / data["test_file"]).resolve()
        tasks.append(
            Task(
                id=data["id"],
                category=data["category"],
                prompt=data["prompt"],
                candidate_libraries=tuple(data["candidate_libraries"]),
                solution_filename=data.get("solution_filename", "solution.py"),
                test_path=str(test_path),
                difficulty=data.get("difficulty", "easy"),
            )
        )
    return tasks
