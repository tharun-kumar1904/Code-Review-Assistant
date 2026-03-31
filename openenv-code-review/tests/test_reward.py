"""
Tests for the reward function.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from reward import compute_reward, RewardConfig
from schemas import GradeBreakdown


class TestRewardComputation:
    def test_perfect_score(self):
        breakdown = GradeBreakdown(
            recall=1.0, precision=1.0, severity_accuracy=1.0,
            feedback_quality=1.0, summary_quality=1.0,
        )
        assert compute_reward(breakdown) == 1.0

    def test_zero_score(self):
        breakdown = GradeBreakdown()
        assert compute_reward(breakdown) == 0.0

    def test_partial_score(self):
        breakdown = GradeBreakdown(
            recall=0.67, precision=1.0, severity_accuracy=0.83,
            feedback_quality=0.80, summary_quality=0.90,
        )
        reward = compute_reward(breakdown)
        expected = 0.35 * 0.67 + 0.15 * 1.0 + 0.20 * 0.83 + 0.20 * 0.80 + 0.10 * 0.90
        assert abs(reward - round(expected, 4)) < 0.01

    def test_reward_clamped_to_01(self):
        breakdown = GradeBreakdown(
            recall=1.0, precision=1.0, severity_accuracy=1.0,
            feedback_quality=1.0, summary_quality=1.0,
        )
        assert 0.0 <= compute_reward(breakdown) <= 1.0

    def test_custom_weights(self):
        config = RewardConfig(
            w_recall=0.50, w_precision=0.20, w_severity=0.10,
            w_feedback=0.10, w_summary=0.10,
        )
        breakdown = GradeBreakdown(
            recall=1.0, precision=0.0, severity_accuracy=0.5,
            feedback_quality=0.5, summary_quality=0.5,
        )
        reward = compute_reward(breakdown, config)
        expected = 0.50 * 1.0 + 0.20 * 0.0 + 0.10 * 0.5 + 0.10 * 0.5 + 0.10 * 0.5
        assert abs(reward - round(expected, 4)) < 0.01

    def test_invalid_weights_raises(self):
        with pytest.raises(AssertionError):
            RewardConfig(w_recall=0.5, w_precision=0.5, w_severity=0.5,
                         w_feedback=0.5, w_summary=0.5)
