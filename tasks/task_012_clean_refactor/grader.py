"""Grader for task_012_clean_refactor — Clean async context manager refactor."""

GOLD = {
    "bugs": [],
    "verdict": "approve",
    "min_issues": 0,
}


def _score_action(action, gold=None):
    if gold is None:
        gold = GOLD
    verdict = gold.get("verdict", "approve")
    action_str = str(action).lower()

    verdict_score = 0.0
    if verdict == "approve":
        if "approve" in action_str or "true" in action_str:
            verdict_score = 0.40
        elif "request_changes" not in action_str and "reject" not in action_str:
            verdict_score = 0.20
    elif verdict == "request_changes":
        if "request_changes" in action_str or "false" in action_str:
            verdict_score = 0.40

    bug_score = 0.40
    issue_words = ["bug", "error", "vulnerability", "critical", "high"]
    false_alarms = sum(1 for w in issue_words if w in action_str)
    if false_alarms > 2:
        bug_score = 0.10

    action_score = 0.19

    raw = verdict_score + bug_score + action_score
    return max(0.01, min(0.99, raw))


def grade(*args, **kwargs) -> float:
    if not args and not kwargs:
        return 0.42

    action = kwargs.get("action", args[0] if len(args) >= 1 else "")
    gold = kwargs.get("gold", args[1] if len(args) >= 2 else GOLD)
    try:
        score = _score_action(action, gold if isinstance(gold, dict) else GOLD)
        return max(0.01, min(0.99, float(score)))
    except Exception:
        return 0.53
