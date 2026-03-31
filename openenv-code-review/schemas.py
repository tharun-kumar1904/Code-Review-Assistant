"""
Pydantic schemas for the OpenEnv Code Review Assistant.
Defines typed interfaces between agent and environment.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


# ──────────────────────────── Enums ────────────────────────────

class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

    @classmethod
    def rank(cls, s: "Severity") -> int:
        return {cls.CRITICAL: 4, cls.HIGH: 3, cls.MEDIUM: 2, cls.LOW: 1, cls.INFO: 0}[s]


class Category(str, Enum):
    BUG = "bug"
    SECURITY = "security"
    PERFORMANCE = "performance"
    STYLE = "style"
    LOGIC = "logic"
    ERROR_HANDLING = "error_handling"


RELATED_CATEGORIES: dict[Category, set[Category]] = {
    Category.BUG: {Category.LOGIC, Category.ERROR_HANDLING},
    Category.LOGIC: {Category.BUG},
    Category.ERROR_HANDLING: {Category.BUG},
    Category.SECURITY: set(),
    Category.PERFORMANCE: set(),
    Category.STYLE: set(),
}


# ──────────────────────── Observation ──────────────────────────

class ReviewObservation(BaseModel):
    """What the agent receives from the environment."""
    task_id: str = Field(..., description="Unique task identifier")
    diff: str = Field(..., description="Unified diff text")
    file_context: str = Field("", description="Full file content for context")
    language: str = Field("python", description="Programming language")
    pr_description: str = Field("", description="PR title / description")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Extra metadata")


# ─────────────────────────── Action ────────────────────────────

class ReviewIssue(BaseModel):
    """A single issue detected by the agent."""
    file: str = Field(..., description="Filename where issue was found")
    line: int = Field(..., description="Line number (1-indexed)")
    severity: Severity = Field(..., description="Issue severity level")
    category: Category = Field(..., description="Issue category")
    description: str = Field(..., description="What the issue is")
    suggested_fix: Optional[str] = Field(None, description="How to fix it")
    confidence: float = Field(
        1.0, ge=0.0, le=1.0, description="Agent's confidence in this issue"
    )


class ReviewAction(BaseModel):
    """What the agent submits to the environment."""
    issues: list[ReviewIssue] = Field(default_factory=list, description="Detected issues")
    summary: str = Field("", description="One-paragraph review summary")
    approve: bool = Field(True, description="Whether to approve the PR")


# ──────────────────── Gold Standard ────────────────────────────

class GoldIssue(BaseModel):
    """Ground-truth issue from the task dataset."""
    file: str
    line: int
    severity: Severity
    category: Category
    description: str


class GoldAnnotation(BaseModel):
    """Complete ground-truth for a single task."""
    issues: list[GoldIssue] = Field(default_factory=list)
    summary_keywords: list[str] = Field(default_factory=list)
    should_approve: bool = True


# ──────────────────── Grading Results ──────────────────────────

class GradeBreakdown(BaseModel):
    """Detailed grading breakdown."""
    recall: float = Field(0.0, ge=0.0, le=1.0)
    precision: float = Field(0.0, ge=0.0, le=1.0)
    severity_accuracy: float = Field(0.0, ge=0.0, le=1.0)
    feedback_quality: float = Field(0.0, ge=0.0, le=1.0)
    summary_quality: float = Field(0.0, ge=0.0, le=1.0)
    matched_issues: int = 0
    false_positives: int = 0
    missed_issues: int = 0
    total_gold: int = 0
    total_agent: int = 0


class GradeResult(BaseModel):
    """Complete grading output."""
    score: float = Field(0.0, ge=0.0, le=1.0)
    breakdown: GradeBreakdown = Field(default_factory=GradeBreakdown)
    matched_pairs: list[dict[str, Any]] = Field(
        default_factory=list, description="Agent ↔ Gold issue pairings"
    )
    feedback: str = Field("", description="Human-readable grading feedback")


# ──────────────────── Environment State ────────────────────────

class EnvironmentState(BaseModel):
    """Current state of the environment episode."""
    episode_id: str = ""
    task_id: str = ""
    step_count: int = 0
    done: bool = False
    last_reward: Optional[float] = None
    total_tasks: int = 0
