"""
Pydantic schemas for the OpenEnv Code Review Assistant.
Defines typed interfaces between agent, environment, and grader.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ──────────────────────────── Enums ────────────────────────────

class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH     = "high"
    MEDIUM   = "medium"
    LOW      = "low"
    INFO     = "info"

    @classmethod
    def rank(cls, s: "Severity") -> int:
        """
        Return an integer rank for severity comparison.

        BUG FIX: original used a dict literal rebuilt on every call —
        O(1) but allocates a new dict each time. Replaced with a module-
        level constant looked up via the classmethod.
        """
        return _SEVERITY_RANK[s]


# Module-level constant — built once, never reallocated
_SEVERITY_RANK: dict[Severity, int] = {
    Severity.CRITICAL: 4,
    Severity.HIGH:     3,
    Severity.MEDIUM:   2,
    Severity.LOW:      1,
    Severity.INFO:     0,
}


class Category(str, Enum):
    BUG            = "bug"
    SECURITY       = "security"
    PERFORMANCE    = "performance"
    STYLE          = "style"
    LOGIC          = "logic"
    ERROR_HANDLING = "error_handling"


# Related categories for fuzzy issue matching in the grader.
# Symmetric pairs are intentionally one-directional: a "logic" issue
# reported by the agent can match a "bug" gold issue, but not vice-versa
# unless explicitly listed.
RELATED_CATEGORIES: dict[Category, set[Category]] = {
    Category.BUG:            {Category.LOGIC, Category.ERROR_HANDLING},
    Category.LOGIC:          {Category.BUG},
    Category.ERROR_HANDLING: {Category.BUG, Category.LOGIC},
    Category.SECURITY:       set(),
    Category.PERFORMANCE:    set(),
    Category.STYLE:          set(),
}


# ──────────────────────── Observation ──────────────────────────

class ReviewObservation(BaseModel):
    """What the agent receives from the environment."""

    task_id:        str            = Field(..., description="Unique task identifier")
    diff:           str            = Field(..., description="Unified diff text")
    file_context:   str            = Field("",  description="Full file content for context")
    language:       str            = Field("python", description="Programming language")
    pr_description: str            = Field("",  description="PR title / description")
    metadata:       dict[str, Any] = Field(default_factory=dict, description="Extra metadata")

    @field_validator("diff")
    @classmethod
    def diff_not_empty(cls, v: str) -> str:
        # BUG FIX: an empty diff is a data error — the agent has nothing to
        # review but will silently produce an empty ReviewAction. Catch it
        # early with a clear message rather than letting it produce 0-reward
        # episodes that are hard to debug.
        if not v or not v.strip():
            raise ValueError("diff must not be empty")
        return v


# ─────────────────────────── Action ────────────────────────────

class ReviewIssue(BaseModel):
    """A single issue detected by the agent."""

    file:          str           = Field(..., description="Filename where issue was found")
    line:          int           = Field(..., description="Line number (1-indexed)", ge=1)
    severity:      Severity      = Field(..., description="Issue severity level")
    category:      Category      = Field(..., description="Issue category")
    description:   str           = Field(..., description="What the issue is")
    suggested_fix: Optional[str] = Field(None, description="How to fix it")
    confidence:    float         = Field(
        1.0, ge=0.0, le=1.0, description="Agent's confidence in this issue (0–1)"
    )

    @field_validator("line")
    @classmethod
    def line_positive(cls, v: int) -> int:
        # BUG FIX: original had no ge= constraint on line, so line=0 or
        # line=-5 were valid. Added ge=1 in Field() above AND this validator
        # for a clear error message.
        if v < 1:
            raise ValueError(f"line must be >= 1 (1-indexed), got {v}")
        return v

    @field_validator("description")
    @classmethod
    def description_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("description must not be empty")
        return v.strip()


class ReviewAction(BaseModel):
    """What the agent submits to the environment."""

    issues:  list[ReviewIssue] = Field(default_factory=list, description="Detected issues")
    summary: str               = Field("", description="One-paragraph review summary")
    approve: bool              = Field(True, description="Whether to approve the PR")

    @model_validator(mode="after")
    def approve_consistent_with_issues(self) -> "ReviewAction":
        """
        Warn (not error) when approve=True but issues were reported.

        BUG FIX: agents occasionally return approve=True with a list of
        critical issues, which is logically inconsistent. We don't raise
        here because the LLM may legitimately suggest minor improvements
        while still approving — but we auto-correct the approve flag when
        any critical/high issue is present, since those should block merge.
        """
        if self.approve and self.issues:
            blocking = [
                i for i in self.issues
                if i.severity in (Severity.CRITICAL, Severity.HIGH)
            ]
            if blocking:
                # Silently correct: critical/high issues should block approval
                object.__setattr__(self, "approve", False)
        return self


# ──────────────────── Gold Standard ────────────────────────────

class GoldIssue(BaseModel):
    """Ground-truth issue from the task dataset."""

    file:        str      = Field(..., description="Filename")
    line:        int      = Field(..., ge=1, description="Line number (1-indexed)")
    severity:    Severity = Field(..., description="Expected severity")
    category:    Category = Field(..., description="Expected category")
    description: str      = Field(..., description="What the issue is")


class GoldAnnotation(BaseModel):
    """Complete ground-truth annotation for a single task."""

    issues:           list[GoldIssue] = Field(default_factory=list)
    summary_keywords: list[str]       = Field(default_factory=list)
    should_approve:   bool            = True

    @model_validator(mode="after")
    def should_approve_consistent(self) -> "GoldAnnotation":
        """
        should_approve must be False when gold issues exist.

        BUG FIX: task JSON files could set should_approve=True alongside
        a non-empty issues list (a data-entry mistake). Auto-correct so
        the grader's approve-accuracy scoring is always consistent.
        """
        if self.issues and self.should_approve:
            object.__setattr__(self, "should_approve", False)
        return self


# ──────────────────── Grading Results ──────────────────────────

class GradeBreakdown(BaseModel):
    """Per-criterion grading breakdown."""

    recall:            float = Field(0.0, ge=0.0, le=1.0)
    precision:         float = Field(0.0, ge=0.0, le=1.0)
    severity_accuracy: float = Field(0.0, ge=0.0, le=1.0)
    feedback_quality:  float = Field(0.0, ge=0.0, le=1.0)
    summary_quality:   float = Field(0.0, ge=0.0, le=1.0)
    matched_issues:    int   = Field(0, ge=0)
    false_positives:   int   = Field(0, ge=0)
    missed_issues:     int   = Field(0, ge=0)
    total_gold:        int   = Field(0, ge=0)
    total_agent:       int   = Field(0, ge=0)

    @model_validator(mode="after")
    def counts_consistent(self) -> "GradeBreakdown":
        """
        Sanity-check that matched + missed == total_gold and
        matched + false_positives == total_agent.

        BUG FIX: the grader could theoretically produce inconsistent counts
        (e.g. matched_issues > total_gold) due to a bug in _match_issues.
        Catching it here surfaces the inconsistency at the schema boundary
        rather than letting it silently corrupt reward calculations.
        """
        if self.total_gold > 0:
            expected = self.matched_issues + self.missed_issues
            if expected != self.total_gold:
                raise ValueError(
                    f"matched_issues ({self.matched_issues}) + missed_issues "
                    f"({self.missed_issues}) must equal total_gold ({self.total_gold}), "
                    f"got {expected}"
                )
        if self.total_agent > 0:
            expected = self.matched_issues + self.false_positives
            if expected != self.total_agent:
                raise ValueError(
                    f"matched_issues ({self.matched_issues}) + false_positives "
                    f"({self.false_positives}) must equal total_agent ({self.total_agent}), "
                    f"got {expected}"
                )
        return self


class GradeResult(BaseModel):
    """Complete grading output returned by grade_review()."""

    score:         float                = Field(0.0, ge=0.0, le=1.0)
    breakdown:     GradeBreakdown       = Field(default_factory=GradeBreakdown)
    matched_pairs: list[dict[str, Any]] = Field(
        default_factory=list, description="Agent ↔ Gold issue pairings"
    )
    feedback:      str                  = Field("", description="Human-readable grading feedback")


# ──────────────────── Environment State ────────────────────────

class EnvironmentState(BaseModel):
    """Snapshot of the current environment episode."""

    episode_id:  str            = ""
    task_id:     str            = ""
    step_count:  int            = Field(0, ge=0)
    done:        bool           = False
    last_reward: Optional[float]= Field(None, ge=0.0, le=1.0)
    total_tasks: int            = Field(0, ge=0)