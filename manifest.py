"""
Task manifest for OpenEnv validator discovery.

Some validator versions read this file to discover tasks independently
of openenv.yaml. Each entry maps a task_id to its grader module path.
"""

TASKS = [
    {"id": "task_001_null_check",       "name": "Null Check Missing",           "grader": "tasks.task_001_null_check.grader:grade"},
    {"id": "task_002_sql_inject",       "name": "SQL Injection",                "grader": "tasks.task_002_sql_inject.grader:grade"},
    {"id": "task_003_off_by_one",       "name": "Off By One Error",             "grader": "tasks.task_003_off_by_one.grader:grade"},
    {"id": "task_004_tensor_shape",     "name": "Tensor Shape Mismatch",        "grader": "tasks.task_004_tensor_shape.grader:grade"},
    {"id": "task_005_clean_pr",         "name": "Clean PR",                     "grader": "tasks.task_005_clean_pr.grader:grade"},
    {"id": "task_006_race_condition",   "name": "Race Condition",               "grader": "tasks.task_006_race_condition.grader:grade"},
    {"id": "task_007_hardcoded_secret", "name": "Hardcoded Secret",             "grader": "tasks.task_007_hardcoded_secret.grader:grade"},
    {"id": "task_008_n_plus_one",       "name": "N Plus One Query",             "grader": "tasks.task_008_n_plus_one.grader:grade"},
    {"id": "task_009_path_traversal",   "name": "Path Traversal",               "grader": "tasks.task_009_path_traversal.grader:grade"},
    {"id": "task_010_memory_leak",      "name": "Memory Leak",                  "grader": "tasks.task_010_memory_leak.grader:grade"},
    {"id": "task_011_type_confusion",   "name": "Type Confusion",               "grader": "tasks.task_011_type_confusion.grader:grade"},
    {"id": "task_012_clean_refactor",   "name": "Clean Refactor",               "grader": "tasks.task_012_clean_refactor.grader:grade"},
    {"id": "task_013_xss_vulnerability","name": "XSS Vulnerability",            "grader": "tasks.task_013_xss_vulnerability.grader:grade"},
    {"id": "task_014_error_swallow",    "name": "Error Swallowing",             "grader": "tasks.task_014_error_swallow.grader:grade"},
    {"id": "task_015_clean_logging",    "name": "Clean Logging",                "grader": "tasks.task_015_clean_logging.grader:grade"},
]


def get_task_graders():
    """Return dict of task_id -> grader module path."""
    return {t["id"]: t["grader"] for t in TASKS}


def get_task_ids():
    """Return list of all task IDs."""
    return [t["id"] for t in TASKS]
