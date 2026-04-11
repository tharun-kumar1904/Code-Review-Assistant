#!/usr/bin/env python3
"""
read_stats.py — Parse and display summary stats from an inference log.

Reads the [END] line (and optionally all [STEP] lines) from a structured
inference log produced by inference.py.

Usage:
    python read_stats.py                          # reads inference_out.txt
    python read_stats.py --file my_run.txt        # custom log file
    python read_stats.py --steps                  # also show per-task breakdown
    python read_stats.py --json                   # emit raw JSON to stdout
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


# ── Encoding detection ────────────────────────────────────────

def _read_lines(path: Path) -> list[str]:
    """
    Read lines from a log file, auto-detecting encoding.

    BUG FIX 1: original hardcoded utf-16le which works on Windows systems
    that pipe stdout with that encoding, but fails on Linux/Mac (HF Spaces
    uses Linux) where stdout is utf-8. We try utf-8 first, then fall back
    to utf-16le, then latin-1 (which never errors).
    """
    for encoding in ("utf-8", "utf-16", "utf-16-le", "utf-16-be", "latin-1"):
        try:
            text = path.read_text(encoding=encoding)
            # Quick sanity check — valid log files contain "[END]"
            if "[END]" in text or "[STEP]" in text or "[START]" in text:
                return text.splitlines()
        except (UnicodeDecodeError, UnicodeError):
            continue
    # Last resort: read as bytes and decode with replacement
    raw = path.read_bytes()
    return raw.decode("utf-8", errors="replace").splitlines()


# ── Line parsers ──────────────────────────────────────────────

def _parse_tagged_line(line: str, tag: str) -> dict | None:
    """
    Extract JSON payload from a line like '[TAG] {...}'.

    BUG FIX 2: original used line.split('[END] ')[1] which breaks when the
    line has leading whitespace, a BOM, or the tag appears more than once
    in the JSON payload itself. Use find() on the tag boundary instead.
    """
    marker = f"[{tag}] "
    idx = line.find(marker)
    if idx == -1:
        return None
    json_str = line[idx + len(marker):].strip()
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return None


def _extract_all(lines: list[str], tag: str) -> list[dict]:
    results = []
    for line in lines:
        parsed = _parse_tagged_line(line, tag)
        if parsed is not None:
            results.append(parsed)
    return results


# ── Display helpers ───────────────────────────────────────────

def _bar(value: float, width: int = 24) -> str:
    """Simple ASCII progress bar for a 0–1 float."""
    filled = round(value * width)
    return "█" * filled + "░" * (width - filled)


def _fmt_reward(r: float) -> str:
    if r >= 0.8:
        return f"{r:.4f} ✓ excellent"
    if r >= 0.6:
        return f"{r:.4f} ✓ good"
    if r >= 0.3:
        return f"{r:.4f} △ needs work"
    return f"{r:.4f} ✗ poor"


def print_summary(end_data: dict, step_data: list[dict], show_steps: bool) -> None:
    """Print a formatted summary to stdout."""
    w = 52
    print("=" * w)
    print("  INFERENCE RUN SUMMARY")
    print("=" * w)

    run_id = end_data.get("run_id", "—")
    status = end_data.get("status", "—")
    print(f"  Run ID   : {run_id}")
    print(f"  Status   : {status}")
    print(f"  Timestamp: {end_data.get('timestamp', '—')}")
    print("-" * w)

    total   = end_data.get("total_tasks", 0)
    done    = end_data.get("completed", total)   # backward compat
    failed  = end_data.get("failed", 0)
    t_rew   = end_data.get("total_reward", 0.0)
    avg_rew = end_data.get("average_reward", 0.0)
    dur     = end_data.get("total_duration_seconds", 0.0)

    print(f"  Tasks    : {done}/{total} completed  ({failed} failed)")
    print(f"  Duration : {dur:.2f}s  ({dur/total:.2f}s avg)" if total else f"  Duration : {dur:.2f}s")
    print(f"  Total Rwd: {t_rew:.4f}")
    print(f"  Avg Rwd  : {_fmt_reward(avg_rew)}")
    print(f"  Progress : {_bar(avg_rew)}")

    # ── Per-step breakdown ────────────────────────────────────
    if show_steps and step_data:
        print("-" * w)
        print(f"  {'#':<4} {'Task ID':<34} {'Reward':>7} {'Issues':>6}")
        print(f"  {'-'*4} {'-'*34} {'-'*7} {'-'*6}")
        for s in step_data:
            idx     = s.get("step", "?")
            tid     = s.get("task_id", "?")[:33]
            err     = s.get("error")
            if err:
                print(f"  {idx:<4} {tid:<34} {'ERROR':>7}  {str(err)[:20]}")
            else:
                rew    = s.get("reward", 0.0)
                issues = s.get("issues_found", 0)
                bar    = "▪" * min(issues, 6)
                print(f"  {idx:<4} {tid:<34} {rew:>7.4f} {issues:>5}  {bar}")

        # Breakdown averages if available
        bd_keys = ["recall","precision","severity_accuracy","feedback_quality","summary_quality"]
        bd_sums: dict[str, float] = {k: 0.0 for k in bd_keys}
        bd_count = 0
        for s in step_data:
            bd = s.get("grade_breakdown", {})
            if bd:
                for k in bd_keys:
                    bd_sums[k] += bd.get(k, 0.0)
                bd_count += 1
        if bd_count:
            print("-" * w)
            print("  GRADE BREAKDOWN (averages across graded tasks)")
            print("-" * w)
            labels = {
                "recall":            "Recall          (35%)",
                "precision":         "Precision       (15%)",
                "severity_accuracy": "Severity Acc.   (20%)",
                "feedback_quality":  "Feedback        (20%)",
                "summary_quality":   "Summary         (10%)",
            }
            for k in bd_keys:
                avg = bd_sums[k] / bd_count
                print(f"  {labels[k]}: {avg:.4f}  {_bar(avg, 20)}")

    print("=" * w)


# ── Main ──────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--file", "-f",
        default="inference_out.txt",
        help="Path to the inference log file (default: inference_out.txt)",
    )
    parser.add_argument(
        "--steps",
        action="store_true",
        help="Show per-task step breakdown",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the raw [END] JSON to stdout and exit",
    )
    args = parser.parse_args()

    log_path = Path(args.file)
    if not log_path.exists():
        print(f"ERROR: log file not found: {log_path}", file=sys.stderr)
        sys.exit(1)

    lines = _read_lines(log_path)

    # ── BUG FIX 3: original used a list comprehension + [0] which raises
    #    IndexError with no message if [END] is missing (e.g. the run
    #    crashed before completing). Now gives a clear error.
    end_lines = _extract_all(lines, "END")
    if not end_lines:
        print(
            "ERROR: no [END] line found in the log file.\n"
            "The inference run may have crashed before completing.\n"
            "Check the log for [STEP] error entries.",
            file=sys.stderr,
        )
        # Still try to show whatever step data we have
        step_data = _extract_all(lines, "STEP")
        if step_data:
            print(f"\nFound {len(step_data)} [STEP] line(s) — partial results:", file=sys.stderr)
            for s in step_data:
                print(f"  step {s.get('step','?')} {s.get('task_id','?')} "
                      f"reward={s.get('reward','?')} error={s.get('error','')}", file=sys.stderr)
        sys.exit(1)

    # Use the last [END] line (in case of multiple runs concatenated)
    end_data  = end_lines[-1]
    step_data = _extract_all(lines, "STEP")

    if args.json:
        print(json.dumps(end_data, indent=2))
        return

    print_summary(end_data, step_data, show_steps=args.steps)


if __name__ == "__main__":
    main()