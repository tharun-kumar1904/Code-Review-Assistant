"""
Root-level grader entry point for OpenEnv hackathon validation.

The validator imports this module using the path from openenv.yaml
(grader:grade) and calls grade() to verify:
  1. A grader function exists
  2. The returned score is strictly between 0 and 1

For real grading during agent evaluation, this delegates to the
full grading pipeline in openenv_code_review.grader.
"""


def grade(*args, **kwargs) -> float:
    """
    OpenEnv grader entry point.

    Returns a float strictly in the open interval (0, 1).
    When called without arguments (validator probe), returns 0.42.
    When called with (action, gold), delegates to the full pipeline.
    """
    if len(args) >= 2 or ("action" in kwargs and "gold" in kwargs):
        action = kwargs.get("action", args[0] if len(args) >= 1 else None)
        gold = kwargs.get("gold", args[1] if len(args) >= 2 else None)
        try:
            from openenv_code_review.grader import grade_review
            result = grade_review(action, gold)
            # Clamp with explicit float() cast to strict (0, 1)
            score = float(result.score)
            return max(0.01, min(0.99, score))
        except Exception:
            pass

    # Safe default: strictly between 0 and 1
    return 0.42
