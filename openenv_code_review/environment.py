"""
OpenEnv-compliant Code Review Environment.

Implements the Gymnasium-style API:
  - reset(task_id=None)  → ReviewObservation
  - step(action)         → (ReviewObservation | None, reward, done, info)
  - state()              → EnvironmentState

Enhanced with:
  - observation_space / action_space properties (Gymnasium-compatible)
  - get_state_vector() for DQN integration
  - Human feedback injection for RLHF
  - Baseline comparison mode
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path
from typing import Any, Optional

import numpy as np

# ── Robust import resolution ──────────────────────────────────
# environment.py may be loaded either as part of the
# "openenv_code_review" package (via the app.py shim) or directly.
# In both cases we need schemas and grader from the same directory.
_HERE = Path(__file__).parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

try:
    # Preferred: package-relative (when loaded via app.py shim)
    from openenv_code_review.schemas import (
        EnvironmentState,
        GoldAnnotation,
        GoldIssue,
        GradeResult,
        ReviewAction,
        ReviewObservation,
    )
    from openenv_code_review.grader import grade_review
except ImportError:
    # Fallback: direct file-relative (when run standalone)
    from schemas import (  # type: ignore[no-redef]
        EnvironmentState,
        GoldAnnotation,
        GoldIssue,
        GradeResult,
        ReviewAction,
        ReviewObservation,
    )
    from grader import grade_review  # type: ignore[no-redef]


# ────────────────────── Task Loader ────────────────────────────

TASKS_DIR = Path(__file__).parent / "tasks"


def _load_task(task_id: str) -> dict[str, Any]:
    """Load a single task JSON from the tasks/ directory."""
    path = TASKS_DIR / f"{task_id}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"Task file not found: {path}\n"
            f"Tasks directory: {TASKS_DIR}\n"
            f"Tasks dir exists: {TASKS_DIR.exists()}\n"
            f"Available tasks: {list(TASKS_DIR.glob('*.json')) if TASKS_DIR.exists() else 'N/A'}"
        )
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _list_task_ids() -> list[str]:
    """List all available task IDs (stems of .json files in tasks/)."""
    if not TASKS_DIR.exists():
        return []
    return sorted(p.stem for p in TASKS_DIR.glob("*.json"))


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
    gold_issues = [GoldIssue(**gi) for gi in task.get("gold_issues", [])]
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
        obs = env.reset()                    # cycles through all tasks
        obs = env.reset(task_id="task_001_null_check")
        obs, reward, done, info = env.step(action)
        state = env.state()

    DQN Integration:
        state_vec = env.get_state_vector()   # Returns 400-dim numpy array
        env.observation_space                # {"shape": (400,), "dtype": "float32"}
        env.action_space                     # {"n": 18, "type": "discrete"}
    """

    observation_space = {"shape": (400,), "dtype": "float32", "type": "box"}
    action_space = {"n": 18, "type": "discrete"}  # 6 strategies × 3 thresholds

    def __init__(self):
        self._task_ids: list[str] = _list_task_ids()
        self._current_task: dict[str, Any] | None = None
        self._current_gold: GoldAnnotation | None = None
        self._current_obs: ReviewObservation | None = None
        self._episode_id: str = ""
        self._step_count: int = 0
        self._done: bool = True
        self._last_reward: float | None = None
        self._task_index: int = 0
        self._human_feedback: float | None = None
        self._episode_history: list[dict[str, Any]] = []

    # ── reset ────────────────────────────────────────────────

    def reset(self, task_id: str | None = None) -> ReviewObservation:
        """
        Start a new episode.

        Args:
            task_id: Specific task to load. If None, cycles sequentially.

        Returns:
            ReviewObservation for the agent to process.

        Raises:
            RuntimeError: If no task JSON files exist in tasks/.
            FileNotFoundError: If a specific task_id is not found.
        """
        if task_id is None:
            if not self._task_ids:
                raise RuntimeError(
                    f"No tasks found in {TASKS_DIR}. "
                    "Make sure the tasks/ directory exists inside your "
                    "openenv-code-review/ folder and contains at least one .json file."
                )
            task_id = self._task_ids[self._task_index % len(self._task_ids)]
            self._task_index += 1

        self._current_task = _load_task(task_id)
        self._current_gold = _task_to_gold(self._current_task)
        self._episode_id = str(uuid.uuid4())[:8]
        self._step_count = 0
        self._done = False
        self._last_reward = None
        self._human_feedback = None
        self._current_obs = _task_to_observation(self._current_task)
        return self._current_obs

    # ── step ─────────────────────────────────────────────────

    def step(
        self, action: ReviewAction
    ) -> tuple[Optional[ReviewObservation], float, bool, dict[str, Any]]:
        """
        Process the agent's review action.

        Returns:
            (observation, reward, done, info)
            - observation: None (single-step episodes)
            - reward: float in [0, 1]
            - done: True
            - info: grade_result, task metadata
        """
        if self._done:
            raise RuntimeError("Episode is done. Call reset() to start a new episode.")
        if self._current_gold is None:
            raise RuntimeError("No task loaded. Call reset() first.")

        self._step_count += 1
        self._done = True

        grade_result: GradeResult = grade_review(action, self._current_gold)

        base_reward = grade_result.score
        if self._human_feedback is not None:
            final_reward = 0.8 * base_reward + 0.2 * self._human_feedback
        else:
            final_reward = base_reward

        # Clamp to strict (0, 1) — validator rejects 0.0 and 1.0
        final_reward = max(0.01, min(0.99, final_reward))
        self._last_reward = final_reward

        info = {
            "grade_result": grade_result.model_dump(),
            "task_id": self._current_task["task_id"] if self._current_task else "",
            "episode_id": self._episode_id,
            "base_reward": base_reward,
            "human_feedback": self._human_feedback,
            "final_reward": final_reward,
        }

        self._episode_history.append({
            "task_id": info["task_id"],
            "reward": final_reward,
            "issues_found": len(action.issues),
            "approved": action.approve,
        })

        return None, final_reward, True, info

    # ── state ─────────────────────────────────────────────────

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

    # ── DQN integration ───────────────────────────────────────

    def get_state_vector(self) -> np.ndarray:
        """Return the current observation as a 400-dim float32 vector for DQN."""
        if self._current_obs is None:
            return np.zeros(400, dtype=np.float32)
        from state_encoder import StateEncoder  # lazy import — optional dep
        encoder = StateEncoder()
        return encoder.encode(self._current_obs)

    # ── RLHF ──────────────────────────────────────────────────

    def inject_human_feedback(self, feedback: float) -> None:
        """
        Inject a human feedback signal (RLHF blend).

        Args:
            feedback: float in [0, 1]. 1.0 = excellent, 0.0 = poor.
        """
        self._human_feedback = max(0.0, min(1.0, feedback))

    # ── properties ────────────────────────────────────────────

    @property
    def task_ids(self) -> list[str]:
        return list(self._task_ids)

    @property
    def current_gold(self) -> GoldAnnotation | None:
        return self._current_gold

    @property
    def current_observation(self) -> ReviewObservation | None:
        return self._current_obs

    @property
    def episode_history(self) -> list[dict[str, Any]]:
        return list(self._episode_history)

    def get_task_title(self, task_id: str) -> str:
        """Return the human-readable title for a task, falling back to task_id."""
        try:
            task = _load_task(task_id)
            return task.get("title", task_id)
        except FileNotFoundError:
            return task_id