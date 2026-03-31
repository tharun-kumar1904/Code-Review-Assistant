"""
Reward function — computes a scalar reward ∈ [0, 1] from grading breakdown.

reward = Σ (weight_i × criterion_i)

Default weights:
  recall:           0.35
  precision:        0.15
  severity_accuracy: 0.20
  feedback_quality:  0.20
  summary_quality:   0.10
"""

from __future__ import annotations

from dataclasses import dataclass

from schemas import GradeBreakdown


@dataclass
class RewardConfig:
    """Tunable weights for the reward function."""
    w_recall: float = 0.35
    w_precision: float = 0.15
    w_severity: float = 0.20
    w_feedback: float = 0.20
    w_summary: float = 0.10

    def __post_init__(self):
        total = (
            self.w_recall + self.w_precision + self.w_severity
            + self.w_feedback + self.w_summary
        )
        assert abs(total - 1.0) < 1e-6, f"Weights must sum to 1.0, got {total}"


DEFAULT_CONFIG = RewardConfig()


def compute_reward(
    breakdown: GradeBreakdown,
    config: RewardConfig | None = None,
) -> float:
    """
    Compute reward from grading breakdown.

    Args:
        breakdown: Per-criterion scores from the grader
        config: Optional custom weights (defaults to DEFAULT_CONFIG)

    Returns:
        Reward in [0.0, 1.0]
    """
    c = config or DEFAULT_CONFIG
    reward = (
        c.w_recall * breakdown.recall
        + c.w_precision * breakdown.precision
        + c.w_severity * breakdown.severity_accuracy
        + c.w_feedback * breakdown.feedback_quality
        + c.w_summary * breakdown.summary_quality
    )
    return max(0.0, min(1.0, round(reward, 4)))
