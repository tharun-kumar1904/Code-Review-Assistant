"""
Grader — compares agent review output against gold-standard annotations.

Scoring criteria:
  1. Bug Detection Recall   (35%)
  2. False Positive Rate    (15%)  — measured as precision
  3. Severity Accuracy      (20%)
  4. Feedback Quality       (20%)
  5. Summary Quality        (10%)
"""

from __future__ import annotations

from schemas import (
    Category,
    GoldAnnotation,
    GoldIssue,
    GradeBreakdown,
    GradeResult,
    ReviewAction,
    ReviewIssue,
    Severity,
    RELATED_CATEGORIES,
)

# ───────────────── Configuration ───────────────────────────────

LINE_PROXIMITY_THRESHOLD = 5   # Lines within ±5 count as a match
MIN_DESCRIPTION_LENGTH = 20    # Minimum chars for "useful" feedback
SUGGESTED_FIX_BONUS = 0.15    # Bonus for providing a suggested fix


# ───────────────── Issue Matching ──────────────────────────────

def _categories_match(agent_cat: Category, gold_cat: Category) -> bool:
    """Check if two categories match (exact or related)."""
    if agent_cat == gold_cat:
        return True
    return gold_cat in RELATED_CATEGORIES.get(agent_cat, set())


def _issues_match(agent: ReviewIssue, gold: GoldIssue) -> bool:
    """Two issues match if same file, close line numbers, and compatible categories."""
    if agent.file != gold.file:
        return False
    if abs(agent.line - gold.line) > LINE_PROXIMITY_THRESHOLD:
        return False
    if not _categories_match(agent.category, gold.category):
        return False
    return True


def _match_issues(
    agent_issues: list[ReviewIssue], gold_issues: list[GoldIssue]
) -> tuple[list[tuple[ReviewIssue, GoldIssue]], list[ReviewIssue], list[GoldIssue]]:
    """
    Greedy bipartite matching: agent issues ↔ gold issues.
    Returns (matched_pairs, unmatched_agent, unmatched_gold).
    """
    used_gold: set[int] = set()
    matched: list[tuple[ReviewIssue, GoldIssue]] = []
    unmatched_agent: list[ReviewIssue] = []

    for a_issue in agent_issues:
        best_idx = -1
        best_line_dist = LINE_PROXIMITY_THRESHOLD + 1

        for g_idx, g_issue in enumerate(gold_issues):
            if g_idx in used_gold:
                continue
            if _issues_match(a_issue, g_issue):
                dist = abs(a_issue.line - g_issue.line)
                if dist < best_line_dist:
                    best_line_dist = dist
                    best_idx = g_idx

        if best_idx >= 0:
            matched.append((a_issue, gold_issues[best_idx]))
            used_gold.add(best_idx)
        else:
            unmatched_agent.append(a_issue)

    unmatched_gold = [g for i, g in enumerate(gold_issues) if i not in used_gold]
    return matched, unmatched_agent, unmatched_gold


# ───────────────── Criterion Scorers ───────────────────────────

def _score_recall(matched: int, total_gold: int) -> float:
    """Fraction of gold issues found by agent."""
    if total_gold == 0:
        return 1.0  # No issues to find → perfect recall
    return matched / total_gold


def _score_precision(false_positives: int, total_agent: int) -> float:
    """1 - false_positive_rate. Higher is better."""
    if total_agent == 0:
        return 1.0  # No claims → no false positives
    return 1.0 - (false_positives / total_agent)


def _score_severity(
    matched_pairs: list[tuple[ReviewIssue, GoldIssue]],
) -> float:
    """Average severity closeness across matched pairs."""
    if not matched_pairs:
        return 0.0
    total = 0.0
    for agent_issue, gold_issue in matched_pairs:
        diff = abs(Severity.rank(agent_issue.severity) - Severity.rank(gold_issue.severity))
        if diff == 0:
            total += 1.0
        elif diff == 1:
            total += 0.5
        # diff >= 2 → 0.0
    return total / len(matched_pairs)


def _score_feedback(agent_issues: list[ReviewIssue]) -> float:
    """Score feedback usefulness: description length + suggested fix bonus."""
    if not agent_issues:
        return 0.0
    total = 0.0
    for issue in agent_issues:
        # Description quality
        desc_score = min(1.0, len(issue.description) / 80)  # Full marks at 80+ chars
        if len(issue.description) < MIN_DESCRIPTION_LENGTH:
            desc_score *= 0.5
        # Suggested fix bonus
        fix_score = SUGGESTED_FIX_BONUS if issue.suggested_fix and len(issue.suggested_fix) > 10 else 0.0
        total += min(1.0, desc_score + fix_score)
    return total / len(agent_issues)


def _score_summary(summary: str, keywords: list[str]) -> float:
    """Score summary quality based on keyword coverage and length."""
    if not summary or len(summary.strip()) < 10:
        return 0.0
    score = 0.3  # Base score for non-empty summary
    # Length bonus (up to 0.3)
    score += min(0.3, len(summary) / 300)
    # Keyword coverage (up to 0.4)
    if keywords:
        hits = sum(1 for kw in keywords if kw.lower() in summary.lower())
        score += 0.4 * (hits / len(keywords))
    else:
        score += 0.2  # No keywords defined → partial credit
    return min(1.0, score)


# ───────────────── Main Grading Function ───────────────────────

def grade_review(action: ReviewAction, gold: GoldAnnotation) -> GradeResult:
    """
    Grade an agent's review against the gold standard.

    Returns a GradeResult with per-criterion breakdown and final score.
    """
    # --- Match issues ---
    matched_pairs, unmatched_agent, unmatched_gold = _match_issues(
        action.issues, gold.issues
    )

    n_matched = len(matched_pairs)
    n_fp = len(unmatched_agent)
    n_missed = len(unmatched_gold)
    n_gold = len(gold.issues)
    n_agent = len(action.issues)

    # --- Per-criterion scores ---
    recall = _score_recall(n_matched, n_gold)
    precision = _score_precision(n_fp, n_agent)
    severity_acc = _score_severity(matched_pairs)
    feedback_q = _score_feedback(action.issues)
    summary_q = _score_summary(action.summary, gold.summary_keywords)

    breakdown = GradeBreakdown(
        recall=round(recall, 4),
        precision=round(precision, 4),
        severity_accuracy=round(severity_acc, 4),
        feedback_quality=round(feedback_q, 4),
        summary_quality=round(summary_q, 4),
        matched_issues=n_matched,
        false_positives=n_fp,
        missed_issues=n_missed,
        total_gold=n_gold,
        total_agent=n_agent,
    )

    # --- Matched pair details for the UI ---
    pair_details = []
    for a, g in matched_pairs:
        pair_details.append({
            "agent": a.model_dump(),
            "gold": g.model_dump(),
            "severity_match": a.severity == g.severity,
        })

    # --- Human-readable feedback ---
    lines = []
    if n_missed > 0:
        lines.append(f"Missed {n_missed} issue(s): " + ", ".join(
            f"{g.category.value} at {g.file}:{g.line}" for g in unmatched_gold
        ))
    if n_fp > 0:
        lines.append(f"{n_fp} false positive(s) reported.")
    if recall == 1.0 and precision == 1.0:
        lines.append("✅ Perfect detection — all issues found with no false positives!")
    feedback_text = " | ".join(lines) if lines else "Review graded successfully."

    # --- Final weighted score ---
    from reward import compute_reward
    score = compute_reward(breakdown)

    return GradeResult(
        score=round(score, 4),
        breakdown=breakdown,
        matched_pairs=pair_details,
        feedback=feedback_text,
    )
