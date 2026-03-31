"""
Pydantic schemas for request/response validation.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


# ── Enums ────────────────────────────────────────────────────────────────

class SeverityEnum(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class CategoryEnum(str, Enum):
    BUG = "bug"
    SECURITY = "security"
    PERFORMANCE = "performance"
    STYLE = "style"
    LOGIC = "logic"
    DESIGN = "design"
    DOCUMENTATION = "documentation"


# ── Request Schemas ──────────────────────────────────────────────────────

class AnalyzePRRequest(BaseModel):
    repo_owner: str = Field(..., description="Repository owner")
    repo_name: str = Field(..., description="Repository name")
    pr_number: int = Field(..., description="Pull request number")


# ── Response Schemas ─────────────────────────────────────────────────────

class ReviewCommentResponse(BaseModel):
    id: int
    file_path: str
    line_number: Optional[int] = None
    severity: SeverityEnum
    category: CategoryEnum
    issue: str
    explanation: Optional[str] = None
    suggested_fix: Optional[str] = None
    code_snippet: Optional[str] = None
    confidence: float = 0.8
    source: str = "llm"
    created_at: datetime

    class Config:
        from_attributes = True


class SecurityIssueResponse(BaseModel):
    id: int
    vulnerability_type: str
    severity: SeverityEnum
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    description: Optional[str] = None
    remediation: Optional[str] = None
    cwe_id: Optional[str] = None
    owasp_category: Optional[str] = None
    code_snippet: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class CodeMetricsResponse(BaseModel):
    id: int
    file_path: Optional[str] = None
    cyclomatic_complexity: float = 0.0
    maintainability_index: float = 0.0
    lines_of_code: int = 0
    comment_ratio: float = 0.0
    duplication_percentage: float = 0.0

    class Config:
        from_attributes = True


class ReviewResultResponse(BaseModel):
    id: int
    summary: Optional[str] = None
    quality_score: float = 0.0
    total_issues: int = 0
    critical_issues: int = 0
    high_issues: int = 0
    medium_issues: int = 0
    low_issues: int = 0
    analysis_duration: Optional[float] = None
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    created_at: datetime
    comments: List[ReviewCommentResponse] = []
    security_issues: List[SecurityIssueResponse] = []
    code_metrics: List[CodeMetricsResponse] = []

    class Config:
        from_attributes = True


class PullRequestResponse(BaseModel):
    id: int
    pr_number: int
    title: Optional[str] = None
    author: Optional[str] = None
    state: str = "open"
    github_url: Optional[str] = None
    files_changed: int = 0
    additions: int = 0
    deletions: int = 0
    analysis_status: str = "pending"
    created_at: datetime
    review_results: List[ReviewResultResponse] = []

    class Config:
        from_attributes = True


class RepositoryResponse(BaseModel):
    id: int
    owner: str
    name: str
    full_name: str
    github_url: Optional[str] = None
    language: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AnalysisTaskResponse(BaseModel):
    task_id: str
    status: str = "queued"
    message: str = "PR analysis has been queued"


class RepositoryInsightsResponse(BaseModel):
    repository: RepositoryResponse
    total_prs_analyzed: int = 0
    avg_quality_score: float = 0.0
    total_issues_found: int = 0
    total_security_issues: int = 0
    avg_complexity: float = 0.0
    avg_maintainability: float = 0.0
    quality_trend: List[dict] = []
    severity_distribution: dict = {}


class PaginatedResponse(BaseModel):
    items: List[dict]
    total: int
    page: int
    per_page: int
    pages: int
