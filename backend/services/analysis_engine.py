"""
Analysis Engine — orchestrates the full PR analysis pipeline.

Pipeline:
1. Fetch PR diff from GitHub
2. Run static analysis
3. Run security scanning
4. Retrieve RAG context
5. Run LLM analysis
6. Aggregate results & compute quality score
7. Store in database
8. Post comments to GitHub
"""

import time
from typing import Dict, Any, List, Optional
from services.github_service import GitHubService
from services.llm_service import LLMService
from services.static_analyzer import StaticAnalyzer
from services.security_scanner import SecurityScanner
from services.rag_service import RAGService


class AnalysisEngine:
    """Orchestrates the complete code review analysis pipeline."""

    def __init__(self):
        self.github = GitHubService()
        self.llm = LLMService()
        self.static = StaticAnalyzer()
        self.security = SecurityScanner()
        self.rag = RAGService()

    async def analyze(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        post_comments: bool = True,
    ) -> Dict[str, Any]:
        """
        Run the full analysis pipeline on a pull request.
        """
        start_time = time.time()

        # Step 1: Fetch PR data from GitHub
        pr_data = await self.github.get_pull_request(owner, repo, pr_number)
        files = await self.github.get_pr_files(owner, repo, pr_number)

        # Step 2: Run static analysis
        static_results = self.static.analyze_files(files)

        # Step 3: Run security scanning
        security_issues = self.security.scan_files(files)

        # Step 4: Retrieve RAG context
        diff_summary = self._summarize_diff(files)
        rag_context = await self.rag.retrieve_context(owner, repo, diff_summary)

        # Step 5: Run LLM analysis
        llm_issues = await self.llm.analyze_code(files, context=rag_context)

        # Step 6: Aggregate results
        all_issues = self._aggregate_issues(
            static_results.get("issues", []),
            security_issues,
            llm_issues,
        )

        quality_score = self._compute_quality_score(all_issues, static_results)
        summary = await self.llm.generate_summary(all_issues, pr_data)

        duration = time.time() - start_time

        # Step 7: Store in database
        review_id = await self._store_results(
            owner=owner,
            repo=repo,
            pr_number=pr_number,
            pr_data=pr_data,
            all_issues=all_issues,
            security_issues=security_issues,
            static_results=static_results,
            quality_score=quality_score,
            summary=summary,
            duration=duration,
        )

        # Step 8: Post comments to GitHub
        if post_comments and all_issues:
            await self._post_github_comments(
                owner, repo, pr_number, pr_data, all_issues, summary
            )

        return {
            "review_id": review_id,
            "quality_score": quality_score,
            "total_issues": len(all_issues),
            "summary": summary,
            "issues": all_issues,
            "security_issues": security_issues,
            "metrics": static_results.get("aggregated", {}),
            "duration": round(duration, 2),
        }

    def _summarize_diff(self, files: List[Dict]) -> str:
        """Create a text summary of changed files for RAG retrieval."""
        summaries = []
        for f in files[:10]:
            filename = f.get("filename", "")
            status = f.get("status", "modified")
            additions = f.get("additions", 0)
            deletions = f.get("deletions", 0)
            summaries.append(f"{filename} ({status}: +{additions}/-{deletions})")
        return "Changed files:\n" + "\n".join(summaries)

    def _aggregate_issues(
        self,
        static_issues: List[Dict],
        security_issues: List[Dict],
        llm_issues: List[Dict],
    ) -> List[Dict]:
        """Merge and deduplicate issues from all analysis sources."""
        all_issues = []

        # Add static analysis issues
        for issue in static_issues:
            issue["source"] = "static"
            all_issues.append(issue)

        # Add security issues (convert to common format)
        for issue in security_issues:
            all_issues.append({
                "file_path": issue.get("file_path", ""),
                "line_number": issue.get("line_number"),
                "severity": issue.get("severity", "high"),
                "category": "security",
                "issue": issue.get("vulnerability_type", "Security Issue"),
                "explanation": issue.get("description", ""),
                "suggested_fix": issue.get("remediation", ""),
                "confidence": 0.85,
                "source": "security",
            })

        # Add LLM issues
        for issue in llm_issues:
            issue["source"] = issue.get("source", "llm")
            all_issues.append(issue)

        # Sort by severity priority
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
        all_issues.sort(key=lambda x: severity_order.get(x.get("severity", "info"), 5))

        return all_issues

    def _compute_quality_score(
        self, issues: List[Dict], static_results: Dict
    ) -> float:
        """Compute an overall quality score (0-100)."""
        score = 100.0

        # Deduct based on issue severity
        severity_deductions = {
            "critical": 15,
            "high": 10,
            "medium": 5,
            "low": 2,
            "info": 0.5,
        }

        for issue in issues:
            sev = issue.get("severity", "info")
            score -= severity_deductions.get(sev, 1)

        # Bonus for good maintainability
        aggregated = static_results.get("aggregated", {})
        maintainability = aggregated.get("avg_maintainability", 50)
        if maintainability > 70:
            score += 5
        elif maintainability < 30:
            score -= 10

        # Penalty for high complexity
        complexity = aggregated.get("avg_complexity", 5)
        if complexity > 15:
            score -= 10
        elif complexity > 10:
            score -= 5

        return max(0, min(100, round(score, 1)))

    async def _store_results(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        pr_data: Dict,
        all_issues: List[Dict],
        security_issues: List[Dict],
        static_results: Dict,
        quality_score: float,
        summary: str,
        duration: float,
    ) -> Optional[int]:
        """Persist analysis results to the database."""
        try:
            from database import async_session
            from models import (
                Repository, PullRequest, ReviewResult,
                ReviewComment, SecurityIssue, CodeMetrics, PRStatus,
            )
            from sqlalchemy import select

            async with async_session() as session:
                # Upsert repository
                result = await session.execute(
                    select(Repository).where(Repository.full_name == f"{owner}/{repo}")
                )
                repository = result.scalar_one_or_none()
                if not repository:
                    repository = Repository(
                        owner=owner, name=repo,
                        full_name=f"{owner}/{repo}",
                        github_url=f"https://github.com/{owner}/{repo}",
                        language=pr_data.get("base", {}).get("repo", {}).get("language"),
                    )
                    session.add(repository)
                    await session.flush()

                # Upsert pull request
                result = await session.execute(
                    select(PullRequest).where(
                        PullRequest.repository_id == repository.id,
                        PullRequest.pr_number == pr_number,
                    )
                )
                pr = result.scalar_one_or_none()
                if not pr:
                    pr = PullRequest(
                        pr_number=pr_number,
                        repository_id=repository.id,
                    )
                    session.add(pr)
                    await session.flush()

                pr.title = pr_data.get("title", "")
                pr.author = pr_data.get("user", {}).get("login", "")
                pr.state = pr_data.get("state", "open")
                pr.github_url = pr_data.get("html_url", "")
                pr.head_sha = pr_data.get("head", {}).get("sha", "")
                pr.base_branch = pr_data.get("base", {}).get("ref", "")
                pr.head_branch = pr_data.get("head", {}).get("ref", "")
                pr.files_changed = pr_data.get("changed_files", 0)
                pr.additions = pr_data.get("additions", 0)
                pr.deletions = pr_data.get("deletions", 0)
                pr.analysis_status = PRStatus.COMPLETED

                # Count severities
                severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
                for issue in all_issues:
                    sev = issue.get("severity", "info")
                    if sev in severity_counts:
                        severity_counts[sev] += 1

                # Create review result
                review = ReviewResult(
                    summary=summary,
                    quality_score=quality_score,
                    total_issues=len(all_issues),
                    critical_issues=severity_counts["critical"],
                    high_issues=severity_counts["high"],
                    medium_issues=severity_counts["medium"],
                    low_issues=severity_counts["low"],
                    analysis_duration=duration,
                    llm_provider=self.llm.provider,
                    llm_model=self.llm.model,
                    pull_request_id=pr.id,
                )
                session.add(review)
                await session.flush()

                # Store comments
                for issue in all_issues:
                    comment = ReviewComment(
                        file_path=issue.get("file_path", "unknown"),
                        line_number=issue.get("line_number"),
                        severity=issue.get("severity", "medium"),
                        category=issue.get("category", "bug"),
                        issue=issue.get("issue", ""),
                        explanation=issue.get("explanation", ""),
                        suggested_fix=issue.get("suggested_fix", ""),
                        code_snippet=issue.get("code_snippet", ""),
                        confidence=issue.get("confidence", 0.8),
                        source=issue.get("source", "llm"),
                        review_result_id=review.id,
                    )
                    session.add(comment)

                # Store security issues
                for si in security_issues:
                    sec_issue = SecurityIssue(
                        vulnerability_type=si.get("vulnerability_type", ""),
                        severity=si.get("severity", "high"),
                        file_path=si.get("file_path", ""),
                        line_number=si.get("line_number"),
                        description=si.get("description", ""),
                        remediation=si.get("remediation", ""),
                        cwe_id=si.get("cwe_id", ""),
                        owasp_category=si.get("owasp_category", ""),
                        code_snippet=si.get("code_snippet", ""),
                        review_result_id=review.id,
                    )
                    session.add(sec_issue)

                # Store code metrics
                for file_metrics in static_results.get("files", []):
                    metrics = CodeMetrics(
                        file_path=file_metrics.get("file_path", ""),
                        cyclomatic_complexity=file_metrics.get("cyclomatic_complexity", 0),
                        maintainability_index=file_metrics.get("maintainability_index", 0),
                        lines_of_code=file_metrics.get("lines_of_code", 0),
                        comment_ratio=file_metrics.get("comment_ratio", 0),
                        duplication_percentage=file_metrics.get("duplication_percentage", 0),
                        halstead_volume=file_metrics.get("halstead_volume", 0),
                        review_result_id=review.id,
                    )
                    session.add(metrics)

                await session.commit()
                return review.id

        except Exception as e:
            print(f"Error storing results: {e}")
            return None

    async def _post_github_comments(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        pr_data: Dict,
        issues: List[Dict],
        summary: str,
    ):
        """Post review comments back to the GitHub PR."""
        try:
            head_sha = pr_data.get("head", {}).get("sha", "")

            # Post summary comment
            await self.github.post_pr_comment(
                owner, repo, pr_number,
                f"🤖 **AI Code Review Assistant**\n\n{summary}"
            )

            # Post inline comments for top issues (limit to avoid spam)
            top_issues = [i for i in issues if i.get("severity") in ("critical", "high")][:10]

            for issue in top_issues:
                file_path = issue.get("file_path", "")
                line_number = issue.get("line_number", 1)
                severity = issue.get("severity", "medium").upper()
                emoji = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡"}.get(severity, "🔵")

                body = (
                    f"{emoji} **{severity}** — {issue.get('category', 'issue').upper()}\n\n"
                    f"**Issue:** {issue.get('issue', '')}\n\n"
                    f"**Explanation:** {issue.get('explanation', '')}\n\n"
                    f"**Suggested Fix:**\n```\n{issue.get('suggested_fix', '')}\n```"
                )

                if head_sha and file_path and line_number:
                    await self.github.post_review_comment(
                        owner, repo, pr_number,
                        body, head_sha, file_path, line_number,
                    )
        except Exception as e:
            print(f"Error posting GitHub comments: {e}")
