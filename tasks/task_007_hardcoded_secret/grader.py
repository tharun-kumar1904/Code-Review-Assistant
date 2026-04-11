"""Grader for task_007_hardcoded_secret — Hardcoded Stripe API key + bare except."""

GOLD = {
    "bugs": ["hardcoded", "secret", "api key", "stripe", "credential", "bare except", "password"],
    "verdict": "request_changes",
    "min_issues": 1,
}


def _score_action(action, gold=None):
    if gold is None:
        gold = GOLD
    bugs = gold.get("bugs", [])
    verdict = gold.get("verdict", "request_changes")
    action_str = str(action).lower()

    verdict_score = 0.0
    if verdict == "request_changes":
        if "request_changes" in action_str or "false" in action_str or "reject" in action_str:
            verdict_score = 0.40
        elif "approve" not in action_str:
            verdict_score = 0.20
    elif verdict == "approve":
        if "approve" in action_str or "true" in action_str:
            verdict_score = 0.40

    bug_hits = sum(1 for b in bugs if b in action_str)
    bug_score = 0.40 * (bug_hits / max(len(bugs), 1))

    actionable_words = ["fix", "use", "environment", "vault", "config", "remove", "rotate"]
    hits = sum(1 for w in actionable_words if w in action_str)
    action_score = 0.20 * min(1.0, hits / 3.0)

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
        return 0.48
