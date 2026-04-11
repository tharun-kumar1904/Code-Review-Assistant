"""
Analysis router — PR analysis endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from sqlalchemy.orm import selectinload
from database import get_db
from models import PullRequest, ReviewResult, Repository, PRStatus
from schemas import (
    AnalyzePRRequest, AnalysisTaskResponse,
    ReviewResultResponse,
)
from typing import Optional
import uuid

router = APIRouter()


@router.post("/analyze-pr", response_model=AnalysisTaskResponse)
async def analyze_pull_request(
    request: AnalyzePRRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger asynchronous PR analysis.
    Enqueues a Celery task for the full analysis pipeline.
    """
    # Upsert repository
    repo_query = await db.execute(
        select(Repository).where(
            Repository.owner == request.repo_owner,
            Repository.name == request.repo_name,
        )
    )
    repo = repo_query.scalar_one_or_none()
    if not repo:
        repo = Repository(
            owner=request.repo_owner,
            name=request.repo_name,
            full_name=f"{request.repo_owner}/{request.repo_name}",
            github_url=f"https://github.com/{request.repo_owner}/{request.repo_name}",
        )
        db.add(repo)
        await db.flush()

    # Upsert pull request
    pr_query = await db.execute(
        select(PullRequest).where(
            PullRequest.repository_id == repo.id,
            PullRequest.pr_number == request.pr_number,
        )
    )
    pr = pr_query.scalar_one_or_none()
    if not pr:
        pr = PullRequest(
            pr_number=request.pr_number,
            repository_id=repo.id,
            analysis_status=PRStatus.PENDING,
        )
        db.add(pr)
        await db.flush()

    pr.analysis_status = PRStatus.PENDING
    await db.commit()

    # Enqueue Celery task
    task_id = str(uuid.uuid4())
    try:
        from workers.tasks import analyze_pull_request_task
        analyze_pull_request_task.apply_async(
            args=[request.repo_owner, request.repo_name, request.pr_number],
            task_id=task_id,
        )
    except Exception:
        # Fallback: run synchronously if Celery not available
        from services.analysis_engine import AnalysisEngine
        engine = AnalysisEngine()
        await engine.analyze(request.repo_owner, request.repo_name, request.pr_number)
        task_id = "sync-" + task_id

    return AnalysisTaskResponse(
        task_id=task_id,
        status="queued",
        message=f"Analysis queued for {request.repo_owner}/{request.repo_name}#{request.pr_number}",
    )


@router.get("/review-results")
async def list_review_results(
    repo: Optional[str] = Query(None, description="Filter by repo full_name"),
    severity: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List all review results with pagination and filters."""
    query = (
        select(ReviewResult)
        .options(
            selectinload(ReviewResult.pull_request).selectinload(PullRequest.repository),
            selectinload(ReviewResult.comments),
        )
        .order_by(desc(ReviewResult.created_at))
    )

    if repo:
        query = query.join(ReviewResult.pull_request).join(PullRequest.repository).where(
            Repository.full_name == repo
        )

    # Count total
    count_query = select(func.count()).select_from(ReviewResult)
    total = (await db.execute(count_query)).scalar() or 0

    # Paginate
    offset = (page - 1) * per_page
    results = (await db.execute(query.offset(offset).limit(per_page))).scalars().all()

    return {
        "items": [
            {
                "id": r.id,
                "summary": r.summary,
                "quality_score": r.quality_score,
                "total_issues": r.total_issues,
                "critical_issues": r.critical_issues,
                "high_issues": r.high_issues,
                "medium_issues": r.medium_issues,
                "low_issues": r.low_issues,
                "analysis_duration": r.analysis_duration,
                "llm_provider": r.llm_provider,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "pull_request": {
                    "pr_number": r.pull_request.pr_number,
                    "title": r.pull_request.title,
                    "author": r.pull_request.author,
                    "github_url": r.pull_request.github_url,
                    "repo": r.pull_request.repository.full_name if r.pull_request.repository else None,
                } if r.pull_request else None,
                "comment_count": len(r.comments) if r.comments else 0,
            }
            for r in results
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page if per_page else 0,
    }


@router.get("/review-results/{review_id}", response_model=ReviewResultResponse)
async def get_review_result(
    review_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get detailed review result with all comments."""
    query = (
        select(ReviewResult)
        .options(
            selectinload(ReviewResult.comments),
            selectinload(ReviewResult.security_issues),
            selectinload(ReviewResult.code_metrics),
        )
        .where(ReviewResult.id == review_id)
    )
    result = (await db.execute(query)).scalar_one_or_none()
    if not result:
        raise HTTPException(status_code=404, detail="Review result not found")
    return result
