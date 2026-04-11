"""
Security vulnerability scanner.
Pattern-based detection for common security issues.
"""

import re
from typing import List, Dict, Any


class SecurityScanner:
    """Detects security vulnerabilities in source code."""

    # ── Vulnerability patterns ────────────────────────────────────────────
    PATTERNS = {
        "SQL Injection": {
            "patterns": [
                r'execute\s*\(\s*["\'].*%s.*["\'].*%',
                r'execute\s*\(\s*f["\']',
                r'execute\s*\(\s*["\'].*\+.*\+',
                r'\.format\s*\(.*\).*execute',
                r'cursor\.execute\s*\(\s*["\'].*\{',
                r'query\s*=\s*["\'].*\+\s*\w+',
                r'raw\s*\(\s*f["\']SELECT',
            ],
            "cwe_id": "CWE-89",
            "owasp": "A03:2021 Injection",
            "severity": "critical",
            "remediation": "Use parameterized queries or an ORM instead of string interpolation in SQL statements.",
        },
        "Cross-Site Scripting (XSS)": {
            "patterns": [
                r'innerHTML\s*=',
                r'dangerouslySetInnerHTML',
                r'document\.write\s*\(',
                r'\.html\s*\(\s*[^"\'<]',
                r'v-html\s*=',
                r'render_template_string\s*\(',
                r'Markup\s*\(',
            ],
            "cwe_id": "CWE-79",
            "owasp": "A03:2021 Injection",
            "severity": "high",
            "remediation": "Sanitize and escape all user input before rendering in HTML. Use textContent instead of innerHTML.",
        },
        "Hardcoded Secrets": {
            "patterns": [
                r'(?:password|passwd|pwd|secret|api_key|apikey|token|auth)\s*=\s*["\'][^"\']{8,}["\']',
                r'(?:AWS_SECRET|PRIVATE_KEY|SECRET_KEY)\s*=\s*["\']',
                r'-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----',
                r'sk-[a-zA-Z0-9]{20,}',
                r'ghp_[a-zA-Z0-9]{36}',
                r'AKIA[0-9A-Z]{16}',
            ],
            "cwe_id": "CWE-798",
            "owasp": "A07:2021 Identification and Authentication Failures",
            "severity": "critical",
            "remediation": "Use environment variables or a secrets manager. Never commit credentials to source code.",
        },
        "Insecure Functions": {
            "patterns": [
                r'\beval\s*\(',
                r'\bexec\s*\(',
                r'subprocess\.call\s*\(\s*["\'].*\+',
                r'os\.system\s*\(',
                r'os\.popen\s*\(',
                r'pickle\.loads?\s*\(',
                r'yaml\.load\s*\([^)]*(?!Loader)',
                r'__import__\s*\(',
                r'shell\s*=\s*True',
            ],
            "cwe_id": "CWE-78",
            "owasp": "A03:2021 Injection",
            "severity": "high",
            "remediation": "Avoid using eval/exec. Use subprocess with shell=False and argument lists. Use safe loaders for YAML/pickle.",
        },
        "Path Traversal": {
            "patterns": [
                r'open\s*\(.*\+.*\)',
                r'os\.path\.join\s*\(.*request',
                r'send_file\s*\(.*\+',
                r'\.\./',
                r'file_get_contents\s*\(\s*\$',
            ],
            "cwe_id": "CWE-22",
            "owasp": "A01:2021 Broken Access Control",
            "severity": "high",
            "remediation": "Validate and sanitize file paths. Use os.path.realpath() and ensure paths stay within expected directories.",
        },
        "Insecure HTTP": {
            "patterns": [
                r'http://(?!localhost|127\.0\.0\.1|0\.0\.0\.0)',
                r'verify\s*=\s*False',
                r'VERIFY_SSL\s*=\s*False',
                r'InsecureRequestWarning',
            ],
            "cwe_id": "CWE-319",
            "owasp": "A02:2021 Cryptographic Failures",
            "severity": "medium",
            "remediation": "Always use HTTPS for external connections. Never disable SSL verification in production.",
        },
        "Weak Cryptography": {
            "patterns": [
                r'md5\s*\(',
                r'sha1\s*\(',
                r'DES\b',
                r'RC4\b',
                r'random\.random\s*\(',
                r'Math\.random\s*\(',
            ],
            "cwe_id": "CWE-327",
            "owasp": "A02:2021 Cryptographic Failures",
            "severity": "medium",
            "remediation": "Use SHA-256 or bcrypt for hashing. Use secrets module for cryptographic randomness.",
        },
        "Missing Error Handling": {
            "patterns": [
                r'except\s*:\s*$',
                r'except\s*:\s*pass',
                r'catch\s*\(\s*\)\s*\{',
                r'\.catch\s*\(\s*\(\)\s*=>',
            ],
            "cwe_id": "CWE-390",
            "owasp": "A09:2021 Security Logging and Monitoring Failures",
            "severity": "medium",
            "remediation": "Always catch specific exceptions and handle them appropriately. Log errors for monitoring.",
        },
    }

    def scan_file(self, filename: str, content: str) -> List[Dict[str, Any]]:
        """Scan a single file for security vulnerabilities."""
        issues = []
        lines = content.split('\n')

        for vuln_type, config in self.PATTERNS.items():
            for pattern in config["patterns"]:
                for i, line in enumerate(lines, 1):
                    try:
                        if re.search(pattern, line, re.IGNORECASE):
                            # Avoid false positives in comments
                            stripped = line.strip()
                            if stripped.startswith(('#', '//', '/*', '*', '"""', "'''")):
                                continue

                            issues.append({
                                "vulnerability_type": vuln_type,
                                "severity": config["severity"],
                                "file_path": filename,
                                "line_number": i,
                                "description": f"Potential {vuln_type} detected: {stripped[:120]}",
                                "remediation": config["remediation"],
                                "cwe_id": config["cwe_id"],
                                "owasp_category": config["owasp"],
                                "code_snippet": stripped[:200],
                            })
                    except re.error:
                        continue

        # Deduplicate by (vuln_type, file, line)
        seen = set()
        unique_issues = []
        for issue in issues:
            key = (issue["vulnerability_type"], issue["file_path"], issue["line_number"])
            if key not in seen:
                seen.add(key)
                unique_issues.append(issue)

        return unique_issues

    def scan_files(self, files: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Scan multiple files for security vulnerabilities."""
        all_issues = []
        for f in files:
            filename = f.get("filename", "")
            content = f.get("patch", "") or f.get("content", "")
            if content:
                all_issues.extend(self.scan_file(filename, content))
        return all_issues
