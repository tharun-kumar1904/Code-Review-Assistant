#!/usr/bin/env python3
"""
validate.py — Pre-submission validation script.

Checks all hackathon requirements before submission:
  1. openenv.yaml exists and is valid
  2. inference.py exists
  3. Dockerfile exists
  4. Required environment variables
  5. reset()/step()/state() work correctly
  6. 3+ tasks with graders
  7. Rewards in [0.0, 1.0]
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure local imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = Path(__file__).parent

PASS = "✅"
FAIL = "❌"
WARN = "⚠️"

results: list[tuple[str, str, str]] = []


def check(name: str, passed: bool, detail: str = "") -> bool:
    status = PASS if passed else FAIL
    results.append((status, name, detail))
    return passed


def main() -> int:
    print("=" * 60)
    print("  Pre-Submission Validation")
    print("=" * 60)
    print()

    all_pass = True

    # ── 1. openenv.yaml ──
    openenv_path = ROOT / "openenv.yaml"
    exists = openenv_path.exists()
    valid_yaml = False
    if exists:
        try:
            import yaml
            with open(openenv_path) as f:
                data = yaml.safe_load(f)
            valid_yaml = isinstance(data, dict) and "name" in data
        except ImportError:
            # yaml not installed, just check existence
            valid_yaml = True
        except Exception as e:
            check("openenv.yaml valid", False, str(e))
            all_pass = False
    all_pass &= check("openenv.yaml exists", exists)
    if exists:
        all_pass &= check("openenv.yaml valid", valid_yaml)

    # ── 2. inference.py ──
    inference_path = ROOT / "inference.py"
    all_pass &= check("inference.py exists", inference_path.exists())
    if inference_path.exists():
        content = inference_path.read_text()
        all_pass &= check("inference.py has [START] log", "[START]" in content)
        all_pass &= check("inference.py has [STEP] log", "[STEP]" in content)
        all_pass &= check("inference.py has [END] log", "[END]" in content)
        all_pass &= check(
            "inference.py uses OpenAI Client",
            "from openai" in content or "import openai" in content,
        )
        all_pass &= check("inference.py reads API_BASE_URL", "API_BASE_URL" in content)
        all_pass &= check("inference.py reads MODEL_NAME", "MODEL_NAME" in content)
        all_pass &= check("inference.py reads HF_TOKEN", "HF_TOKEN" in content)

    # ── 3. Dockerfile ──
    dockerfile_path = ROOT / "Dockerfile"
    all_pass &= check("Dockerfile exists", dockerfile_path.exists())
    if dockerfile_path.exists():
        df_content = dockerfile_path.read_text()
        all_pass &= check("Dockerfile exposes port 7860", "7860" in df_content)
        all_pass &= check(
            "Dockerfile serves app",
            "app.py" in df_content or "app:combined_app" in df_content,
        )

    # ── 4. Environment variables ──
    api_base = os.environ.get("API_BASE_URL")
    model_name = os.environ.get("MODEL_NAME")
    hf_token = os.environ.get("HF_TOKEN")
    check("API_BASE_URL set", bool(api_base), api_base or "NOT SET")
    check("MODEL_NAME set", bool(model_name), model_name or "NOT SET")
    check("HF_TOKEN set", bool(hf_token), "(hidden)" if hf_token else "NOT SET")

    # ── 5. Environment reset/step/state ──
    try:
        from environment import CodeReviewEnv
        from schemas import ReviewAction, ReviewIssue, Severity, Category

        env = CodeReviewEnv()

        # reset()
        obs = env.reset(task_id="task_001_null_check")
        all_pass &= check("reset() returns observation", obs is not None and hasattr(obs, "task_id"))

        # step()
        action = ReviewAction(
            issues=[
                ReviewIssue(
                    file="app.py",
                    line=15,
                    severity=Severity.HIGH,
                    category=Category.BUG,
                    description="Missing null check on user object",
                    suggested_fix="Add if user is None check",
                )
            ],
            summary="Found a null reference bug.",
            approve=False,
        )
        obs_out, reward, done, info = env.step(action)
        all_pass &= check("step() returns tuple", done is True)
        all_pass &= check("step() reward in [0,1]", 0.0 <= reward <= 1.0, f"reward={reward:.4f}")
        all_pass &= check("step() info has grade_result", "grade_result" in info)

        # state()
        state = env.state()
        all_pass &= check("state() returns EnvironmentState", hasattr(state, "episode_id"))

    except Exception as e:
        all_pass = False
        check("Environment endpoints work", False, str(e))

    # ── 6. Tasks ──
    tasks_dir = ROOT / "tasks"
    if tasks_dir.exists():
        task_files = list(tasks_dir.glob("*.json"))
        n_tasks = len(task_files)
        all_pass &= check("3+ tasks exist", n_tasks >= 3, f"found {n_tasks} tasks")
    else:
        all_pass &= check("tasks/ directory exists", False)

    # ── 7. Grader produces valid rewards ──
    try:
        from environment import CodeReviewEnv
        from schemas import ReviewAction

        env2 = CodeReviewEnv()
        sample_tasks = env2.task_ids[:3]
        grader_ok = True
        for tid in sample_tasks:
            obs = env2.reset(task_id=tid)
            action = ReviewAction(issues=[], summary="No issues.", approve=True)
            _, r, _, _ = env2.step(action)
            if not (0.0 <= r <= 1.0):
                grader_ok = False
                break
        all_pass &= check("Grader rewards in [0.0, 1.0]", grader_ok)
    except Exception as e:
        all_pass &= check("Grader validation", False, str(e))

    # ── 8. Requirements check ──
    req_path = ROOT / "requirements.txt"
    if req_path.exists():
        req_content = req_path.read_text().lower()
        check("No heavy torch dep", "torch" not in req_content, "torch found — may exceed 8GB")

    # ── Print results ──
    print()
    print("-" * 60)
    for status, name, detail in results:
        line = f"  {status}  {name}"
        if detail:
            line += f"  ({detail})"
        print(line)
    print("-" * 60)

    passed = sum(1 for s, _, _ in results if s == PASS)
    total = len(results)
    print(f"\n  Result: {passed}/{total} checks passed\n")

    if all_pass:
        print("  🎉 All critical checks passed! Ready for submission.\n")
        return 0
    else:
        print("  ⚠️  Some checks failed. Please fix before submitting.\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
