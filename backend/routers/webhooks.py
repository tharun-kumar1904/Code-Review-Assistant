"""
Webhooks router — GitHub webhook handler.
"""

from fastapi import APIRouter, Request, HTTPException, Header
from typing import Optional
import hashlib
import hmac
import json
from config import get_settings

settings = get_settings()
router = APIRouter()


def verify_github_signature(payload_body: bytes, signature: str, secret: str) -> bool:
    """Verify the GitHub webhook signature (HMAC-SHA256)."""
    if not secret:
        return True  # Skip verification if no secret configured
    expected = "sha256=" + hmac.new(
        secret.encode("utf-8"),
        payload_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/webhook/github")
async def github_webhook(
    request: Request,
    x_hub_signature_256: Optional[str] = Header(None),
    x_github_event: Optional[str] = Header(None),
):
    """
    Handle GitHub webhook events.
    Auto-triggers PR analysis on pull_request opened/synchronize events.
    """
    body = await request.body()

    # Verify signature
    if settings.GITHUB_WEBHOOK_SECRET and x_hub_signature_256:
        if not verify_github_signature(body, x_hub_signature_256, settings.GITHUB_WEBHOOK_SECRET):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

    payload = json.loads(body)

    # Handle ping event
    if x_github_event == "ping":
        return {"status": "pong", "zen": payload.get("zen", "")}

    # Handle pull_request events
    if x_github_event == "pull_request":
        action = payload.get("action", "")

        if action in ("opened", "synchronize", "reopened"):
            pr = payload.get("pull_request", {})
            repo = payload.get("repository", {})

            repo_owner = repo.get("owner", {}).get("login", "")
            repo_name = repo.get("name", "")
            pr_number = pr.get("number", 0)

            if not all([repo_owner, repo_name, pr_number]):
                raise HTTPException(status_code=400, detail="Missing required PR data")

            # Enqueue async analysis
            try:
                from workers.tasks import analyze_pull_request_task
                task = analyze_pull_request_task.apply_async(
                    args=[repo_owner, repo_name, pr_number],
                )
                return {
                    "status": "analysis_queued",
                    "task_id": task.id,
                    "pr": f"{repo_owner}/{repo_name}#{pr_number}",
                }
            except Exception as e:
                return {
                    "status": "queued_with_fallback",
                    "message": f"Celery unavailable, will process later: {str(e)}",
                    "pr": f"{repo_owner}/{repo_name}#{pr_number}",
                }

        return {"status": "ignored", "action": action}

    return {"status": "ignored", "event": x_github_event}
