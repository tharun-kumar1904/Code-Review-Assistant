"""
Unified diff parser — extracts structured hunk data from patch text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class DiffLine:
    """A single line within a diff hunk."""
    number: int          # Line number in the new file (0 if deleted)
    old_number: int      # Line number in the old file (0 if added)
    content: str         # Line content (without +/-/ prefix)
    kind: str            # "add", "delete", or "context"


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
        return [l for h in self.hunks for l in h.lines if l.kind == "add"]

    @property
    def deleted_lines(self) -> list[DiffLine]:
        return [l for h in self.hunks for l in h.lines if l.kind == "delete"]


# ────────────────────── Regex Patterns ─────────────────────────

_DIFF_HEADER = re.compile(r"^diff --git a/(.+?) b/(.+?)$")
_HUNK_HEADER = re.compile(
    r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@"
)


def parse_diff(diff_text: str) -> list[FileDiff]:
    """Parse a unified diff string into structured FileDiff objects."""
    files: list[FileDiff] = []
    current_file: FileDiff | None = None
    current_hunk: DiffHunk | None = None
    new_line = 0
    old_line = 0

    for raw_line in diff_text.splitlines():
        # New file header
        m = _DIFF_HEADER.match(raw_line)
        if m:
            current_file = FileDiff(old_path=m.group(1), new_path=m.group(2))
            files.append(current_file)
            current_hunk = None
            continue

        # Detect new / deleted files
        if raw_line.startswith("new file"):
            if current_file:
                current_file.is_new = True
            continue
        if raw_line.startswith("deleted file"):
            if current_file:
                current_file.is_deleted = True
            continue

        # Skip --- and +++ lines
        if raw_line.startswith("--- ") or raw_line.startswith("+++ "):
            continue

        # Hunk header
        m = _HUNK_HEADER.match(raw_line)
        if m and current_file is not None:
            old_start = int(m.group(1))
            old_count = int(m.group(2) or "1")
            new_start = int(m.group(3))
            new_count = int(m.group(4) or "1")
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

        # Diff content lines
        if current_hunk is not None:
            if raw_line.startswith("+"):
                current_hunk.lines.append(
                    DiffLine(
                        number=new_line,
                        old_number=0,
                        content=raw_line[1:],
                        kind="add",
                    )
                )
                new_line += 1
            elif raw_line.startswith("-"):
                current_hunk.lines.append(
                    DiffLine(
                        number=0,
                        old_number=old_line,
                        content=raw_line[1:],
                        kind="delete",
                    )
                )
                old_line += 1
            elif raw_line.startswith(" "):
                current_hunk.lines.append(
                    DiffLine(
                        number=new_line,
                        old_number=old_line,
                        content=raw_line[1:],
                        kind="context",
                    )
                )
                old_line += 1
                new_line += 1
            # Skip "No newline at end of file" or other noise

    return files


def summarize_diff(files: list[FileDiff]) -> str:
    """Produce a human-readable summary of a parsed diff."""
    parts = []
    for f in files:
        added = len(f.added_lines)
        deleted = len(f.deleted_lines)
        status = "new" if f.is_new else "deleted" if f.is_deleted else "modified"
        parts.append(f"  {f.new_path} ({status}): +{added} -{deleted}")
    return "Files changed:\n" + "\n".join(parts)
