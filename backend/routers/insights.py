"""
Insights router — repository insights & security issues.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload
from database import get_db
from models import (
    Repository, PullRequest, ReviewResult,
    SecurityIssue, CodeMetrics, ReviewComment, Severity,
)
from schemas import SecurityIssueResponse, RepositoryInsightsResponse
from typing import Optional

router = APIRouter()


@router.get("/repository-insights/{owner}/{repo}")
async def get_repository_insights(
    owner: str,
    repo: str,
    db: AsyncSession = Depends(get_db),
):
    """Aggregated code quality metrics and trends for a repository."""
    # Find repository
    query = select(Repository).where(
        Repository.owner == owner,
        Repository.name == repo,
    )
    repository = (await db.execute(query)).scalar_one_or_none()

    if not repository:
        return {
            "repository": {"owner": owner, "name": repo, "full_name": f"{owner}/{repo}"},
            "total_prs_analyzed": 0,
            "avg_quality_score": 0,
            "total_issues_found": 0,
            "total_security_issues": 0,
            "avg_complexity": 0,
            "avg_maintainability": 0,
            "quality_trend": [],
            "severity_distribution": {},
        }

    # Aggregate stats
    pr_count = (await db.execute(
        select(func.count()).select_from(PullRequest).where(
            PullRequest.repository_id == repository.id
        )
    )).scalar() or 0

    avg_score = (await db.execute(
        select(func.avg(ReviewResult.quality_score))
        .join(PullRequest)
        .where(PullRequest.repository_id == repository.id)
    )).scalar() or 0

    total_issues = (await db.execute(
        select(func.sum(ReviewResult.total_issues))
        .join(PullRequest)
        .where(PullRequest.repository_id == repository.id)
    )).scalar() or 0

    total_security = (await db.execute(
        select(func.count()).select_from(SecurityIssue)
        .join(ReviewResult)
        .join(PullRequest)
        .where(PullRequest.repository_id == repository.id)
    )).scalar() or 0

    avg_complexity = (await db.execute(
        select(func.avg(CodeMetrics.cyclomatic_complexity))
        .join(ReviewResult)
        .join(PullRequest)
        .where(PullRequest.repository_id == repository.id)
    )).scalar() or 0

    avg_maintainability = (await db.execute(
        select(func.avg(CodeMetrics.maintainability_index))
        .join(ReviewResult)
        .join(PullRequest)
        .where(PullRequest.repository_id == repository.id)
    )).scalar() or 0

    # Quality trend (last 10 reviews)
    trend_query = (
        select(ReviewResult.quality_score, ReviewResult.created_at)
        .join(PullRequest)
        .where(PullRequest.repository_id == repository.id)
        .order_by(desc(ReviewResult.created_at))
        .limit(10)
    )
    trend_rows = (await db.execute(trend_query)).all()
    quality_trend = [
        {"score": row[0], "date": row[1].isoformat() if row[1] else None}
        for row in reversed(trend_rows)
    ]

    # Severity distribution
    severity_query = (
        select(ReviewComment.severity, func.count())
        .join(ReviewResult)
        .join(PullRequest)
        .where(PullRequest.repository_id == repository.id)
        .group_by(ReviewComment.severity)
    )
    severity_rows = (await db.execute(severity_query)).all()
    severity_distribution = {
        row[0].value if hasattr(row[0], "value") else str(row[0]): row[1]
        for row in severity_rows
    }

    return {
        "repository": {
            "id": repository.id,
            "owner": repository.owner,
            "name": repository.name,
            "full_name": repository.full_name,
            "github_url": repository.github_url,
            "language": repository.language,
            "created_at": repository.created_at.isoformat() if repository.created_at else None,
        },
        "total_prs_analyzed": pr_count,
        "avg_quality_score": round(float(avg_score), 1),
        "total_issues_found": int(total_issues),
        "total_security_issues": int(total_security),
        "avg_complexity": round(float(avg_complexity), 2),
        "avg_maintainability": round(float(avg_maintainability), 2),
        "quality_trend": quality_trend,
        "severity_distribution": severity_distribution,
    }


@router.get("/security-issues")
async def list_security_issues(
    severity: Optional[str] = Query(None),
    vuln_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List all security issues with filters and pagination."""
    query = select(SecurityIssue).order_by(desc(SecurityIssue.created_at))

    if severity:
        query = query.where(SecurityIssue.severity == severity)
    if vuln_type:
        query = query.where(SecurityIssue.vulnerability_type.ilike(f"%{vuln_type}%"))

    count_q = select(func.count()).select_from(SecurityIssue)
    total = (await db.execute(count_q)).scalar() or 0

    offset = (page - 1) * per_page
    results = (await db.execute(query.offset(offset).limit(per_page))).scalars().all()

    return {
        "items": [
            {
                "id": si.id,
                "vulnerability_type": si.vulnerability_type,
                "severity": si.severity.value if hasattr(si.severity, "value") else si.severity,
                "file_path": si.file_path,
                "line_number": si.line_number,
                "description": si.description,
                "remediation": si.remediation,
                "cwe_id": si.cwe_id,
                "owasp_category": si.owasp_category,
                "code_snippet": si.code_snippet,
                "created_at": si.created_at.isoformat() if si.created_at else None,
            }
            for si in results
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page if per_page else 0,
    }
