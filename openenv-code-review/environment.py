"""
OpenEnv-compliant Code Review Environment.

Implements the Gymnasium-style API:
  - reset(task_id=None)  → ReviewObservation
  - step(action)         → (ReviewObservation | None, reward, done, info)
  - state()              → EnvironmentState
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any, Optional

from schemas import (
    EnvironmentState,
    GoldAnnotation,
    GoldIssue,
    GradeResult,
    ReviewAction,
    ReviewObservation,
)
from grader import grade_review


# ────────────────────── Task Loader ────────────────────────────

TASKS_DIR = Path(__file__).parent / "tasks"


def _load_task(task_id: str) -> dict[str, Any]:
    """Load a single task JSON from the tasks/ directory."""
    path = TASKS_DIR / f"{task_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Task file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _list_task_ids() -> list[str]:
    """List all available task IDs."""
    if not TASKS_DIR.exists():
        return []
    return sorted(
        p.stem for p in TASKS_DIR.glob("*.json")
    )


def _task_to_observation(task: dict[str, Any]) -> ReviewObservation:
    """Convert a task dict into a ReviewObservation."""
    return ReviewObservation(
        task_id=task["task_id"],
        diff=task["diff"],
        file_context=task.get("file_context", ""),
        language=task.get("language", "python"),
        pr_description=task.get("pr_description", task.get("title", "")),
        metadata={
            "title": task.get("title", ""),
            "author": task.get("author", "contributor"),
        },
    )


def _task_to_gold(task: dict[str, Any]) -> GoldAnnotation:
    """Convert a task dict into a GoldAnnotation."""
    gold_issues = [
        GoldIssue(**gi) for gi in task.get("gold_issues", [])
    ]
    return GoldAnnotation(
        issues=gold_issues,
        summary_keywords=task.get("gold_summary_keywords", []),
        should_approve=task.get("should_approve", len(gold_issues) == 0),
    )


# ────────────────────── Environment ────────────────────────────

class CodeReviewEnv:
    """
    OpenEnv Code Review Environment.

    Usage:
        env = CodeReviewEnv()
        obs = env.reset()                    # or env.reset(task_id="task_001_null_check")
        obs, reward, done, info = env.step(action)
        state = env.state()
    """

    def __init__(self):
        self._task_ids = _list_task_ids()
        self._current_task: dict[str, Any] | None = None
        self._current_gold: GoldAnnotation | None = None
        self._episode_id: str = ""
        self._step_count: int = 0
        self._done: bool = True
        self._last_reward: float | None = None
        self._task_index: int = 0

    # ─────────── reset ───────────

    def reset(self, task_id: str | None = None) -> ReviewObservation:
        """
        Start a new episode.

        Args:
            task_id: Specific task to load. If None, cycles through tasks sequentially.

        Returns:
            ReviewObservation for the agent to process.
        """
        if task_id is None:
            if not self._task_ids:
                raise RuntimeError("No tasks found in tasks/ directory")
            task_id = self._task_ids[self._task_index % len(self._task_ids)]
            self._task_index += 1

        self._current_task = _load_task(task_id)
        self._current_gold = _task_to_gold(self._current_task)
        self._episode_id = str(uuid.uuid4())[:8]
        self._step_count = 0
        self._done = False
        self._last_reward = None

        return _task_to_observation(self._current_task)

    # ─────────── step ────────────

    def step(
        self, action: ReviewAction
    ) -> tuple[Optional[ReviewObservation], float, bool, dict[str, Any]]:
        """
        Process the agent's review action.

        Args:
            action: The agent's structured review output.

        Returns:
            (observation, reward, done, info)
            - observation: None (episode ends after one step)
            - reward: float in [0, 1]
            - done: True (single-step episodes)
            - info: dict with grade_result and task details
        """
        if self._done:
            raise RuntimeError("Episode is done. Call reset() to start a new episode.")
        if self._current_gold is None:
            raise RuntimeError("No task loaded. Call reset() first.")

        self._step_count += 1
        self._done = True

        # Grade the review
        grade_result: GradeResult = grade_review(action, self._current_gold)
        self._last_reward = grade_result.score

        info = {
            "grade_result": grade_result.model_dump(),
            "task_id": self._current_task["task_id"] if self._current_task else "",
            "episode_id": self._episode_id,
        }

        return None, grade_result.score, True, info

    # ─────────── state ───────────

    def state(self) -> EnvironmentState:
        """Return current environment state metadata."""
        return EnvironmentState(
            episode_id=self._episode_id,
            task_id=self._current_task["task_id"] if self._current_task else "",
            step_count=self._step_count,
            done=self._done,
            last_reward=self._last_reward,
            total_tasks=len(self._task_ids),
        )

    # ─────────── helpers ─────────

    @property
    def task_ids(self) -> list[str]:
        return list(self._task_ids)

    @property
    def current_gold(self) -> GoldAnnotation | None:
        return self._current_gold

    def get_task_title(self, task_id: str) -> str:
        """Get the human-readable title for a task."""
        try:
            task = _load_task(task_id)
            return task.get("title", task_id)
        except FileNotFoundError:
            return task_id
