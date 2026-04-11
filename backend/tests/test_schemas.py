"""
Tests for Pydantic request/response schemas.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from datetime import datetime
from schemas import (
    AnalyzePRRequest,
    ReviewCommentResponse,
    ReviewResultResponse,
    RepositoryResponse,
    AnalysisTaskResponse,
    RepositoryInsightsResponse,
    SeverityEnum,
    CategoryEnum,
)
from pydantic import ValidationError


# ── Request Schemas ───────────────────────────────────────────────────

class TestAnalyzePRRequest:
    def test_valid_request(self):
        req = AnalyzePRRequest(repo_owner="acme", repo_name="backend", pr_number=42)
        assert req.repo_owner == "acme"
        assert req.repo_name == "backend"
        assert req.pr_number == 42

    def test_missing_required_field(self):
        with pytest.raises(ValidationError):
            AnalyzePRRequest(repo_owner="acme", repo_name="backend")

    def test_invalid_pr_number_type(self):
        with pytest.raises(ValidationError):
            AnalyzePRRequest(repo_owner="acme", repo_name="backend", pr_number="not-a-number")


# ── Enum Schemas ──────────────────────────────────────────────────────

class TestEnums:
    def test_severity_values(self):
        assert SeverityEnum.CRITICAL == "critical"
        assert SeverityEnum.HIGH == "high"
        assert SeverityEnum.MEDIUM == "medium"
        assert SeverityEnum.LOW == "low"
        assert SeverityEnum.INFO == "info"

    def test_category_values(self):
        assert CategoryEnum.BUG == "bug"
        assert CategoryEnum.SECURITY == "security"
        assert CategoryEnum.PERFORMANCE == "performance"


# ── Response Schemas ──────────────────────────────────────────────────

class TestReviewCommentResponse:
    def test_valid_comment(self):
        comment = ReviewCommentResponse(
            id=1,
            file_path="test.py",
            severity=SeverityEnum.HIGH,
            category=CategoryEnum.BUG,
            issue="Null reference",
            created_at=datetime.now(),
        )
        assert comment.id == 1
        assert comment.confidence == 0.8  # default
        assert comment.source == "llm"  # default

    def test_optional_fields(self):
        comment = ReviewCommentResponse(
            id=1,
            file_path="test.py",
            severity=SeverityEnum.LOW,
            category=CategoryEnum.STYLE,
            issue="Naming",
            created_at=datetime.now(),
        )
        assert comment.line_number is None
        assert comment.explanation is None
        assert comment.suggested_fix is None


class TestAnalysisTaskResponse:
    def test_defaults(self):
        task = AnalysisTaskResponse(task_id="abc-123")
        assert task.status == "queued"
        assert task.message == "PR analysis has been queued"


class TestReviewResultResponse:
    def test_empty_lists_default(self):
        result = ReviewResultResponse(
            id=1,
            created_at=datetime.now(),
        )
        assert result.comments == []
        assert result.security_issues == []
        assert result.code_metrics == []
        assert result.quality_score == 0.0

    def test_with_nested_comments(self):
        result = ReviewResultResponse(
            id=1,
            summary="Test review",
            quality_score=85.0,
            total_issues=1,
            created_at=datetime.now(),
            comments=[
                ReviewCommentResponse(
                    id=1,
                    file_path="a.py",
                    severity=SeverityEnum.MEDIUM,
                    category=CategoryEnum.PERFORMANCE,
                    issue="Slow query",
                    created_at=datetime.now(),
                )
            ],
        )
        assert len(result.comments) == 1
        assert result.comments[0].issue == "Slow query"


class TestRepositoryInsightsResponse:
    def test_defaults(self):
        repo = RepositoryResponse(
            id=1,
            owner="acme",
            name="backend",
            full_name="acme/backend",
            created_at=datetime.now(),
        )
        insights = RepositoryInsightsResponse(repository=repo)
        assert insights.total_prs_analyzed == 0
        assert insights.avg_quality_score == 0.0
        assert insights.quality_trend == []
        assert insights.severity_distribution == {}
