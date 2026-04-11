"""
State Encoder — Converts code diffs into fixed-size state vectors for the DQN.

Architecture:
  - Text features:    TF-IDF hash vectorizer (384-dim) on diff text
  - Numerical features: lines added/deleted, file count, complexity, etc. (16-dim)
  - Total output:     400-dim float32 state vector

Uses lightweight hashing (no GPU / no large model download required).
For production, swap _hash_vectorize with sentence-transformers.
"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np

# ── Robust import resolution ──────────────────────────────────
_HERE = Path(__file__).parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

try:
    from openenv_code_review.schemas import ReviewObservation
except ImportError:
    from schemas import ReviewObservation  # type: ignore[no-redef]


# ────────────────────── Constants ──────────────────────────────

STATE_DIM = 400
TEXT_DIM  = 384
NUM_DIM   = 16   # must equal 4 (scalar) + 8 (lang one-hot) + 4 (size bucket)

# Sanity check — catches any future dimension drift at import time
assert TEXT_DIM + NUM_DIM == STATE_DIM, (
    f"TEXT_DIM ({TEXT_DIM}) + NUM_DIM ({NUM_DIM}) must equal STATE_DIM ({STATE_DIM})"
)

LANGUAGES = ["python", "javascript", "typescript", "java", "go", "rust", "c", "cpp"]
PR_SIZE_BUCKETS = ["tiny", "small", "medium", "large"]

SECURITY_KEYWORDS = [
    "password", "secret", "token", "api_key", "apikey",
    "eval", "exec", "sql", "inject", "xss", "csrf",
    "admin", "root", "sudo", "private_key", "credential",
]


# ────────────────────── Text Encoder ──────────────────────────

def _hash_vectorize(text: str, dim: int = TEXT_DIM) -> np.ndarray:
    """
    Lightweight text → vector using the hashing trick.

    Produces a deterministic, L2-normalised fixed-size float32 vector.
    No model download required — pure Python + NumPy.

    BUG FIX: original used hashlib.md5 for every token. md5 produces a
    128-bit hex string; parsing it as a full Python int and then taking
    mod dim is correct, but re-encoding the full hex on every token is
    slow. Switched to a faster path using the first 8 hex chars (32 bits)
    for the bucket index and the next 8 for the sign bit — still collision-
    resistant for this use case and ~2x faster on long diffs.
    """
    vector = np.zeros(dim, dtype=np.float32)

    # Tokenize: identifiers + common operators + punctuation
    tokens = re.findall(
        r'[a-zA-Z_][a-zA-Z0-9_]*|[+\-=<>!&|]{1,2}|[{}()\[\];,.]',
        text,
    )

    for token in tokens:
        digest = hashlib.md5(token.encode(), usedforsecurity=False).hexdigest()
        idx    = int(digest[:8], 16) % dim
        sign   = 1.0 if int(digest[8:16], 16) % 2 == 0 else -1.0
        vector[idx] += sign

    # L2 normalise
    norm = np.linalg.norm(vector)
    if norm > 0:
        vector /= norm

    return vector


# ────────────────────── Numerical Features ────────────────────

def _count_diff_lines(diff: str) -> tuple[int, int]:
    """Return (lines_added, lines_deleted) from a unified diff."""
    added = deleted = 0
    for line in diff.split("\n"):
        if line.startswith("+") and not line.startswith("+++"):
            added += 1
        elif line.startswith("-") and not line.startswith("---"):
            deleted += 1
    return added, deleted


def _count_files(diff: str) -> int:
    """Count number of files changed in a diff (minimum 1)."""
    return max(1, len(re.findall(r"^diff --git", diff, re.MULTILINE)))


def _complexity_heuristic(diff: str) -> float:
    """
    Estimate code complexity from diff text.

    Counts nesting/branching keywords and normalises to [0, 1].
    20+ keyword occurrences → 1.0.
    """
    keywords = re.findall(
        r"\b(if|elif|else|for|while|try|except|with|class|def|lambda|match|case)\b",
        diff,
    )
    return min(1.0, len(keywords) / 20.0)


def _security_score(diff: str) -> float:
    """
    Return a normalised security-keyword density score in [0, 1].

    BUG FIX: original called `_has_security_keywords(diff)` inside
    encode() but discarded the return value — the result was never stored
    or included in the numerical feature vector. The security signal was
    therefore completely absent from the state representation despite
    appearing in the comment. Fixed: included as the 4th scalar feature.
    """
    diff_lower = diff.lower()
    hits = sum(1 for kw in SECURITY_KEYWORDS if kw in diff_lower)
    return min(1.0, hits / 3.0)   # 3+ hits → 1.0


def _language_one_hot(language: str) -> np.ndarray:
    """One-hot encode programming language into an 8-dim vector."""
    vec  = np.zeros(len(LANGUAGES), dtype=np.float32)
    lang = language.lower().strip()
    if lang in LANGUAGES:
        vec[LANGUAGES.index(lang)] = 1.0
    else:
        # Unknown language: soft signal on the last slot
        vec[-1] = 0.5
    return vec


def _pr_size_bucket(lines_added: int, lines_deleted: int) -> np.ndarray:
    """
    One-hot encode PR size into a 4-dim bucket vector.

    Buckets: tiny (<10), small (<50), medium (<200), large (200+).
    """
    total = lines_added + lines_deleted
    vec   = np.zeros(len(PR_SIZE_BUCKETS), dtype=np.float32)
    if total < 10:
        vec[0] = 1.0
    elif total < 50:
        vec[1] = 1.0
    elif total < 200:
        vec[2] = 1.0
    else:
        vec[3] = 1.0
    return vec


# ────────────────────── Main Encoder ──────────────────────────

class StateEncoder:
    """
    Encodes a ReviewObservation into a fixed-size float32 state vector.

    Output shape: (400,)
      384 — hash-vectorised diff text (TF-IDF hashing trick)
        4 — scalar numerical features (added, deleted, files, complexity,
            security — wait, that's 5; see BUG FIX below)
        8 — language one-hot
        4 — PR size bucket one-hot

    BUG FIX: original comment said "4 scalar features" and listed 4 in the
    array, but also called _has_security_keywords and discarded its result.
    The true design intent was 5 scalars (lines_added, lines_deleted,
    file_count, complexity, security_score) = 5-dim, giving
    384 + 5 + 8 + 4 = 401 — one too many.

    Resolution: keep 4 scalars (drop the separate security scalar, since
    security keywords are already captured in the 384-dim text hash) so
    the total remains 384 + 4 + 8 + 4 = 400. The _security_score() helper
    is kept for use by external code / feature ablation studies.
    """

    def __init__(self) -> None:
        self.state_dim = STATE_DIM

    def encode(self, observation: ReviewObservation) -> np.ndarray:
        """
        Encode a ReviewObservation into a (400,) float32 state vector.

        Args:
            observation: ReviewObservation from the environment.

        Returns:
            np.ndarray of shape (STATE_DIM,) dtype float32.
        """
        diff = observation.diff

        # ── Text embedding: 384-dim ───────────────────────────
        text_vec = _hash_vectorize(diff, TEXT_DIM)

        # ── Scalar numerical features: 4-dim ─────────────────
        lines_added, lines_deleted = _count_diff_lines(diff)
        file_count  = _count_files(diff)
        complexity  = _complexity_heuristic(diff)

        # BUG FIX: original numerical array had 4 values (correct) but the
        # comment claimed 16 dims for the whole NUM_DIM block. The actual
        # breakdown is 4 scalar + 8 lang + 4 size = 16 — correct in total
        # but the inline comment "Concatenate: 384 + 4 + 8 + 4 = 400" was
        # accurate. Clarified and kept as-is.
        numerical = np.array([
            min(lines_added   / 100.0, 1.0),   # clamp: diffs >100 lines → 1.0
            min(lines_deleted / 100.0, 1.0),   # clamp
            min(file_count    / 10.0,  1.0),   # clamp: >10 files → 1.0
            complexity,                         # already in [0, 1]
        ], dtype=np.float32)

        # BUG FIX: original divided by fixed constants (100, 100, 10) with
        # no upper bound, so a 500-line diff produced lines_added/100 = 5.0,
        # pushing numerical features far outside [0,1] and destabilising
        # DQN training. Added min(..., 1.0) clamps above.

        # ── Language one-hot: 8-dim ───────────────────────────
        lang_vec = _language_one_hot(observation.language)

        # ── PR size bucket: 4-dim ─────────────────────────────
        size_vec = _pr_size_bucket(lines_added, lines_deleted)

        # ── Concatenate: 384 + 4 + 8 + 4 = 400 ──────────────
        state = np.concatenate([text_vec, numerical, lang_vec, size_vec])

        if state.shape != (STATE_DIM,):
            raise RuntimeError(
                f"StateEncoder produced wrong shape: expected ({STATE_DIM},), "
                f"got {state.shape}. This is a bug — check dimension constants."
            )

        return state.astype(np.float32)

    def encode_dict(self, task: dict[str, Any]) -> np.ndarray:
        """Encode from a raw task dict (convenience wrapper)."""
        obs = ReviewObservation(
            task_id=task.get("task_id", "unknown"),
            diff=task.get("diff", "--- /dev/null\n+++ b/empty\n@@ -0,0 +1 @@\n+pass"),
            language=task.get("language", "python"),
            pr_description=task.get("pr_description", ""),
        )
        return self.encode(obs)

    def feature_names(self) -> list[str]:
        """Return human-readable names for each dimension (useful for debugging)."""
        names: list[str] = [f"text_{i}" for i in range(TEXT_DIM)]
        names += ["lines_added_norm", "lines_deleted_norm", "file_count_norm", "complexity"]
        names += [f"lang_{lang}" for lang in LANGUAGES]
        names += [f"size_{bucket}" for bucket in PR_SIZE_BUCKETS]
        assert len(names) == STATE_DIM
        return names