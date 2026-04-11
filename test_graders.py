"""Test all 15 task graders for OpenEnv validator compliance."""

tasks = [
    "task_001_null_check", "task_002_sql_inject", "task_003_off_by_one",
    "task_004_tensor_shape", "task_005_clean_pr", "task_006_race_condition",
    "task_007_hardcoded_secret", "task_008_n_plus_one", "task_009_path_traversal",
    "task_010_memory_leak", "task_011_type_confusion", "task_012_clean_refactor",
    "task_013_xss_vulnerability", "task_014_error_swallow", "task_015_clean_logging"
]

print("Task                              Probe   Full    Status")
print("-" * 65)
all_ok = True
for tid in tasks:
    mod = __import__(f"tasks.{tid}.grader", fromlist=["grade"])
    probe = mod.grade()
    full = mod.grade(
        "test action with sql injection null check bug fix",
        {"bugs": ["test"], "verdict": "request_changes", "min_issues": 1}
    )
    ok = 0.0 < probe < 1.0 and 0.0 < full < 1.0
    status = "PASS" if ok else "FAIL"
    if not ok:
        all_ok = False
    print(f"{tid:35s} {probe:.4f}  {full:.4f}  {status}")

print("-" * 65)

# Also test root grader
import grader
root_probe = grader.grade()
root_ok = 0.0 < root_probe < 1.0
print(f"Root grader probe: {root_probe:.4f}  {'PASS' if root_ok else 'FAIL'}")
print()
print(f"{len(tasks)}/15 task graders - all scores in (0, 1): {'YES' if all_ok else 'NO'}")
