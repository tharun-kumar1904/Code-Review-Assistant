"""
Unit tests for the StaticAnalyzer service.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from services.static_analyzer import StaticAnalyzer


@pytest.fixture
def analyzer():
    return StaticAnalyzer()


# ── Line of Code counting ────────────────────────────────────────────

class TestLOC:
    def test_counts_non_empty_lines(self, analyzer):
        code = "line1\nline2\nline3"
        assert analyzer._count_loc(code) == 3

    def test_ignores_empty_lines(self, analyzer):
        code = "line1\n\n\nline2\n"
        assert analyzer._count_loc(code) == 2

    def test_empty_string(self, analyzer):
        assert analyzer._count_loc("") == 0

    def test_whitespace_only_lines(self, analyzer):
        code = "   \n\t\n  \t  "
        assert analyzer._count_loc(code) == 0


# ── Cyclomatic complexity ─────────────────────────────────────────────

class TestComplexity:
    def test_simple_code_low_complexity(self, analyzer):
        code = "x = 1\ny = 2\nz = x + y"
        result = analyzer._cyclomatic_complexity(code, "test.js")
        assert result >= 1.0

    def test_branching_increases_complexity(self, analyzer):
        code = "if x:\n  pass\nelif y:\n  pass\nelse:\n  pass\nfor i in range(10):\n  pass"
        result = analyzer._cyclomatic_complexity(code, "test.js")
        assert result > 1.0


# ── Comment ratio ─────────────────────────────────────────────────────

class TestCommentRatio:
    def test_python_comments(self, analyzer):
        code = "# comment\nx = 1\n# another"
        ratio = analyzer._comment_ratio(code, "test.py")
        assert abs(ratio - 2 / 3) < 0.01

    def test_js_comments(self, analyzer):
        code = "// comment\nvar x = 1;\n// another"
        ratio = analyzer._comment_ratio(code, "test.js")
        assert abs(ratio - 2 / 3) < 0.01

    def test_no_comments(self, analyzer):
        code = "x = 1\ny = 2"
        ratio = analyzer._comment_ratio(code, "test.py")
        assert ratio == 0.0

    def test_empty_file(self, analyzer):
        assert analyzer._comment_ratio("", "test.py") == 0.0


# ── Issue detection ───────────────────────────────────────────────────

class TestIssueDetection:
    def test_detects_todo_comments(self, analyzer):
        code = "x = 1\n# TODO: fix this later\ny = 2"
        issues = analyzer._detect_issues("test.py", code)
        todo_issues = [i for i in issues if "TODO" in i["issue"]]
        assert len(todo_issues) == 1
        assert todo_issues[0]["severity"] == "info"
        assert todo_issues[0]["category"] == "documentation"

    def test_detects_fixme(self, analyzer):
        code = "# FIXME: broken logic"
        issues = analyzer._detect_issues("test.py", code)
        assert any("TODO" in i["issue"] or "FIXME" in i["issue"] for i in issues)

    def test_no_issues_in_clean_code(self, analyzer):
        code = "x = 1\ny = x + 2\nprint(y)"
        issues = analyzer._detect_issues("test.py", code)
        assert len(issues) == 0


# ── Full file analysis ────────────────────────────────────────────────

class TestAnalyzeFile:
    def test_returns_all_metrics(self, analyzer):
        code = "def foo():\n    x = 1\n    return x"
        result = analyzer.analyze_file("test.py", code)
        assert "file_path" in result
        assert "cyclomatic_complexity" in result
        assert "maintainability_index" in result
        assert "lines_of_code" in result
        assert "comment_ratio" in result
        assert "issues" in result
        assert result["file_path"] == "test.py"
        assert result["lines_of_code"] == 3

    def test_analyze_files_aggregation(self, analyzer):
        files = [
            {"filename": "a.py", "patch": "x = 1\ny = 2"},
            {"filename": "b.py", "patch": "z = 3\nw = 4\nv = 5"},
        ]
        result = analyzer.analyze_files(files)
        assert result["aggregated"]["total_files"] == 2
        assert result["aggregated"]["total_loc"] == 5


# ── Halstead estimate ─────────────────────────────────────────────────

class TestHalstead:
    def test_basic_halstead(self, analyzer):
        code = "x = 1\ny = x + 2"
        result = analyzer._halstead_estimate(code)
        assert result > 0

    def test_empty_halstead(self, analyzer):
        assert analyzer._halstead_estimate("") == 0.0


# ── Duplication detection ─────────────────────────────────────────────

class TestDuplication:
    def test_no_duplication(self, analyzer):
        chunks = [("a.py", "chunk one\nline two\nline three")]
        result = analyzer._detect_duplication(chunks)
        assert result == 0.0

    def test_empty_chunks(self, analyzer):
        assert analyzer._detect_duplication([]) == 0.0
