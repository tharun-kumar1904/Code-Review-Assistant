"""
Tests for the CodeReviewEnv (OpenEnv interface compliance).
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from environment import CodeReviewEnv
from schemas import ReviewAction, ReviewIssue, Severity, Category


@pytest.fixture
def env():
    return CodeReviewEnv()


class TestReset:
    def test_reset_returns_observation(self, env):
        obs = env.reset(task_id="task_001_null_check")
        assert obs.task_id == "task_001_null_check"
        assert len(obs.diff) > 0
        assert obs.language == "python"

    def test_reset_sequential_cycling(self, env):
        obs1 = env.reset()
        obs2 = env.reset()
        # Should get different tasks
        assert obs1.task_id != obs2.task_id or len(env.task_ids) == 1

    def test_reset_invalid_task_raises(self, env):
        with pytest.raises(FileNotFoundError):
            env.reset(task_id="nonexistent_task")

    def test_reset_clears_state(self, env):
        obs = env.reset(task_id="task_001_null_check")
        state = env.state()
        assert state.step_count == 0
        assert state.done is False
        assert state.last_reward is None


class TestStep:
    def test_step_returns_tuple(self, env):
        env.reset(task_id="task_001_null_check")
        action = ReviewAction(
            issues=[
                ReviewIssue(
                    file="app.py",
                    line=15,
                    severity=Severity.HIGH,
                    category=Category.BUG,
                    description="Missing null check on user object",
                    suggested_fix="Add if user is None check",
                )
            ],
            summary="Found a null reference bug.",
            approve=False,
        )
        obs, reward, done, info = env.step(action)
        assert obs is None  # Episode ends
        assert isinstance(reward, float)
        assert 0.0 <= reward <= 1.0
        assert done is True
        assert "grade_result" in info

    def test_step_perfect_review_high_reward(self, env):
        env.reset(task_id="task_001_null_check")
        action = ReviewAction(
            issues=[
                ReviewIssue(
                    file="app.py",
                    line=15,
                    severity=Severity.HIGH,
                    category=Category.BUG,
                    description="Missing null check on user object. get_user may return None causing AttributeError.",
                    suggested_fix="Add: if user is None: return HTTPException(404)",
                )
            ],
            summary="Critical null reference bug found. The user object from get_user() is not checked for None before attribute access.",
            approve=False,
        )
        _, reward, _, _ = env.step(action)
        assert reward >= 0.7  # Should score well

    def test_step_empty_review_low_reward(self, env):
        env.reset(task_id="task_001_null_check")
        action = ReviewAction(issues=[], summary="", approve=True)
        _, reward, _, _ = env.step(action)
        assert reward <= 0.3  # Should score poorly

    def test_step_when_done_raises(self, env):
        env.reset(task_id="task_001_null_check")
        action = ReviewAction(issues=[], summary="ok", approve=True)
        env.step(action)
        with pytest.raises(RuntimeError):
            env.step(action)

    def test_step_clean_pr_no_issues_high_reward(self, env):
        env.reset(task_id="task_005_clean_pr")
        action = ReviewAction(
            issues=[],
            summary="Clean, well-structured configuration loader with proper error handling. No issues found.",
            approve=True,
        )
        _, reward, _, _ = env.step(action)
        assert reward >= 0.55  # Clean PR with no false positives


class TestState:
    def test_state_initial(self, env):
        state = env.state()
        assert state.done is True  # No episode started
        assert state.total_tasks > 0

    def test_state_after_reset(self, env):
        env.reset(task_id="task_002_sql_inject")
        state = env.state()
        assert state.task_id == "task_002_sql_inject"
        assert state.step_count == 0
        assert state.done is False

    def test_state_after_step(self, env):
        env.reset(task_id="task_002_sql_inject")
        action = ReviewAction(issues=[], summary="ok", approve=True)
        env.step(action)
        state = env.state()
        assert state.step_count == 1
        assert state.done is True
        assert state.last_reward is not None
