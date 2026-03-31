"""
SQLAlchemy ORM models for the AI Code Review Assistant.
"""

from sqlalchemy import (
    Column, Integer, String, Text, Float, DateTime, ForeignKey, Enum
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
from database import Base
import enum


# ── Enums ────────────────────────────────────────────────────────────────

class Severity(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class IssueCategory(str, enum.Enum):
    BUG = "bug"
    SECURITY = "security"
    PERFORMANCE = "performance"
    STYLE = "style"
    LOGIC = "logic"
    DESIGN = "design"
    DOCUMENTATION = "documentation"


class PRStatus(str, enum.Enum):
    PENDING = "pending"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"


# ── Models ───────────────────────────────────────────────────────────────

class Repository(Base):
    __tablename__ = "repositories"

    id = Column(Integer, primary_key=True, index=True)
    owner = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    full_name = Column(String(512), unique=True, nullable=False)
    github_url = Column(String(1024))
    language = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    pull_requests = relationship("PullRequest", back_populates="repository")
    code_embeddings = relationship("CodeEmbedding", back_populates="repository")


class PullRequest(Base):
    __tablename__ = "pull_requests"

    id = Column(Integer, primary_key=True, index=True)
    pr_number = Column(Integer, nullable=False)
    title = Column(String(1024))
    author = Column(String(255))
    state = Column(String(50), default="open")
    github_url = Column(String(1024))
    head_sha = Column(String(64))
    base_branch = Column(String(255))
    head_branch = Column(String(255))
    files_changed = Column(Integer, default=0)
    additions = Column(Integer, default=0)
    deletions = Column(Integer, default=0)
    analysis_status = Column(
        Enum(PRStatus), default=PRStatus.PENDING, nullable=False
    )
    repository_id = Column(Integer, ForeignKey("repositories.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    repository = relationship("Repository", back_populates="pull_requests")
    review_results = relationship("ReviewResult", back_populates="pull_request")


class ReviewResult(Base):
    __tablename__ = "review_results"

    id = Column(Integer, primary_key=True, index=True)
    summary = Column(Text)
    quality_score = Column(Float, default=0.0)  # 0-100
    total_issues = Column(Integer, default=0)
    critical_issues = Column(Integer, default=0)
    high_issues = Column(Integer, default=0)
    medium_issues = Column(Integer, default=0)
    low_issues = Column(Integer, default=0)
    analysis_duration = Column(Float)  # seconds
    llm_provider = Column(String(50))
    llm_model = Column(String(100))
    pull_request_id = Column(Integer, ForeignKey("pull_requests.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    pull_request = relationship("PullRequest", back_populates="review_results")
    comments = relationship("ReviewComment", back_populates="review_result")
    security_issues = relationship("SecurityIssue", back_populates="review_result")
    code_metrics = relationship("CodeMetrics", back_populates="review_result")


class ReviewComment(Base):
    __tablename__ = "review_comments"

    id = Column(Integer, primary_key=True, index=True)
    file_path = Column(String(1024), nullable=False)
    line_number = Column(Integer)
    severity = Column(Enum(Severity), default=Severity.MEDIUM)
    category = Column(Enum(IssueCategory), default=IssueCategory.BUG)
    issue = Column(Text, nullable=False)
    explanation = Column(Text)
    suggested_fix = Column(Text)
    code_snippet = Column(Text)
    confidence = Column(Float, default=0.8)
    source = Column(String(50), default="llm")  # llm | static | security
    review_result_id = Column(Integer, ForeignKey("review_results.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    review_result = relationship("ReviewResult", back_populates="comments")


class SecurityIssue(Base):
    __tablename__ = "security_issues"

    id = Column(Integer, primary_key=True, index=True)
    vulnerability_type = Column(String(255), nullable=False)
    severity = Column(Enum(Severity), default=Severity.HIGH)
    file_path = Column(String(1024))
    line_number = Column(Integer)
    description = Column(Text)
    remediation = Column(Text)
    cwe_id = Column(String(20))  # e.g. CWE-89
    owasp_category = Column(String(100))
    code_snippet = Column(Text)
    review_result_id = Column(Integer, ForeignKey("review_results.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    review_result = relationship("ReviewResult", back_populates="security_issues")


class CodeMetrics(Base):
    __tablename__ = "code_metrics"

    id = Column(Integer, primary_key=True, index=True)
    file_path = Column(String(1024))
    cyclomatic_complexity = Column(Float, default=0.0)
    maintainability_index = Column(Float, default=0.0)
    lines_of_code = Column(Integer, default=0)
    comment_ratio = Column(Float, default=0.0)
    duplication_percentage = Column(Float, default=0.0)
    halstead_volume = Column(Float, default=0.0)
    review_result_id = Column(Integer, ForeignKey("review_results.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    review_result = relationship("ReviewResult", back_populates="code_metrics")


class CodeEmbedding(Base):
    __tablename__ = "code_embeddings"

    id = Column(Integer, primary_key=True, index=True)
    file_path = Column(String(1024), nullable=False)
    chunk_index = Column(Integer, default=0)
    content = Column(Text) 
    embedding = Column(Vector(1536))  # OpenAI text-embedding-3-small
    repository_id = Column(Integer, ForeignKey("repositories.id"))
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

    repository = relationship("Repository", back_populates="code_embeddings")
