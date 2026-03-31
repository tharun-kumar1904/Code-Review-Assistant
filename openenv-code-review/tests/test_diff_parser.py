"""
Tests for the unified diff parser.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from diff_parser import parse_diff, summarize_diff


SAMPLE_DIFF = """diff --git a/app.py b/app.py
index 1a2b3c4..5d6e7f8 100644
--- a/app.py
+++ b/app.py
@@ -8,6 +8,12 @@ from database import get_user
 app = FastAPI()
 
 
+@app.get("/user/{user_id}/profile")
+async def get_user_profile(user_id: int):
+    db = get_db_session()
+    user = get_user(db, user_id)
+    return {"name": user.name}
+
 
 @app.get("/health")
 async def health_check():
"""


NEW_FILE_DIFF = """diff --git a/utils.py b/utils.py
new file mode 100644
index 0000000..abc1234
--- /dev/null
+++ b/utils.py
@@ -0,0 +1,3 @@
+def helper():
+    return 42
+
"""


class TestParseDiff:
    def test_parse_single_file(self):
        files = parse_diff(SAMPLE_DIFF)
        assert len(files) == 1
        assert files[0].old_path == "app.py"
        assert files[0].new_path == "app.py"

    def test_added_lines(self):
        files = parse_diff(SAMPLE_DIFF)
        added = files[0].added_lines
        assert len(added) == 6  # 5 code lines + 1 blank line
        assert any("get_user_profile" in l.content for l in added)

    def test_line_numbers(self):
        files = parse_diff(SAMPLE_DIFF)
        added = files[0].added_lines
        # First added line should be at line 11 in new file
        assert added[0].number >= 8

    def test_new_file(self):
        files = parse_diff(NEW_FILE_DIFF)
        assert len(files) == 1
        assert files[0].is_new is True
        assert files[0].new_path == "utils.py"

    def test_empty_diff(self):
        files = parse_diff("")
        assert files == []

    def test_multiple_hunks(self):
        multi_hunk = """diff --git a/a.py b/a.py
--- a/a.py
+++ b/a.py
@@ -1,3 +1,4 @@
 line1
+added1
 line2
 line3
@@ -10,3 +11,4 @@
 line10
+added2
 line11
 line12
"""
        files = parse_diff(multi_hunk)
        assert len(files) == 1
        assert len(files[0].hunks) == 2
        total_added = len(files[0].added_lines)
        assert total_added == 2


class TestSummarizeDiff:
    def test_summarize(self):
        files = parse_diff(SAMPLE_DIFF)
        summary = summarize_diff(files)
        assert "app.py" in summary
        assert "modified" in summary

    def test_summarize_new_file(self):
        files = parse_diff(NEW_FILE_DIFF)
        summary = summarize_diff(files)
        assert "new" in summary
