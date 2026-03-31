"""Task loader utilities."""

from pathlib import Path
import json

TASKS_DIR = Path(__file__).parent


def list_tasks() -> list[str]:
    """Return sorted list of task IDs."""
    return sorted(p.stem for p in TASKS_DIR.glob("*.json"))


def load_task(task_id: str) -> dict:
    """Load a task by ID."""
    path = TASKS_DIR / f"{task_id}.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
