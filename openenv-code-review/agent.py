"""
LLM-based Code Review Agent.

Uses OpenAI API (or compatible) with structured JSON output
to produce review actions from observations.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from schemas import (
    Category,
    ReviewAction,
    ReviewIssue,
    ReviewObservation,
    Severity,
)

# ────────────────────── Prompt Templates ───────────────────────

SYSTEM_PROMPT = """You are an expert code reviewer specializing in Python, with deep knowledge of:
- Common bugs (null references, off-by-one, race conditions, type errors)
- Security vulnerabilities (SQL injection, XSS, secrets exposure, path traversal)
- Performance issues (N+1 queries, unnecessary copies, blocking I/O)
- PyTorch/ML specific issues (tensor shape mismatches, device placement, gradient bugs)
- Code quality and best practices

You review pull request diffs and produce structured JSON feedback.

RULES:
1. Only report REAL issues you are confident about. Do NOT hallucinate issues.
2. If the code looks correct, return an empty issues list — do NOT invent problems.
3. For each issue, provide: file, line number, severity, category, clear description, and a suggested fix.
4. Severity levels: critical (crashes/data loss), high (bugs/security), medium (logic issues), low (minor improvements), info (style/nits).
5. Categories: bug, security, performance, style, logic, error_handling.
6. Include a confidence score (0.0-1.0) for each issue.
7. Write a concise summary paragraph covering the overall review.

OUTPUT FORMAT (strict JSON):
{
  "issues": [
    {
      "file": "filename.py",
      "line": 15,
      "severity": "high",
      "category": "bug",
      "description": "Clear description of what the issue is",
      "suggested_fix": "How to fix it (code snippet if applicable)",
      "confidence": 0.9
    }
  ],
  "summary": "One paragraph summarizing the review findings.",
  "approve": true/false
}"""

USER_PROMPT_TEMPLATE = """Review this pull request diff.

**PR Description**: {pr_description}
**Language**: {language}

**Diff**:
```
{diff}
```

{context_section}

Analyze the diff carefully. Report only genuine issues. If the code is clean, return empty issues list.
Respond with valid JSON only."""


# ────────────────────── Agent Class ────────────────────────────

class ReviewAgent:
    """
    LLM-based code review agent.

    Supports OpenAI API and compatible providers.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.model = model or os.environ.get("OPENAI_MODEL", "gpt-4o")
        self.base_url = base_url or os.environ.get("OPENAI_BASE_URL")
        self._client = None

    def _get_client(self):
        """Lazy-initialize the OpenAI client."""
        if self._client is None:
            try:
                from openai import OpenAI
                kwargs: dict[str, Any] = {"api_key": self.api_key}
                if self.base_url:
                    kwargs["base_url"] = self.base_url
                self._client = OpenAI(**kwargs)
            except ImportError:
                raise ImportError(
                    "openai package required. Install with: pip install openai"
                )
        return self._client

    def review(self, observation: ReviewObservation) -> ReviewAction:
        """
        Review a PR diff and return structured feedback.

        Args:
            observation: The environment observation containing the diff.

        Returns:
            ReviewAction with detected issues and summary.
        """
        # Build prompt
        context_section = ""
        if observation.file_context:
            context_section = (
                f"**Full File Context** (for reference):\n"
                f"```{observation.language}\n{observation.file_context}\n```"
            )

        user_prompt = USER_PROMPT_TEMPLATE.format(
            pr_description=observation.pr_description,
            language=observation.language,
            diff=observation.diff,
            context_section=context_section,
        )

        # Call LLM
        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=2000,
            )
            raw = response.choices[0].message.content or "{}"
        except Exception as e:
            # Fallback: return empty review on API error
            return ReviewAction(
                issues=[],
                summary=f"Review failed due to API error: {str(e)}",
                approve=True,
            )

        # Parse response
        return self._parse_response(raw)

    def _parse_response(self, raw: str) -> ReviewAction:
        """Parse LLM JSON response into ReviewAction."""
        try:
            # Try direct JSON parse
            data = json.loads(raw)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code block
            json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    return ReviewAction(
                        issues=[],
                        summary="Failed to parse LLM response.",
                        approve=True,
                    )
            else:
                return ReviewAction(
                    issues=[],
                    summary="Failed to parse LLM response.",
                    approve=True,
                )

        # Build ReviewAction from parsed data
        issues = []
        for item in data.get("issues", []):
            try:
                issue = ReviewIssue(
                    file=str(item.get("file", "unknown")),
                    line=int(item.get("line", 0)),
                    severity=Severity(item.get("severity", "info")),
                    category=Category(item.get("category", "bug")),
                    description=str(item.get("description", "")),
                    suggested_fix=item.get("suggested_fix"),
                    confidence=float(item.get("confidence", 0.8)),
                )
                issues.append(issue)
            except (ValueError, KeyError):
                continue  # Skip malformed issues

        return ReviewAction(
            issues=issues,
            summary=str(data.get("summary", "")),
            approve=bool(data.get("approve", True)),
        )


# ────────────────── Deterministic Demo Agent ───────────────────

