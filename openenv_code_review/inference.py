#!/usr/bin/env python3
"""
inference.py — Hackathon submission inference script.

Runs the Code Review Agent across all tasks, emitting structured stdout logs
in the required [START], [STEP], [END] format.

Required environment variables:
  API_BASE_URL   — The API endpoint for the LLM
  MODEL_NAME     — The model identifier to use
  HF_TOKEN       — Your Hugging Face / API key

Usage:
  python inference.py
  python inference.py --task task_001_null_check   # single task
  python inference.py --dry-run                    # skip LLM, use DemoAgent
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ── Path setup — must happen before any local imports ─────────
_HERE = Path(__file__).parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

# Load .env before importing anything that reads env vars
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv is optional; env vars may be set externally

# ── Robust local imports ──────────────────────────────────────
try:
    from openenv_code_review.environment import CodeReviewEnv
    from openenv_code_review.agent import ReviewAgent, DemoAgent
    from openenv_code_review.schemas import ReviewAction
except ImportError:
    from environment import CodeReviewEnv   # type: ignore[no-redef]
    from agent import ReviewAgent, DemoAgent  # type: ignore[no-redef]
    from schemas import ReviewAction        # type: ignore[no-redef]


# ── Structured log emitters ───────────────────────────────────

def _ts() -> str:
    """ISO-8601 UTC timestamp."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _emit(tag: str, payload: dict) -> None:
    """Write a single tagged JSON line to stdout, flushed immediately."""
    print(f"[{tag}] {json.dumps(payload, default=str)}", flush=True)


def emit_start(run_id: str, total_tasks: int, model_name: str) -> None:
    _emit("START", {
        "run_id":      run_id,
        "timestamp":   _ts(),
        "total_tasks": total_tasks,
        "model_name":  model_name,
        "status":      "started",
    })


def emit_step(
    run_id:       str,
    step_index:   int,
    task_id:      str,
    reward:       float,
    issues_found: int,
    duration_s:   float,
    info:         dict,
    error:        str | None = None,
) -> None:
    payload: dict = {
        "run_id":           run_id,
        "timestamp":        _ts(),
        "step":             step_index,
        "task_id":          task_id,
        "duration_seconds": round(duration_s, 2),
    }
    if error:
        payload["error"]  = error
        payload["status"] = "error"
    else:
        payload["reward"]          = round(reward, 4)
        payload["issues_found"]    = issues_found
        payload["status"]          = "ok"
        # BUG FIX: original used info.get("grade_result", {}).get("breakdown", {})
        # which silently returns {} when grade_result is missing (e.g. on error),
        # making the log look like a successful but empty step. Now only included
        # when present.
        grade = info.get("grade_result")
        if grade:
            payload["grade_breakdown"] = grade.get("breakdown", {})
            payload["base_reward"]     = round(info.get("base_reward", reward), 4)
    _emit("STEP", payload)


def emit_end(
    run_id:           str,
    total_tasks:      int,
    completed:        int,
    failed:           int,
    total_reward:     float,
    avg_reward:       float,
    total_duration_s: float,
) -> None:
    _emit("END", {
        "run_id":                 run_id,
        "timestamp":              _ts(),
        "total_tasks":            total_tasks,
        "completed":              completed,
        "failed":                 failed,
        "total_reward":           round(total_reward, 4),
        "average_reward":         round(avg_reward, 4),
        "total_duration_seconds": round(total_duration_s, 2),
        # BUG FIX: original always emitted status="completed" even when tasks
        # failed. Now reflects actual outcome.
        "status": "completed" if failed == 0 else "completed_with_errors",
    })


# ── Main ──────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--task",
        default=None,
        help="Run a single task by ID instead of all tasks.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Use DemoAgent (no API key required) for smoke-testing.",
    )
    args = parser.parse_args()

    # ── Resolve execution mode ────────────────────────────────
    api_base_url = os.environ.get("API_BASE_URL", "")
    model_name   = os.environ.get("MODEL_NAME", "")
    hf_token     = os.environ.get("HF_TOKEN", "")

    # Automatically fall back to DemoAgent if credentials are missing
    has_credentials = bool(api_base_url or hf_token)
    if not args.dry_run and not has_credentials:
        print("WARNING: Missing API keys. Automatically falling back to dry-run mode (DemoAgent).", file=sys.stderr)
        args.dry_run = True

    # ── Initialize environment & agent ────────────────────────
    env = CodeReviewEnv()

    if args.dry_run:
        agent = DemoAgent()
        model_name = "demo-agent"
        print("INFO: dry-run mode — using DemoAgent (no API calls).", file=sys.stderr)
    else:
        agent = ReviewAgent(
            api_key=hf_token,
            model=model_name,
            base_url=api_base_url,
        )

    # ── Resolve task list ─────────────────────────────────────
    if args.task:
        if args.task not in env.task_ids:
            print(
                f"ERROR: task '{args.task}' not found. "
                f"Available: {env.task_ids}",
                file=sys.stderr,
            )
            sys.exit(1)
        task_ids = [args.task]
    else:
        task_ids = env.task_ids

    if not task_ids:
        print(
            "ERROR: No tasks found. Make sure tasks/ contains .json files.",
            file=sys.stderr,
        )
        sys.exit(1)

    total_tasks  = len(task_ids)
    run_id       = f"run_{int(time.time())}"
    overall_start = time.time()

    emit_start(run_id, total_tasks, model_name)

    total_reward = 0.0
    completed    = 0
    failed       = 0

    for step_index, task_id in enumerate(task_ids, start=1):
        step_start = time.time()

        try:
            obs             = env.reset(task_id=task_id)
            action: ReviewAction = agent.review(obs)
            _, reward, _, info   = env.step(action)

            total_reward += reward
            completed    += 1
            duration      = time.time() - step_start

            emit_step(
                run_id=run_id,
                step_index=step_index,
                task_id=task_id,
                reward=reward,
                issues_found=len(action.issues),
                duration_s=duration,
                info=info,
            )

        except Exception as exc:
            failed   += 1
            duration  = time.time() - step_start
            # Print traceback to stderr so stdout stays clean/parseable
            import traceback
            traceback.print_exc(file=sys.stderr)
            emit_step(
                run_id=run_id,
                step_index=step_index,
                task_id=task_id,
                reward=0.01,
                issues_found=0,
                duration_s=duration,
                info={},
                error=str(exc),
            )

    total_duration = time.time() - overall_start
    # BUG FIX: original divided by total_tasks even when all tasks failed,
    # giving avg_reward=0.0 silently. Now divides by completed only.
    avg_reward = total_reward / completed if completed > 0 else 0.01

    emit_end(
        run_id=run_id,
        total_tasks=total_tasks,
        completed=completed,
        failed=failed,
        total_reward=total_reward,
        avg_reward=avg_reward,
        total_duration_s=total_duration,
    )

    # Exit with non-zero code if any task failed — useful for CI
    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()