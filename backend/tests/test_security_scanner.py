"""
Unit tests for the SecurityScanner service.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from services.security_scanner import SecurityScanner


@pytest.fixture
def scanner():
    return SecurityScanner()


# ── SQL Injection Detection ───────────────────────────────────────────

class TestSQLInjection:
    def test_detects_fstring_execute(self, scanner):
        code = 'cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")'
        issues = scanner.scan_file("test.py", code)
        sqli = [i for i in issues if "SQL Injection" in i["vulnerability_type"]]
        assert len(sqli) >= 1
        assert sqli[0]["severity"] == "critical"
        assert sqli[0]["cwe_id"] == "CWE-89"

    def test_detects_string_concat_query(self, scanner):
        code = 'query = "SELECT * FROM users WHERE id = " + user_id'
        issues = scanner.scan_file("test.py", code)
        sqli = [i for i in issues if "SQL Injection" in i["vulnerability_type"]]
        assert len(sqli) >= 1


# ── XSS Detection ────────────────────────────────────────────────────

class TestXSS:
    def test_detects_innerhtml(self, scanner):
        code = 'element.innerHTML = userInput;'
        issues = scanner.scan_file("test.js", code)
        xss = [i for i in issues if "XSS" in i["vulnerability_type"]]
        assert len(xss) >= 1
        assert xss[0]["severity"] == "high"

    def test_detects_dangerously_set_innerhtml(self, scanner):
        code = '<div dangerouslySetInnerHTML={{ __html: data }} />'
        issues = scanner.scan_file("test.jsx", code)
        xss = [i for i in issues if "XSS" in i["vulnerability_type"]]
        assert len(xss) >= 1

    def test_detects_document_write(self, scanner):
        code = 'document.write(userContent)'
        issues = scanner.scan_file("test.js", code)
        xss = [i for i in issues if "XSS" in i["vulnerability_type"]]
        assert len(xss) >= 1


# ── Hardcoded Secrets ─────────────────────────────────────────────────

class TestHardcodedSecrets:
    def test_detects_hardcoded_password(self, scanner):
        code = 'password = "SuperSecretPassword123!"'
        issues = scanner.scan_file("config.py", code)
        secrets = [i for i in issues if "Hardcoded" in i["vulnerability_type"]]
        assert len(secrets) >= 1
        assert secrets[0]["severity"] == "critical"

    def test_detects_aws_key(self, scanner):
        code = 'AKIAIOSFODNN7EXAMPLE'
        issues = scanner.scan_file("config.py", code)
        secrets = [i for i in issues if "Hardcoded" in i["vulnerability_type"]]
        assert len(secrets) >= 1

    def test_detects_github_token(self, scanner):
        code = 'token = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij"'
        issues = scanner.scan_file("config.py", code)
        secrets = [i for i in issues if "Hardcoded" in i["vulnerability_type"]]
        assert len(secrets) >= 1


# ── Insecure Functions ────────────────────────────────────────────────

class TestInsecureFunctions:
    def test_detects_eval(self, scanner):
        code = 'result = eval(user_input)'
        issues = scanner.scan_file("test.py", code)
        insecure = [i for i in issues if "Insecure" in i["vulnerability_type"]]
        assert len(insecure) >= 1

    def test_detects_os_system(self, scanner):
        code = 'os.system("rm -rf " + path)'
        issues = scanner.scan_file("test.py", code)
        assert len(issues) >= 1

    def test_detects_pickle_load(self, scanner):
        code = 'data = pickle.load(file)'
        issues = scanner.scan_file("test.py", code)
        insecure = [i for i in issues if "Insecure" in i["vulnerability_type"]]
        assert len(insecure) >= 1

    def test_detects_shell_true(self, scanner):
        code = 'subprocess.run(cmd, shell=True)'
        issues = scanner.scan_file("test.py", code)
        insecure = [i for i in issues if "Insecure" in i["vulnerability_type"]]
        assert len(insecure) >= 1


# ── Path Traversal ────────────────────────────────────────────────────

class TestPathTraversal:
    def test_detects_path_traversal_pattern(self, scanner):
        code = 'open(base_dir + user_filename)'
        issues = scanner.scan_file("test.py", code)
        traversal = [i for i in issues if "Path Traversal" in i["vulnerability_type"]]
        assert len(traversal) >= 1


# ── Insecure HTTP ─────────────────────────────────────────────────────

class TestInsecureHTTP:
    def test_detects_http_url(self, scanner):
        code = 'requests.get("http://api.example.com/data")'
        issues = scanner.scan_file("test.py", code)
        http_issues = [i for i in issues if "Insecure HTTP" in i["vulnerability_type"]]
        assert len(http_issues) >= 1

    def test_ignores_localhost(self, scanner):
        code = 'requests.get("http://localhost:8000/api")'
        issues = scanner.scan_file("test.py", code)
        http_issues = [i for i in issues if "Insecure HTTP" in i["vulnerability_type"]]
        assert len(http_issues) == 0

    def test_detects_verify_false(self, scanner):
        code = 'requests.get(url, verify=False)'
        issues = scanner.scan_file("test.py", code)
        assert len(issues) >= 1


# ── Weak Cryptography ─────────────────────────────────────────────────

class TestWeakCrypto:
    def test_detects_md5(self, scanner):
        code = 'hash = md5(password)'
        issues = scanner.scan_file("auth.py", code)
        crypto = [i for i in issues if "Weak" in i["vulnerability_type"]]
        assert len(crypto) >= 1

    def test_detects_math_random(self, scanner):
        code = 'token = Math.random().toString(36)'
        issues = scanner.scan_file("auth.js", code)
        crypto = [i for i in issues if "Weak" in i["vulnerability_type"]]
        assert len(crypto) >= 1


# ── False Positive Avoidance ──────────────────────────────────────────

class TestFalsePositives:
    def test_ignores_comments(self, scanner):
        code = "# eval() is dangerous, never use it"
        issues = scanner.scan_file("docs.py", code)
        assert len(issues) == 0

    def test_ignores_js_comments(self, scanner):
        code = "// avoid using document.write() in production"
        issues = scanner.scan_file("docs.js", code)
        assert len(issues) == 0


# ── Multi-file scanning ──────────────────────────────────────────────

class TestMultiFileScan:
    def test_scan_multiple_files(self, scanner):
        files = [
            {"filename": "a.py", "patch": 'eval(user_input)'},
            {"filename": "b.js", "patch": 'element.innerHTML = data'},
        ]
        issues = scanner.scan_files(files)
        assert len(issues) >= 2

    def test_scan_empty_files(self, scanner):
        files = [{"filename": "empty.py", "patch": ""}]
        issues = scanner.scan_files(files)
        assert len(issues) == 0

    def test_deduplicates_within_file(self, scanner):
        code = 'eval(a)\neval(b)'
        issues = scanner.scan_file("test.py", code)
        # Each eval on different lines should be separate issues
        eval_issues = [i for i in issues if "Insecure" in i["vulnerability_type"]]
        assert len(eval_issues) == 2