class DemoAgent:
    """
    A deterministic agent for testing/demo WITHOUT needing an API key.
    Returns canned responses for known task IDs.
    """

    # Pre-defined reviews for each test task
    _REVIEWS: dict[str, dict[str, Any]] = {
        "task_001_null_check": {
            "issues": [
                {
                    "file": "app.py",
                    "line": 15,
                    "severity": "high",
                    "category": "bug",
                    "description": "Missing null check on user object. If `get_user(user_id)` returns None, accessing `user.name` will raise an AttributeError. This is a common NoneType error pattern.",
                    "suggested_fix": "Add a null check: `if user is None: return {'error': 'User not found'}, 404`",
                    "confidence": 0.95,
                }
            ],
            "summary": "This PR adds a user profile endpoint but has a critical null reference bug. The `get_user()` call may return None if the user doesn't exist, and the code does not guard against this. This will cause a NoneType AttributeError at runtime.",
            "approve": False,
        },
        "task_002_sql_inject": {
            "issues": [
                {
                    "file": "db.py",
                    "line": 23,
                    "severity": "critical",
                    "category": "security",
                    "description": "SQL injection vulnerability: user input is directly interpolated into SQL query string via f-string formatting. An attacker can inject arbitrary SQL by providing malicious input in the `username` parameter.",
                    "suggested_fix": "Use parameterized queries: `cursor.execute('SELECT * FROM users WHERE username = %s', (username,))`",
                    "confidence": 0.98,
                }
            ],
            "summary": "Critical security issue: the search endpoint constructs SQL queries by directly embedding user input using f-strings. This is a textbook SQL injection vulnerability that must be fixed before merging. Use parameterized queries instead.",
            "approve": False,
        },
        "task_003_off_by_one": {
            "issues": [
                {
                    "file": "processor.py",
                    "line": 34,
                    "severity": "high",
                    "category": "bug",
                    "description": "Off-by-one error in the batch processing loop. Using `range(1, len(items))` skips the first element (index 0) of the list, so item[0] is never processed.",
                    "suggested_fix": "Change to `range(len(items))` or `range(0, len(items))` to include the first element.",
                    "confidence": 0.92,
                },
                {
                    "file": "processor.py",
                    "line": 42,
                    "severity": "medium",
                    "category": "error_handling",
                    "description": "Bare except clause catches all exceptions including SystemExit and KeyboardInterrupt. This makes debugging difficult and can mask real errors.",
                    "suggested_fix": "Use `except Exception as e:` instead of bare `except:` and log the error.",
                    "confidence": 0.88,
                },
            ],
            "summary": "Two issues found: (1) An off-by-one error in the batch loop that skips the first item, and (2) a bare except clause that silently swallows all exceptions. Both should be fixed before merging.",
            "approve": False,
        },
        "task_004_tensor_shape": {
            "issues": [
                {
                    "file": "model.py",
                    "line": 28,
                    "severity": "critical",
                    "category": "bug",
                    "description": "Tensor shape mismatch: the linear layer expects input of size 512 but the preceding conv layer outputs 256 features. This will cause a RuntimeError at forward pass.",
                    "suggested_fix": "Change `nn.Linear(512, 128)` to `nn.Linear(256, 128)` to match the conv output, or adjust the conv layer.",
                    "confidence": 0.93,
                },
                {
                    "file": "model.py",
                    "line": 45,
                    "severity": "high",
                    "category": "bug",
                    "description": "Device placement issue: the new tensor is created on CPU while the model may be on GPU. This will cause a RuntimeError when the tensors interact.",
                    "suggested_fix": "Use `torch.zeros(batch_size, 10, device=x.device)` to match the input tensor's device.",
                    "confidence": 0.90,
                },
            ],
            "summary": "Two PyTorch-specific bugs found: (1) A tensor shape mismatch between conv and linear layers that will crash during forward pass, and (2) a device placement issue where a new tensor defaults to CPU while the model runs on GPU. Both are runtime-breaking bugs.",
            "approve": False,
        },
        "task_005_clean_pr": {
            "issues": [],
            "summary": "This PR correctly implements the configuration loading utility. The code is well-structured, handles edge cases appropriately with proper error handling, and follows Python best practices. No issues found.",
            "approve": True,
        },
    }

    def review(self, observation: ReviewObservation) -> ReviewAction:
        """Return a pre-defined review for known tasks, or empty for unknown."""
        canned = self._REVIEWS.get(observation.task_id)
        if canned is None:
            return ReviewAction(
                issues=[],
                summary="No pre-defined review available for this task.",
                approve=True,
            )

        issues = []
        for item in canned["issues"]:
            issues.append(
                ReviewIssue(
                    file=item["file"],
                    line=item["line"],
                    severity=Severity(item["severity"]),
                    category=Category(item["category"]),
                    description=item["description"],
                    suggested_fix=item.get("suggested_fix"),
                    confidence=item.get("confidence", 0.9),
                )
            )

        return ReviewAction(
            issues=issues,
            summary=canned["summary"],
            approve=canned["approve"],
        )
