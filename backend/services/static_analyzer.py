"""
Static code analyzer.
Computes complexity, maintainability, duplication, and LOC metrics.
"""

import re
import hashlib
from typing import List, Dict, Any


class StaticAnalyzer:
    """Static analysis engine for code quality metrics."""

    def analyze_file(self, filename: str, content: str) -> Dict[str, Any]:
        """Run all static analysis checks on a file."""
        return {
            "file_path": filename,
            "cyclomatic_complexity": self._cyclomatic_complexity(content, filename),
            "maintainability_index": self._maintainability_index(content, filename),
            "lines_of_code": self._count_loc(content),
            "comment_ratio": self._comment_ratio(content, filename),
            "duplication_percentage": 0.0,  # Computed across files
            "halstead_volume": self._halstead_estimate(content),
            "issues": self._detect_issues(filename, content),
        }

    def analyze_files(self, files: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze multiple files and compute aggregated metrics."""
        results = []
        all_chunks = []

        for f in files:
            filename = f.get("filename", "")
            content = f.get("patch", "") or f.get("content", "")
            if not content:
                continue

            result = self.analyze_file(filename, content)
            results.append(result)

            # Collect chunks for duplication detection
            chunks = self._extract_chunks(content)
            all_chunks.extend([(filename, c) for c in chunks])

        # Compute duplication across files
        duplication = self._detect_duplication(all_chunks)

        # Aggregate metrics
        total_loc = sum(r["lines_of_code"] for r in results)
        avg_complexity = (
            sum(r["cyclomatic_complexity"] for r in results) / len(results)
            if results else 0
        )
        avg_maintainability = (
            sum(r["maintainability_index"] for r in results) / len(results)
            if results else 100
        )

        all_issues = []
        for r in results:
            all_issues.extend(r.get("issues", []))

        return {
            "files": results,
            "aggregated": {
                "total_files": len(results),
                "total_loc": total_loc,
                "avg_complexity": round(avg_complexity, 2),
                "avg_maintainability": round(avg_maintainability, 2),
                "duplication_percentage": round(duplication, 2),
            },
            "issues": all_issues,
        }

    def _cyclomatic_complexity(self, content: str, filename: str) -> float:
        """Estimate cyclomatic complexity from code."""
        try:
            if filename.endswith(".py"):
                from radon.complexity import cc_visit
                blocks = cc_visit(content)
                if blocks:
                    return round(sum(b.complexity for b in blocks) / len(blocks), 2)
        except Exception:
            pass

        # Fallback: count branching keywords
        branches = len(re.findall(
            r'\b(if|elif|else|for|while|case|catch|except|&&|\|\|)\b', content
        ))
        lines = max(content.count('\n'), 1)
        return round(1 + (branches / lines) * 10, 2)

    def _maintainability_index(self, content: str, filename: str) -> float:
        """Estimate maintainability index (0-100 scale)."""
        try:
            if filename.endswith(".py"):
                from radon.metrics import mi_visit
                score = mi_visit(content, True)
                return round(score, 2) if isinstance(score, (int, float)) else 50.0
        except Exception:
            pass

        # Fallback estimation
        loc = self._count_loc(content)
        comment_r = self._comment_ratio(content, filename)
        complexity = self._cyclomatic_complexity(content, filename)

        # Simplified MI formula
        mi = max(0, min(100, 171 - 5.2 * (loc / 100) - 0.23 * complexity + 16 * comment_r))
        return round(mi, 2)

    def _count_loc(self, content: str) -> int:
        """Count non-empty lines of code."""
        lines = content.split('\n')
        return sum(1 for line in lines if line.strip())

    def _comment_ratio(self, content: str, filename: str) -> float:
        """Estimate the ratio of comment lines to total lines."""
        lines = content.split('\n')
        total = len(lines)
        if total == 0:
            return 0.0

        comment_patterns = {
            '.py': r'^\s*(#|"""|\'\'\')' ,
            '.js': r'^\s*(//|/\*|\*)',
            '.jsx': r'^\s*(//|/\*|\*)',
            '.ts': r'^\s*(//|/\*|\*)',
            '.tsx': r'^\s*(//|/\*|\*)',
            '.java': r'^\s*(//|/\*|\*)',
            '.go': r'^\s*(//|/\*)',
        }

        ext = '.' + filename.rsplit('.', 1)[-1] if '.' in filename else ''
        pattern = comment_patterns.get(ext, r'^\s*(//|#|/\*)')

        comments = sum(1 for line in lines if re.match(pattern, line))
        return round(comments / total, 3)

    def _halstead_estimate(self, content: str) -> float:
        """Rough Halstead volume estimate."""
        tokens = re.findall(r'\b\w+\b', content)
        unique = set(tokens)
        n = len(tokens)
        n_unique = len(unique) or 1
        import math
        return round(n * math.log2(n_unique), 2) if n > 0 else 0.0

    def _extract_chunks(self, content: str, chunk_size: int = 3) -> List[str]:
        """Extract overlapping chunks of lines for duplication detection."""
        lines = [l.strip() for l in content.split('\n') if l.strip()]
        chunks = []
        for i in range(len(lines) - chunk_size + 1):
            chunk = '\n'.join(lines[i:i + chunk_size])
            if len(chunk) > 20:  # Ignore tiny chunks
                chunks.append(chunk)
        return chunks

    def _detect_duplication(self, chunks: List[tuple]) -> float:
        """Detect duplicate code blocks using hash matching."""
        if not chunks:
            return 0.0

        hashes = {}
        duplicates = 0
        for filename, chunk in chunks:
            h = hashlib.md5(chunk.encode()).hexdigest()
            if h in hashes and hashes[h] != filename:
                duplicates += 1
            hashes[h] = filename

        return (duplicates / len(chunks)) * 100 if chunks else 0.0

    def _detect_issues(self, filename: str, content: str) -> List[Dict[str, Any]]:
        """Detect common code issues via pattern matching."""
        issues = []

        # Long functions
        if filename.endswith('.py'):
            func_pattern = re.finditer(r'def (\w+)\(', content)
            for match in func_pattern:
                func_start = match.start()
                # Count lines in the function (rough estimate)
                rest = content[func_start:]
                next_def = re.search(r'\ndef ', rest[1:])
                func_body = rest[:next_def.start() + 1] if next_def else rest
                func_lines = func_body.count('\n')
                if func_lines > 50:
                    line_num = content[:func_start].count('\n') + 1
                    issues.append({
                        "file_path": filename,
                        "line_number": line_num,
                        "severity": "medium",
                        "category": "style",
                        "issue": f"Function '{match.group(1)}' is too long ({func_lines} lines)",
                        "explanation": "Long functions are harder to test, understand, and maintain. Consider breaking this into smaller, focused functions.",
                        "suggested_fix": "Refactor into smaller functions, each with a single responsibility.",
                        "confidence": 0.7,
                        "source": "static",
                    })

        # TODO comments
        for i, line in enumerate(content.split('\n'), 1):
            if re.search(r'\bTODO\b|\bFIXME\b|\bHACK\b|\bXXX\b', line, re.IGNORECASE):
                issues.append({
                    "file_path": filename,
                    "line_number": i,
                    "severity": "info",
                    "category": "documentation",
                    "issue": "Unresolved TODO/FIXME comment",
                    "explanation": "Technical debt markers should be addressed before merging.",
                    "suggested_fix": "Resolve the TODO or create a tracking issue.",
                    "confidence": 0.9,
                    "source": "static",
                })

        return issues
