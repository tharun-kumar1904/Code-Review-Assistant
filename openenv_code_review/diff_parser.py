"""
Unified diff parser — extracts structured hunk data from patch text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class DiffLine:
    """A single line within a diff hunk."""
    number: int       # Line number in the new file (0 if deleted)
    old_number: int   # Line number in the old file (0 if added)
    content: str      # Line content (without the +/-/space prefix)
    kind: str         # "add", "delete", or "context"


@dataclass
class DiffHunk:
    """A contiguous block of changes within a file."""
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: list[DiffLine] = field(default_factory=list)


@dataclass
class FileDiff:
    """All changes to a single file."""
    old_path: str
    new_path: str
    hunks: list[DiffHunk] = field(default_factory=list)
    is_new: bool = False
    is_deleted: bool = False

    @property
    def added_lines(self) -> list[DiffLine]:
        return [line for h in self.hunks for line in h.lines if line.kind == "add"]

    @property
    def deleted_lines(self) -> list[DiffLine]:
        return [line for h in self.hunks for line in h.lines if line.kind == "delete"]

    @property
    def changed_line_numbers(self) -> list[int]:
        """New-file line numbers for all added lines (useful for grading)."""
        return [line.number for line in self.added_lines if line.number > 0]


# ────────────────────── Regex Patterns ─────────────────────────

_DIFF_HEADER = re.compile(r"^diff --git a/(.+?) b/(.+?)$")

# BUG FIX: original pattern used r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@"
# which fails on hunk headers that have trailing text after "@@", e.g.:
#   "@@ -1,4 +1,6 @@ def my_function():"
# The fix: allow any trailing characters after the closing "@@".
_HUNK_HEADER = re.compile(
    r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@"
)

# FIX: plain "diff a/foo b/foo" (non-git) patches use this header
_DIFF_HEADER_PLAIN = re.compile(r"^diff (?!--git )(.+)$")


def parse_diff(diff_text: str) -> list[FileDiff]:
    """
    Parse a unified diff string into structured FileDiff objects.

    Supports:
      - git diffs  (diff --git a/foo b/foo)
      - plain diffs (--- a/foo / +++ b/foo)
    """
    files: list[FileDiff] = []
    current_file: FileDiff | None = None
    current_hunk: DiffHunk | None = None
    new_line = 0
    old_line = 0

    for raw_line in diff_text.splitlines():

        # ── git diff header ──────────────────────────────────
        m = _DIFF_HEADER.match(raw_line)
        if m:
            current_file = FileDiff(old_path=m.group(1), new_path=m.group(2))
            files.append(current_file)
            current_hunk = None
            continue

        # ── new / deleted file markers ───────────────────────
        if raw_line.startswith("new file"):
            if current_file:
                current_file.is_new = True
            continue
        if raw_line.startswith("deleted file"):
            if current_file:
                current_file.is_deleted = True
            continue

        # ── plain diff: "--- a/foo" creates a file entry ────
        # (only if no git header was seen for this file)
        if raw_line.startswith("--- "):
            path = raw_line[4:].strip()
            # Strip leading "a/" prefix if present
            if path.startswith("a/"):
                path = path[2:]
            if current_file is None or raw_line.startswith("--- /dev/null"):
                # Start a new file entry for plain diffs
                current_file = FileDiff(old_path=path, new_path=path)
                files.append(current_file)
                if raw_line.startswith("--- /dev/null"):
                    current_file.is_new = True
            continue

        if raw_line.startswith("+++ "):
            path = raw_line[4:].strip()
            if path.startswith("b/"):
                path = path[2:]
            if current_file is not None:
                current_file.new_path = path
                if raw_line.startswith("+++ /dev/null"):
                    current_file.is_deleted = True
            continue

        # ── hunk header ──────────────────────────────────────
        m = _HUNK_HEADER.match(raw_line)
        if m and current_file is not None:
            old_start = int(m.group(1))
            # BUG FIX: group(2) is None when count is omitted (single-line hunk).
            # The original used `int(m.group(2) or "1")` which works, kept as-is.
            old_count = int(m.group(2) if m.group(2) is not None else 1)
            new_start = int(m.group(3))
            new_count = int(m.group(4) if m.group(4) is not None else 1)
            current_hunk = DiffHunk(
                old_start=old_start,
                old_count=old_count,
                new_start=new_start,
                new_count=new_count,
            )
            current_file.hunks.append(current_hunk)
            old_line = old_start
            new_line = new_start
            continue

        # ── diff content lines ───────────────────────────────
        if current_hunk is not None:
            if raw_line.startswith("+"):
                current_hunk.lines.append(DiffLine(
                    number=new_line,
                    old_number=0,
                    content=raw_line[1:],
                    kind="add",
                ))
                new_line += 1

            elif raw_line.startswith("-"):
                current_hunk.lines.append(DiffLine(
                    number=0,
                    old_number=old_line,
                    content=raw_line[1:],
                    kind="delete",
                ))
                old_line += 1

            elif raw_line.startswith(" "):
                current_hunk.lines.append(DiffLine(
                    number=new_line,
                    old_number=old_line,
                    content=raw_line[1:],
                    kind="context",
                ))
                old_line += 1
                new_line += 1

            # "\ No newline at end of file" and other noise → skip

    return files


def summarize_diff(files: list[FileDiff]) -> str:
    """Produce a human-readable summary of a parsed diff."""
    if not files:
        return "No files changed."
    parts = []
    total_added = 0
    total_deleted = 0
    for f in files:
        added = len(f.added_lines)
        deleted = len(f.deleted_lines)
        total_added += added
        total_deleted += deleted
        status = "new" if f.is_new else "deleted" if f.is_deleted else "modified"
        parts.append(f"  {f.new_path} ({status}): +{added} −{deleted}")
    header = (
        f"{len(files)} file{'s' if len(files) != 1 else ''} changed, "
        f"+{total_added} −{total_deleted} lines"
    )
    return header + "\n" + "\n".join(parts)


def get_changed_lines_by_file(files: list[FileDiff]) -> dict[str, list[int]]:
    """
    Return a mapping of filename → list of changed new-file line numbers.
    Useful for cross-referencing agent issue reports against the actual diff.
    """
    return {
        f.new_path: f.changed_line_numbers
        for f in files
        if f.changed_line_numbers
    }