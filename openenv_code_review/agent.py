"""
LLM-based Code Review Agent.

Uses OpenAI API (or compatible) with structured JSON output
to produce review actions from observations.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

# ── Robust import resolution ──────────────────────────────────
# agent.py may be loaded via the app.py hyphenated-folder shim
# (as openenv_code_review.agent) or run directly. Both must work.
_HERE = Path(__file__).parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

try:
    from openenv_code_review.schemas import (
        Category,
        ReviewAction,
        ReviewIssue,
        ReviewObservation,
        Severity,
    )
except ImportError:
    from schemas import (  # type: ignore[no-redef]
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
    """LLM-based code review agent. Supports OpenAI API and compatible providers."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ):
        self.api_key = (
            api_key
            or os.environ.get("HF_TOKEN", "")
            or os.environ.get("OPENAI_API_KEY", "")
        )
        self.model = (
            model
            or os.environ.get("MODEL_NAME", "")
            or os.environ.get("OPENAI_MODEL", "gpt-4o")
        )
        self.base_url = (
            base_url
            or os.environ.get("API_BASE_URL", "")
            or os.environ.get("OPENAI_BASE_URL")
        )
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from openai import OpenAI
                kwargs: dict[str, Any] = {"api_key": self.api_key}
                if self.base_url:
                    kwargs["base_url"] = self.base_url
                self._client = OpenAI(**kwargs)
            except ImportError:
                raise ImportError("openai package required: pip install openai")
        return self._client

    def review(self, observation: ReviewObservation) -> ReviewAction:
        context_section = ""
        if observation.file_context:
            context_section = (
                f"**Full File Context**:\n"
                f"```{observation.language}\n{observation.file_context}\n```"
            )

        user_prompt = USER_PROMPT_TEMPLATE.format(
            pr_description=observation.pr_description,
            language=observation.language,
            diff=observation.diff,
            context_section=context_section,
        )

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
            return ReviewAction(
                issues=[],
                summary=f"Review failed due to API error: {e}",
                approve=True,
            )

        return self._parse_response(raw)

    def _parse_response(self, raw: str) -> ReviewAction:
        try:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
                if match:
                    try:
                        data = json.loads(match.group(1))
                    except json.JSONDecodeError:
                        return ReviewAction(issues=[], summary="Failed to parse LLM response.", approve=True)
                else:
                    return ReviewAction(issues=[], summary="Failed to parse LLM response.", approve=True)

            if not isinstance(data, dict):
                data = {}

            issues = []
            for item in data.get("issues", []):
                try:
                    if not isinstance(item, dict):
                        continue
                    issues.append(ReviewIssue(
                        file=str(item.get("file", "unknown")),
                        line=int(item.get("line", 0)),
                        severity=Severity(item.get("severity", "info")),
                        category=Category(item.get("category", "bug")),
                        description=str(item.get("description", "")),
                        suggested_fix=item.get("suggested_fix"),
                        confidence=float(item.get("confidence", 0.8)),
                    ))
                except (ValueError, KeyError, TypeError):
                    continue

            return ReviewAction(
                issues=issues,
                summary=str(data.get("summary", "")),
                approve=bool(data.get("approve", True)),
            )
        except Exception as e:
            return ReviewAction(issues=[], summary=f"Unexpected parsing error: {e}", approve=True)


# ────────────────── Deterministic Demo Agent ───────────────────

