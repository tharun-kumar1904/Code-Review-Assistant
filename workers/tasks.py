"""
Celery tasks for asynchronous PR analysis.
"""

import asyncio
from workers.celery_app import celery


@celery.task(
    name="workers.tasks.analyze_pull_request_task",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def analyze_pull_request_task(self, owner: str, repo: str, pr_number: int):
    """
    Async Celery task that runs the full analysis pipeline.
    Wraps the async AnalysisEngine in a sync Celery task.
    """
    try:
        self.update_state(state="ANALYZING", meta={
            "owner": owner,
            "repo": repo,
            "pr_number": pr_number,
        })

        # Run async analysis in event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            from services.analysis_engine import AnalysisEngine
            engine = AnalysisEngine()
            result = loop.run_until_complete(
                engine.analyze(owner, repo, pr_number)
            )
        finally:
            loop.close()

        return {
            "status": "completed",
            "review_id": result.get("review_id"),
            "quality_score": result.get("quality_score"),
            "total_issues": result.get("total_issues"),
            "duration": result.get("duration"),
        }

    except Exception as exc:
        self.update_state(state="FAILED", meta={"error": str(exc)})
        raise self.retry(exc=exc)
