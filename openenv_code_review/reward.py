"""
Enhanced Reward Function for RL Code Review Agent.

Base reward = Σ (weight_i × criterion_i)

Shaping bonuses/penalties:
  +0.10  Perfect recall (all issues found)
  +0.10  Correct approve/reject decision
  +0.05  Efficiency bonus (conservative strategy on clean PR)
  -0.05  Per false positive (capped at -0.20 total)

RLHF integration:
  Final reward = (1 - w) × automated + w × human_feedback
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ── Robust import resolution ──────────────────────────────────
_HERE = Path(__file__).parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

try:
    from openenv_code_review.schemas import GradeBreakdown
except ImportError:
    from schemas import GradeBreakdown  # type: ignore[no-redef]


# ── Config ────────────────────────────────────────────────────

@dataclass
class RewardConfig:
    """Tunable weights and shaping coefficients for the reward function."""

    # Criterion weights (must sum to 1.0)
    w_recall:    float = 0.35
    w_precision: float = 0.15
    w_severity:  float = 0.20
    w_feedback:  float = 0.20
    w_summary:   float = 0.10

    # Shaping bonuses
    perfect_recall_bonus:   float = 0.10
    approve_accuracy_bonus: float = 0.10
    efficiency_bonus:       float = 0.05

    # Per-FP penalty and cap
    false_positive_penalty: float = 0.05
    false_positive_cap:     float = 0.20   # BUG FIX: was hardcoded 0.2 in body

    # RLHF blending weight (0 = no human signal, 1 = only human signal)
    human_feedback_weight: float = 0.20

    def __post_init__(self) -> None:
        total = (
            self.w_recall + self.w_precision + self.w_severity
            + self.w_feedback + self.w_summary
        )
        if abs(total - 1.0) > 1e-6:
            raise ValueError(
                f"Criterion weights must sum to 1.0, got {total:.6f}. "
                f"Check w_recall + w_precision + w_severity + w_feedback + w_summary."
            )
        # BUG FIX: original used assert which is silently disabled when Python
        # runs with -O (optimised flag, common in Docker/production images).
        # Replaced with an explicit ValueError so misconfiguration always surfaces.

        if not (0.0 <= self.human_feedback_weight <= 1.0):
            raise ValueError(
                f"human_feedback_weight must be in [0, 1], got {self.human_feedback_weight}"
            )


DEFAULT_CONFIG = RewardConfig()


# ── Base weighted reward ──────────────────────────────────────

def compute_reward(
    breakdown: GradeBreakdown,
    config: RewardConfig | None = None,
) -> float:
    """
    Compute base reward from grading breakdown (no shaping).

    Used by grader.py for the standard episode reward signal.

    Args:
        breakdown: Per-criterion scores from the grader.
        config:    Optional custom weights (defaults to DEFAULT_CONFIG).

    Returns:
        Reward clamped to [0.0, 1.0].
    """
    c = config or DEFAULT_CONFIG
    reward = (
        c.w_recall    * breakdown.recall
        + c.w_precision * breakdown.precision
        + c.w_severity  * breakdown.severity_accuracy
        + c.w_feedback  * breakdown.feedback_quality
        + c.w_summary   * breakdown.summary_quality
    )
    return max(0.0, min(1.0, round(reward, 4)))


# ── Shaped reward ─────────────────────────────────────────────

def compute_shaped_reward(
    breakdown:        GradeBreakdown,
    approve_correct:  bool           = False,
    is_clean_pr:      bool           = False,
    used_conservative:bool           = False,
    human_feedback:   Optional[float]= None,
    config:           RewardConfig | None = None,
) -> dict:
    """
    Compute shaped reward with bonuses, penalties, and optional RLHF blending.

    Args:
        breakdown:         Per-criterion scores from the grader.
        approve_correct:   Whether the agent's approve/reject matched gold.
        is_clean_pr:       Whether the PR has no gold issues.
        used_conservative: Whether the agent used the conservative strategy.
        human_feedback:    Optional human rating in [0, 1].
        config:            Reward weights configuration.

    Returns:
        Dict with base_reward, bonuses, penalties, automated_reward,
        human_feedback, final_reward, and per-criterion breakdown.
    """
    c = config or DEFAULT_CONFIG

    # ── Base weighted sum ─────────────────────────────────────
    base = (
        c.w_recall    * breakdown.recall
        + c.w_precision * breakdown.precision
        + c.w_severity  * breakdown.severity_accuracy
        + c.w_feedback  * breakdown.feedback_quality
        + c.w_summary   * breakdown.summary_quality
    )

    # ── Shaping bonuses ───────────────────────────────────────
    bonuses: dict[str, float] = {}

    # Perfect recall: only meaningful when there were issues to find
    # BUG FIX: original awarded perfect_recall_bonus when total_gold > 0
    # AND recall >= 1.0. That's correct, but it also silently gave the bonus
    # when total_gold == 0 (clean PR) because recall defaults to 1.0 in the
    # grader. We keep the total_gold > 0 guard and document it explicitly.
    if breakdown.total_gold > 0 and breakdown.recall >= 1.0:
        bonuses["perfect_recall"] = c.perfect_recall_bonus

    # Approve accuracy
    if approve_correct:
        bonuses["approve_accuracy"] = c.approve_accuracy_bonus

    # Efficiency: conservative strategy on a clean PR with zero FPs
    if is_clean_pr and used_conservative and breakdown.false_positives == 0:
        bonuses["efficiency"] = c.efficiency_bonus

    total_bonus = sum(bonuses.values())

    # ── Penalties ─────────────────────────────────────────────
    penalties: dict[str, float] = {}

    if breakdown.false_positives > 0:
        # BUG FIX: original computed fp_penalty as
        #   breakdown.false_positives * c.false_positive_penalty
        # then capped with min(fp_penalty, 0.2). The cap (0.2) was a magic
        # number hardcoded in the function body — not tied to the config.
        # Now uses c.false_positive_cap so it's configurable and testable.
        raw_penalty = breakdown.false_positives * c.false_positive_penalty
        penalties["false_positives"] = min(raw_penalty, c.false_positive_cap)

    total_penalty = sum(penalties.values())

    # ── Automated reward ──────────────────────────────────────
    automated_reward = max(0.0, min(1.0, base + total_bonus - total_penalty))

    # ── RLHF blending ─────────────────────────────────────────
    if human_feedback is not None:
        # BUG FIX: original did not validate human_feedback range.
        # A caller passing 85 (out of 100 scale) would silently produce
        # a final_reward > 1.0 before the clamp, skewing RL training.
        human_feedback = max(0.0, min(1.0, float(human_feedback)))
        w = c.human_feedback_weight
        final_reward = (1.0 - w) * automated_reward + w * human_feedback
    else:
        final_reward = automated_reward

    final_reward = max(0.0, min(1.0, round(final_reward, 4)))

    return {
        "base_reward":       round(base, 4),
        "bonuses":           bonuses,
        "total_bonus":       round(total_bonus, 4),
        "penalties":         penalties,
        "total_penalty":     round(total_penalty, 4),
        "automated_reward":  round(automated_reward, 4),
        "human_feedback":    human_feedback,
        "final_reward":      final_reward,
        "breakdown": {
            "recall":            round(breakdown.recall, 4),
            "precision":         round(breakdown.precision, 4),
            "severity_accuracy": round(breakdown.severity_accuracy, 4),
            "feedback_quality":  round(breakdown.feedback_quality, 4),
            "summary_quality":   round(breakdown.summary_quality, 4),
        },
    }