class DemoAgent:
    """
    Deterministic agent for demo/testing — no API key required.
    Returns pre-defined reviews for each built-in task ID.
    """

    _REVIEWS: dict[str, dict[str, Any]] = {
        "task_001_null_check": {
            "issues": [{
                "file": "app.py", "line": 15, "severity": "high", "category": "bug",
                "description": "Missing null check on user object. If `get_user(user_id)` returns None, accessing `user.name` raises AttributeError.",
                "suggested_fix": "Add: `if user is None: return {'error': 'User not found'}, 404`",
                "confidence": 0.95,
            }],
            "summary": "Critical null reference bug: `get_user()` may return None and the code does not guard against it.",
            "approve": False,
        },
        "task_002_sql_inject": {
            "issues": [{
                "file": "db.py", "line": 23, "severity": "critical", "category": "security",
                "description": "SQL injection: user input is directly interpolated into SQL via f-string.",
                "suggested_fix": "Use parameterized queries: `cursor.execute('SELECT * FROM users WHERE username = %s', (username,))`",
                "confidence": 0.98,
            }],
            "summary": "Critical SQL injection vulnerability. Use parameterized queries before merging.",
            "approve": False,
        },
        "task_003_off_by_one": {
            "issues": [
                {
                    "file": "processor.py", "line": 34, "severity": "high", "category": "bug",
                    "description": "`range(1, len(items))` skips index 0 — the first item is never processed.",
                    "suggested_fix": "Change to `range(len(items))`.",
                    "confidence": 0.92,
                },
                {
                    "file": "processor.py", "line": 42, "severity": "medium", "category": "error_handling",
                    "description": "Bare except catches SystemExit and KeyboardInterrupt, masking real errors.",
                    "suggested_fix": "Use `except Exception as e:` and log the error.",
                    "confidence": 0.88,
                },
            ],
            "summary": "Off-by-one skips first item; bare except swallows all errors.",
            "approve": False,
        },
        "task_004_tensor_shape": {
            "issues": [
                {
                    "file": "model.py", "line": 28, "severity": "critical", "category": "bug",
                    "description": "Linear layer expects 512 features but conv outputs 256. RuntimeError on forward pass.",
                    "suggested_fix": "Change `nn.Linear(512, 128)` to `nn.Linear(256, 128)`.",
                    "confidence": 0.93,
                },
                {
                    "file": "model.py", "line": 45, "severity": "high", "category": "bug",
                    "description": "New tensor created on CPU while model may be on GPU.",
                    "suggested_fix": "Use `torch.zeros(batch_size, 10, device=x.device)`.",
                    "confidence": 0.90,
                },
            ],
            "summary": "Tensor shape mismatch and CPU/GPU device mismatch — both crash at runtime.",
            "approve": False,
        },
        "task_005_clean_pr": {
            "issues": [],
            "summary": "Clean PR. Well-structured, handles edge cases properly. No issues found.",
            "approve": True,
        },
        "task_006_race_condition": {
            "issues": [{
                "file": "analytics.py", "line": 9, "severity": "high", "category": "bug",
                "description": "Race condition: `request_count += 1` is not atomic in async context.",
                "suggested_fix": "Use `asyncio.Lock` or `threading.Lock`.",
                "confidence": 0.94,
            }],
            "summary": "Unsynchronized counter causes lost updates under concurrent load.",
            "approve": False,
        },
        "task_007_hardcoded_secret": {
            "issues": [
                {
                    "file": "payments.py", "line": 4, "severity": "critical", "category": "security",
                    "description": "Hardcoded Stripe live key (`sk_live_...`) in source code.",
                    "suggested_fix": "Use `os.environ.get('STRIPE_SECRET_KEY')`.",
                    "confidence": 0.99,
                },
                {
                    "file": "payments.py", "line": 21, "severity": "medium", "category": "error_handling",
                    "description": "Bare except silently swallows all exceptions.",
                    "suggested_fix": "Replace with `except Exception as e:` and log.",
                    "confidence": 0.90,
                },
            ],
            "summary": "Critical: live Stripe key hardcoded in source. Move to environment variables immediately.",
            "approve": False,
        },
        "task_008_n_plus_one": {
            "issues": [{
                "file": "views.py", "line": 12, "severity": "high", "category": "performance",
                "description": "N+1 query: one DB query per user to fetch orders. 1000 users = 1001 queries.",
                "suggested_fix": "Use `joinedload(User.orders)` or a single aggregation query.",
                "confidence": 0.95,
            }],
            "summary": "N+1 query will cause severe performance degradation at scale. Use eager loading.",
            "approve": False,
        },
        "task_009_path_traversal": {
            "issues": [{
                "file": "files.py", "line": 11, "severity": "critical", "category": "security",
                "description": "Path traversal: unsanitized `filename` allows reading arbitrary server files.",
                "suggested_fix": "Use `pathlib.Path(filename).name` to strip directory components.",
                "confidence": 0.97,
            }],
            "summary": "Critical path traversal vulnerability — attackers can read arbitrary files.",
            "approve": False,
        },
        "task_010_memory_leak": {
            "issues": [{
                "file": "events.py", "line": 5, "severity": "high", "category": "bug",
                "description": "Unbounded `event_cache` list grows forever, eventually causing OOM crash.",
                "suggested_fix": "Use `collections.deque(maxlen=10000)`.",
                "confidence": 0.93,
            }],
            "summary": "Unbounded cache causes OOM under sustained traffic. Use a deque with maxlen.",
            "approve": False,
        },
        "task_011_type_confusion": {
            "issues": [{
                "file": "pricing.py", "line": 10, "severity": "high", "category": "bug",
                "description": "String parameters used in arithmetic subtraction — raises TypeError at runtime.",
                "suggested_fix": "Cast to float: `base_price = float(base_price)`.",
                "confidence": 0.96,
            }],
            "summary": "String-typed parameters in arithmetic will crash with TypeError. Use float.",
            "approve": False,
        },
        "task_012_clean_refactor": {
            "issues": [],
            "summary": "Clean async context manager refactor with proper commit/rollback. No issues.",
            "approve": True,
        },
        "task_013_xss_vulnerability": {
            "issues": [{
                "file": "templates.py", "line": 10, "severity": "critical", "category": "security",
                "description": "XSS: `username` and `bio` interpolated into HTML without escaping.",
                "suggested_fix": "Use `html.escape()` or Jinja2 auto-escaping.",
                "confidence": 0.97,
            }],
            "summary": "Critical XSS: unescaped user data in HTML allows arbitrary JS execution.",
            "approve": False,
        },
        "task_014_error_swallow": {
            "issues": [
                {
                    "file": "api_client.py", "line": 8, "severity": "medium", "category": "error_handling",
                    "description": "Bare except swallows all exceptions including KeyboardInterrupt. Errors never logged.",
                    "suggested_fix": "Use `except requests.RequestException as e:` and log.",
                    "confidence": 0.91,
                },
                {
                    "file": "api_client.py", "line": 10, "severity": "medium", "category": "bug",
                    "description": "Silent None return after all retries causes NoneType errors in callers.",
                    "suggested_fix": "Raise the last exception after retries are exhausted.",
                    "confidence": 0.88,
                },
            ],
            "summary": "Retry logic hides errors and returns None silently. Both issues hurt production reliability.",
            "approve": False,
        },
        "task_015_clean_logging": {
            "issues": [],
            "summary": "Well-implemented structured JSON logging with timestamps, correlation IDs, and exception formatting. Production-ready.",
            "approve": True,
        },
    }

    def review(self, observation: ReviewObservation) -> ReviewAction:
        canned = self._REVIEWS.get(observation.task_id)
        if canned is None:
            return ReviewAction(
                issues=[],
                summary="No pre-defined review available for this task (demo mode).",
                approve=True,
            )

        issues = [
            ReviewIssue(
                file=item["file"],
                line=item["line"],
                severity=Severity(item["severity"]),
                category=Category(item["category"]),
                description=item["description"],
                suggested_fix=item.get("suggested_fix"),
                confidence=item.get("confidence", 0.9),
            )
            for item in canned["issues"]
        ]

        return ReviewAction(
            issues=issues,
            summary=canned["summary"],
            approve=canned["approve"],
        )