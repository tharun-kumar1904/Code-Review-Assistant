"""
Tests for the grader module.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from grader import grade_review, _issues_match, _match_issues
from schemas import (
    ReviewAction,
    ReviewIssue,
    GoldAnnotation,
    GoldIssue,
    Severity,
    Category,
)


# ─────────────── Fixtures ──────────────────────────────────────

@pytest.fixture
def gold_single_bug():
    return GoldAnnotation(
        issues=[
            GoldIssue(
                file="app.py",
                line=15,
                severity=Severity.HIGH,
                category=Category.BUG,
                description="Missing null check",
            )
        ],
        summary_keywords=["null", "None", "check"],
    )


@pytest.fixture
def gold_two_issues():
    return GoldAnnotation(
        issues=[
            GoldIssue(file="proc.py", line=34, severity=Severity.HIGH, category=Category.BUG, description="Off by one"),
            GoldIssue(file="proc.py", line=42, severity=Severity.MEDIUM, category=Category.ERROR_HANDLING, description="Bare except"),
        ],
        summary_keywords=["off-by-one", "exception"],
    )


@pytest.fixture
def gold_empty():
    return GoldAnnotation(issues=[], summary_keywords=["clean", "no issues"])


# ─────────────── Issue Matching ────────────────────────────────

class TestIssueMatching:
    def test_exact_match(self):
        a = ReviewIssue(file="a.py", line=10, severity=Severity.HIGH, category=Category.BUG, description="x")
        g = GoldIssue(file="a.py", line=10, severity=Severity.HIGH, category=Category.BUG, description="x")
        assert _issues_match(a, g)

    def test_close_line_match(self):
        a = ReviewIssue(file="a.py", line=12, severity=Severity.HIGH, category=Category.BUG, description="x")
        g = GoldIssue(file="a.py", line=10, severity=Severity.HIGH, category=Category.BUG, description="x")
        assert _issues_match(a, g)

    def test_too_far_line(self):
        a = ReviewIssue(file="a.py", line=20, severity=Severity.HIGH, category=Category.BUG, description="x")
        g = GoldIssue(file="a.py", line=10, severity=Severity.HIGH, category=Category.BUG, description="x")
        assert not _issues_match(a, g)

    def test_wrong_file(self):
        a = ReviewIssue(file="b.py", line=10, severity=Severity.HIGH, category=Category.BUG, description="x")
        g = GoldIssue(file="a.py", line=10, severity=Severity.HIGH, category=Category.BUG, description="x")
        assert not _issues_match(a, g)

    def test_related_category_match(self):
        a = ReviewIssue(file="a.py", line=10, severity=Severity.HIGH, category=Category.LOGIC, description="x")
        g = GoldIssue(file="a.py", line=10, severity=Severity.HIGH, category=Category.BUG, description="x")
        assert _issues_match(a, g)


# ─────────────── Grading ───────────────────────────────────────

class TestGrading:
    def test_perfect_review(self, gold_single_bug):
        action = ReviewAction(
            issues=[
                ReviewIssue(
                    file="app.py", line=15, severity=Severity.HIGH,
                    category=Category.BUG,
                    description="Missing null check on the user object before accessing attributes",
                    suggested_fix="Add if user is None check",
                )
            ],
            summary="Found a null reference issue. The user object may be None.",
            approve=False,
        )
        result = grade_review(action, gold_single_bug)
        assert result.score >= 0.8
        assert result.breakdown.recall == 1.0
        assert result.breakdown.precision == 1.0
        assert result.breakdown.matched_issues == 1

    def test_empty_review_with_bugs(self, gold_single_bug):
        action = ReviewAction(issues=[], summary="", approve=True)
        result = grade_review(action, gold_single_bug)
        assert result.score <= 0.2
        assert result.breakdown.recall == 0.0
        assert result.breakdown.missed_issues == 1

    def test_all_false_positives(self, gold_single_bug):
        action = ReviewAction(
            issues=[
                ReviewIssue(
                    file="other.py", line=100, severity=Severity.LOW,
                    category=Category.STYLE, description="Some style issue",
                )
            ],
            summary="Found some issues.",
            approve=False,
        )
        result = grade_review(action, gold_single_bug)
        assert result.breakdown.false_positives == 1
        assert result.breakdown.recall == 0.0

    def test_clean_pr_no_issues(self, gold_empty):
        action = ReviewAction(
            issues=[],
            summary="Clean code with no issues found.",
            approve=True,
        )
        result = grade_review(action, gold_empty)
        assert result.breakdown.recall == 1.0  # No bugs to find
        assert result.breakdown.precision == 1.0  # No false positives

    def test_partial_detection(self, gold_two_issues):
        action = ReviewAction(
            issues=[
                ReviewIssue(
                    file="proc.py", line=34, severity=Severity.HIGH,
                    category=Category.BUG,
                    description="Off by one error in the loop range that skips the first element",
                )
            ],
            summary="Found an off-by-one issue.",
            approve=False,
        )
        result = grade_review(action, gold_two_issues)
        assert result.breakdown.matched_issues == 1
        assert result.breakdown.missed_issues == 1
        assert 0.3 <= result.score <= 0.8

    def test_severity_mismatch_penalty(self, gold_single_bug):
        action = ReviewAction(
            issues=[
                ReviewIssue(
                    file="app.py", line=15, severity=Severity.INFO,
                    category=Category.BUG,
                    description="There might be a null check issue here with the user object",
                )
            ],
            summary="Minor null concern noted.",
            approve=True,
        )
        result = grade_review(action, gold_single_bug)
        # Severity is way off (info vs high = 3 levels) → severity_accuracy should be 0
        assert result.breakdown.severity_accuracy == 0.0
