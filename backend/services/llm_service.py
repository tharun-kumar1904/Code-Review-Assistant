"""
LLM integration service.
Supports OpenAI, Claude, and Gemini for code analysis.
"""

import json
from typing import List, Dict, Any
from config import get_settings

settings = get_settings()


# ── Prompt Templates ─────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert code reviewer with deep knowledge of software engineering
best practices, security vulnerabilities, performance optimization, and clean code principles.

You analyze code changes from GitHub pull requests and provide structured, actionable feedback.

For each issue you find, you must provide:
1. The specific issue identified
2. The severity level (critical, high, medium, low, info)
3. The category (bug, security, performance, style, logic, design, documentation)
4. A clear explanation of WHY this is an issue
5. A concrete suggested fix with code
6. The file path and approximate line number
7. A confidence score between 0 and 1

Focus on finding real, impactful issues. Avoid trivial style nitpicks unless they
indicate a deeper problem. Prioritize security vulnerabilities and bugs."""

ANALYSIS_PROMPT = """Analyze the following code changes from a pull request.

## Repository Context
{context}

## Changed Files
{files}

## Instructions
Review the code changes carefully and identify:
- Potential bugs and logic errors
- Security vulnerabilities (SQL injection, XSS, hardcoded secrets, etc.)
- Performance issues (N+1 queries, unnecessary computations, memory leaks)
- Code quality issues (complexity, readability, maintainability)
- Design problems (tight coupling, missing error handling, race conditions)

Return your analysis as a JSON array of issues. Each issue must follow this schema:
```json
[
  {{
    "file_path": "path/to/file.py",
    "line_number": 42,
    "severity": "high",
    "category": "security",
    "issue": "SQL Injection vulnerability",
    "explanation": "User input is directly interpolated into the SQL query string without parameterization, allowing an attacker to execute arbitrary SQL commands.",
    "suggested_fix": "Use parameterized queries: cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))",
    "confidence": 0.95
  }}
]
```

Return ONLY the JSON array, no additional text."""


class LLMService:
    """Multi-provider LLM service for code analysis."""

    def __init__(self):
        self.provider = settings.LLM_PROVIDER
        self.model = settings.LLM_MODEL

    async def analyze_code(
        self,
        files: List[Dict[str, Any]],
        context: str = "",
    ) -> List[Dict[str, Any]]:
        """
        Analyze code changes using the configured LLM provider.
        Returns structured list of issues found.
        """
        # Format files for prompt
        files_text = self._format_files(files)

        prompt = ANALYSIS_PROMPT.format(
            context=context or "No additional context available.",
            files=files_text,
        )

        # Call the appropriate LLM provider
        if self.provider == "openai":
            response = await self._call_openai(prompt)
        elif self.provider == "claude":
            response = await self._call_claude(prompt)
        elif self.provider == "gemini":
            response = await self._call_gemini(prompt)
        else:
            response = await self._call_openai(prompt)

        # Parse structured output
        return self._parse_response(response)

    def _format_files(self, files: List[Dict[str, Any]]) -> str:
        """Format changed files for the LLM prompt."""
        formatted = []
        for f in files:
            filename = f.get("filename", "unknown")
            patch = f.get("patch", "")
            status = f.get("status", "modified")
            formatted.append(
                f"### File: {filename} (Status: {status})\n"
                f"```diff\n{patch}\n```\n"
            )
        return "\n".join(formatted)

    async def _call_openai(self, prompt: str) -> str:
        """Call OpenAI API."""
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        response = await client.chat.completions.create(
            model=self.model or "gpt-4o",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=4096,
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content

    async def _call_claude(self, prompt: str) -> str:
        """Call Anthropic Claude API."""
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        response = await client.messages.create(
            model=self.model or "claude-3-5-sonnet-20241022",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

    async def _call_gemini(self, prompt: str) -> str:
        """Call Google Gemini API."""
        import google.generativeai as genai

        genai.configure(api_key=settings.GOOGLE_API_KEY)
        model = genai.GenerativeModel(
            self.model or "gemini-2.5-flash",
            system_instruction=SYSTEM_PROMPT,
        )
        response = await model.generate_content_async(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=0.1,
                max_output_tokens=4096,
            ),
        )
        return response.text

    def _parse_response(self, response: str) -> List[Dict[str, Any]]:
        """Parse LLM response into structured issue list."""
        try:
            # Try direct JSON parse
            data = json.loads(response)
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "issues" in data:
                return data["issues"]
            return [data] if isinstance(data, dict) else []
        except json.JSONDecodeError:
            # Extract JSON from markdown code blocks
            import re
            json_match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', response, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    pass
            # Try finding array in response
            array_match = re.search(r'\[.*\]', response, re.DOTALL)
            if array_match:
                try:
                    return json.loads(array_match.group(0))
                except json.JSONDecodeError:
                    pass
        return []

    async def generate_summary(self, issues: List[Dict], pr_info: Dict) -> str:
        """Generate a human-readable review summary."""
        if not issues:
            return "✅ No significant issues found. The code changes look good!"

        severity_counts = {}
        for issue in issues:
            sev = issue.get("severity", "info")
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

        summary_lines = [
            "## Code Review Summary",
            "",
            f"**Total issues found:** {len(issues)}",
        ]

        for sev in ["critical", "high", "medium", "low", "info"]:
            if sev in severity_counts:
                emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵", "info": "ℹ️"}.get(sev, "")
                summary_lines.append(f"- {emoji} **{sev.upper()}**: {severity_counts[sev]}")

        return "\n".join(summary_lines)
