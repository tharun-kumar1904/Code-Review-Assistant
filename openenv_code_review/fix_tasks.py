#!/usr/bin/env python3
"""
Add / update difficulty levels on all task JSON files.

Run from anywhere — resolves tasks/ relative to this script's location.

Usage:
    python fix_tasks.py                          # update all tasks
    python fix_tasks.py --dry-run                # preview changes, no writes
    python fix_tasks.py --tasks-dir /custom/path # override tasks directory
"""
from __future__ import annotations

import argparse
import json
import os
import sys

# ── Difficulty map ────────────────────────────────────────────
DIFFICULTIES: dict[str, str] = {
    "task_001_null_check":      "easy",
    "task_002_sql_inject":      "easy",
    "task_003_off_by_one":      "medium",
    "task_004_tensor_shape":    "hard",
    "task_005_clean_pr":        "easy",
    "task_006_race_condition":  "medium",
    "task_007_hardcoded_secret":"easy",
    "task_008_n_plus_one":      "medium",
    "task_009_path_traversal":  "medium",
    "task_010_memory_leak":     "medium",
    "task_011_type_confusion":  "easy",
    "task_012_clean_refactor":  "easy",
    "task_013_xss_vulnerability":"medium",
    "task_014_error_swallow":   "hard",
    "task_015_clean_logging":   "easy",
}

VALID_DIFFICULTIES = {"easy", "medium", "hard"}
DEFAULT_DIFFICULTY = "medium"


def process_tasks(tasks_dir: str, dry_run: bool = False) -> int:
    """
    Update all task JSON files with a difficulty field.

    Returns:
        Exit code — 0 on success, 1 if any file failed.
    """
    # ── Validate directory ────────────────────────────────────
    if not os.path.isdir(tasks_dir):
        print(f"ERROR: tasks directory not found: {tasks_dir}", file=sys.stderr)
        print(
            "Make sure tasks/ exists inside your openenv-code-review/ folder.",
            file=sys.stderr,
        )
        return 1

    json_files = sorted(f for f in os.listdir(tasks_dir) if f.endswith(".json"))
    if not json_files:
        print(f"WARNING: no .json files found in {tasks_dir}", file=sys.stderr)
        return 0

    print(f"{'DRY RUN — ' if dry_run else ''}Processing {len(json_files)} task(s) in {tasks_dir}\n")

    errors   = 0
    updated  = 0
    skipped  = 0

    for fname in json_files:
        path = os.path.join(tasks_dir, fname)

        # ── Load ─────────────────────────────────────────────
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"  ERROR  {fname}: invalid JSON — {e}", file=sys.stderr)
            errors += 1
            continue
        except OSError as e:
            print(f"  ERROR  {fname}: cannot read — {e}", file=sys.stderr)
            errors += 1
            continue

        # ── Resolve task_id ───────────────────────────────────
        tid        = data.get("task_id") or fname.removesuffix(".json")
        difficulty = DIFFICULTIES.get(tid, DEFAULT_DIFFICULTY)

        # Warn about unknown task IDs so the map can be kept up to date
        if tid not in DIFFICULTIES:
            print(f"  WARN   {fname}: task_id '{tid}' not in difficulty map — defaulting to '{DEFAULT_DIFFICULTY}'")

        # Skip if already correct (avoid unnecessary writes)
        if data.get("difficulty") == difficulty:
            print(f"  SKIP   {fname} (already '{difficulty}')")
            skipped += 1
            continue

        old = data.get("difficulty", "<missing>")
        data["difficulty"] = difficulty

        # ── Write ─────────────────────────────────────────────
        if not dry_run:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                    f.write("\n")   # POSIX-compliant trailing newline
            except OSError as e:
                print(f"  ERROR  {fname}: cannot write — {e}", file=sys.stderr)
                errors += 1
                continue

        arrow = f"'{old}' → '{difficulty}'"
        tag   = "DRY    " if dry_run else "UPDATE "
        print(f"  {tag}{fname}: {arrow}")
        updated += 1

    # ── Summary ───────────────────────────────────────────────
    print(f"\n{'(dry run) ' if dry_run else ''}Done: {updated} updated, {skipped} skipped, {errors} error(s).")
    return 0 if errors == 0 else 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tasks-dir",
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "tasks"),
        help="Path to the tasks/ directory (default: ./tasks/ next to this script)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing any files",
    )
    args = parser.parse_args()
    sys.exit(process_tasks(args.tasks_dir, dry_run=args.dry_run))


if __name__ == "__main__":
    main()