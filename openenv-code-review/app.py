"""
Gradio Demo App for Hugging Face Spaces.

Showcases the OpenEnv Code Review Agent:
  PR diff → Agent Review → Grading → Reward Score
"""

from __future__ import annotations

import json
import os
import sys

# Ensure local imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gradio as gr

from schemas import ReviewAction, ReviewIssue, Severity, Category
from environment import CodeReviewEnv
from agent import DemoAgent, ReviewAgent


# ────────────────────── Globals ────────────────────────────────

env = CodeReviewEnv()

# Use DemoAgent by default (no API key needed); switch to ReviewAgent if key present
HAS_API_KEY = bool(os.environ.get("OPENAI_API_KEY"))
agent = ReviewAgent() if HAS_API_KEY else DemoAgent()

SEVERITY_COLORS = {
    "critical": "🔴",
    "high": "🟠",
    "medium": "🟡",
    "low": "🔵",
    "info": "⚪",
}

SEVERITY_BADGE_CSS = {
    "critical": "background: linear-gradient(135deg, #dc2626, #b91c1c); color: white;",
    "high": "background: linear-gradient(135deg, #ea580c, #c2410c); color: white;",
    "medium": "background: linear-gradient(135deg, #d97706, #b45309); color: white;",
    "low": "background: linear-gradient(135deg, #2563eb, #1d4ed8); color: white;",
    "info": "background: linear-gradient(135deg, #6b7280, #4b5563); color: white;",
}


# ────────────────────── Core Logic ─────────────────────────────

def get_task_choices() -> list[str]:
    """Return human-readable task choices."""
    choices = []
    for tid in env.task_ids:
        title = env.get_task_title(tid)
        choices.append(f"{tid} — {title}")
    return choices


def run_review(task_choice: str, custom_diff: str) -> tuple:
    """
    Run the agent review pipeline.
    Returns: (diff_display, issues_html, grade_html, reward_display, gold_html, raw_json)
    """
    # Determine which task to use
    if custom_diff and custom_diff.strip():
        # Custom diff mode
        from schemas import ReviewObservation, GoldAnnotation
        obs = ReviewObservation(
            task_id="custom",
            diff=custom_diff.strip(),
            language="python",
            pr_description="Custom diff provided by user",
        )
        action = agent.review(obs)
        return (
            format_diff(custom_diff),
            format_issues(action.issues),
            "<p style='color:#94a3b8;'>⚠️ Grading unavailable for custom diffs (no gold standard)</p>",
            "N/A",
            "<p style='color:#94a3b8;'>No gold standard for custom input</p>",
            json.dumps(action.model_dump(), indent=2),
        )

    if not task_choice:
        return ("", "", "", "", "", "")

    # Extract task_id from choice string
    task_id = task_choice.split(" — ")[0].strip()

    # Reset environment with this task
    obs = env.reset(task_id=task_id)

    # Run agent
    action = agent.review(obs)

    # Step environment (grade the review)
    _, reward, _, info = env.step(action)

    grade = info["grade_result"]
    breakdown = grade["breakdown"]

    # Format outputs
    diff_display = format_diff(obs.diff)
    issues_html = format_issues(action.issues)
    grade_html = format_grade(breakdown, grade["feedback"])
    reward_display = format_reward(reward)
    gold_html = format_gold(env.current_gold)
    raw_json = json.dumps(action.model_dump(), indent=2)

    return (diff_display, issues_html, grade_html, reward_display, gold_html, raw_json)


# ────────────────────── Formatters ─────────────────────────────

def format_diff(diff: str) -> str:
    """Format diff with syntax highlighting."""
    lines = []
    for line in diff.split("\n"):
        if line.startswith("+") and not line.startswith("+++"):
            lines.append(f'<span style="color:#4ade80;background:#14532d22;">{_esc(line)}</span>')
        elif line.startswith("-") and not line.startswith("---"):
            lines.append(f'<span style="color:#f87171;background:#7f1d1d22;">{_esc(line)}</span>')
        elif line.startswith("@@"):
            lines.append(f'<span style="color:#60a5fa;">{_esc(line)}</span>')
        elif line.startswith("diff "):
            lines.append(f'<span style="color:#c084fc;font-weight:bold;">{_esc(line)}</span>')
        else:
            lines.append(f'<span style="color:#cbd5e1;">{_esc(line)}</span>')
    return f'<pre style="background:#0f172a;padding:16px;border-radius:12px;overflow-x:auto;font-family:\'JetBrains Mono\',monospace;font-size:13px;line-height:1.6;border:1px solid #1e293b;">{"<br>".join(lines)}</pre>'


def format_issues(issues: list[ReviewIssue]) -> str:
    """Format agent issues as styled HTML cards."""
    if not issues:
        return '<div style="text-align:center;padding:32px;color:#4ade80;font-size:18px;">✅ No issues found — clean code!</div>'

    cards = []
    for i, issue in enumerate(issues, 1):
        emoji = SEVERITY_COLORS.get(issue.severity.value, "⚪")
        badge_style = SEVERITY_BADGE_CSS.get(issue.severity.value, "")
        fix_html = ""
        if issue.suggested_fix:
            fix_html = f'<div style="margin-top:8px;padding:8px 12px;background:#1e293b;border-radius:8px;border-left:3px solid #4ade80;"><strong style="color:#4ade80;">💡 Fix:</strong> <span style="color:#e2e8f0;">{_esc(issue.suggested_fix)}</span></div>'

        cards.append(f"""
        <div style="background:#1e293b;border-radius:12px;padding:16px;margin-bottom:12px;border:1px solid #334155;">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">
                <span style="font-size:16px;">{emoji}</span>
                <span style="padding:2px 10px;border-radius:20px;font-size:12px;font-weight:600;{badge_style}">{issue.severity.value.upper()}</span>
                <span style="padding:2px 10px;border-radius:20px;font-size:12px;background:#334155;color:#94a3b8;">{issue.category.value}</span>
                <span style="color:#64748b;font-size:12px;margin-left:auto;">{issue.file}:{issue.line}</span>
            </div>
            <p style="color:#e2e8f0;margin:4px 0;font-size:14px;">{_esc(issue.description)}</p>
            {fix_html}
            <div style="margin-top:6px;"><span style="color:#64748b;font-size:11px;">Confidence: {issue.confidence:.0%}</span></div>
        </div>
        """)

    return f'<div>{"".join(cards)}</div>'


def format_grade(breakdown: dict, feedback: str) -> str:
    """Format grading breakdown as a styled dashboard."""
    metrics = [
        ("🎯 Recall", breakdown["recall"], "#4ade80"),
        ("🔍 Precision", breakdown["precision"], "#60a5fa"),
        ("⚖️ Severity Acc.", breakdown["severity_accuracy"], "#f59e0b"),
        ("💬 Feedback", breakdown["feedback_quality"], "#a78bfa"),
        ("📝 Summary", breakdown["summary_quality"], "#f472b6"),
    ]

    bars = []
    for label, val, color in metrics:
        pct = val * 100
        bars.append(f"""
        <div style="margin-bottom:8px;">
            <div style="display:flex;justify-content:space-between;margin-bottom:2px;">
                <span style="color:#e2e8f0;font-size:13px;">{label}</span>
                <span style="color:{color};font-weight:bold;font-size:13px;">{pct:.0f}%</span>
            </div>
            <div style="height:8px;background:#1e293b;border-radius:4px;overflow:hidden;">
                <div style="height:100%;width:{pct}%;background:{color};border-radius:4px;transition:width 0.5s;"></div>
            </div>
        </div>
        """)

    stats = f"""
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:12px;">
        <div style="text-align:center;padding:8px;background:#1e293b;border-radius:8px;">
            <div style="color:#4ade80;font-size:20px;font-weight:bold;">{breakdown['matched_issues']}</div>
            <div style="color:#64748b;font-size:11px;">Matched</div>
        </div>
        <div style="text-align:center;padding:8px;background:#1e293b;border-radius:8px;">
            <div style="color:#f87171;font-size:20px;font-weight:bold;">{breakdown['missed_issues']}</div>
            <div style="color:#64748b;font-size:11px;">Missed</div>
        </div>
        <div style="text-align:center;padding:8px;background:#1e293b;border-radius:8px;">
            <div style="color:#fbbf24;font-size:20px;font-weight:bold;">{breakdown['false_positives']}</div>
            <div style="color:#64748b;font-size:11px;">False +</div>
        </div>
    </div>
    """

    feedback_html = f'<p style="color:#94a3b8;font-size:12px;margin-top:12px;padding:8px;background:#0f172a;border-radius:8px;">{_esc(feedback)}</p>'

    return f'<div style="background:#0f172a;padding:16px;border-radius:12px;border:1px solid #1e293b;">{"".join(bars)}{stats}{feedback_html}</div>'


def format_reward(reward: float) -> str:
    """Format reward as a big styled number."""
    color = "#4ade80" if reward >= 0.7 else "#fbbf24" if reward >= 0.4 else "#f87171"
    return f"""
    <div style="text-align:center;padding:24px;background:linear-gradient(135deg,#0f172a,#1e293b);border-radius:16px;border:2px solid {color};">
        <div style="font-size:48px;font-weight:bold;color:{color};text-shadow:0 0 20px {color}40;">{reward:.2f}</div>
        <div style="color:#94a3b8;font-size:14px;margin-top:4px;">Reward Score</div>
        <div style="color:{color};font-size:12px;margin-top:2px;">{"🏆 Excellent" if reward >= 0.8 else "✅ Good" if reward >= 0.6 else "⚠️ Needs Work" if reward >= 0.3 else "❌ Poor"}</div>
    </div>
    """


def format_gold(gold) -> str:
    """Format gold standard annotations."""
    if gold is None:
        return ""
    if not gold.issues:
        return '<div style="text-align:center;padding:16px;color:#4ade80;">✅ Gold Standard: No issues expected (clean PR)</div>'

    items = []
    for gi in gold.issues:
        emoji = SEVERITY_COLORS.get(gi.severity.value, "⚪")
        items.append(f"""
        <div style="padding:10px;background:#1e293b;border-radius:8px;margin-bottom:8px;border-left:3px solid #6366f1;">
            <span>{emoji} <strong style="color:#e2e8f0;">[{gi.severity.value.upper()}]</strong></span>
            <span style="color:#94a3b8;"> {gi.file}:{gi.line}</span>
            <p style="color:#cbd5e1;margin:4px 0 0;font-size:13px;">{_esc(gi.description)}</p>
        </div>
        """)
    return f'<div>{"".join(items)}</div>'


def _esc(text: str) -> str:
    """Escape HTML special characters."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# ────────────────────── Gradio UI ──────────────────────────────

CUSTOM_CSS = """
.gradio-container {
    background: linear-gradient(180deg, #0a0f1a 0%, #111827 100%) !important;
    font-family: 'Inter', -apple-system, sans-serif !important;
}
.dark {
    background: #0a0f1a !important;
}
#title-block {
    text-align: center;
    padding: 20px 0;
}
.gr-button-primary {
    background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
    border: none !important;
    font-weight: 600 !important;
    font-size: 16px !important;
    padding: 12px 32px !important;
    border-radius: 12px !important;
    transition: all 0.3s ease !important;
}
.gr-button-primary:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 25px rgba(99, 102, 241, 0.4) !important;
}
"""

def build_app() -> gr.Blocks:
    """Build the Gradio interface."""
    with gr.Blocks(
        title="🤖 OpenEnv Code Review Agent",
        css=CUSTOM_CSS,
        theme=gr.themes.Base(
            primary_hue="indigo",
            secondary_hue="slate",
            neutral_hue="slate",
            font=gr.themes.GoogleFont("Inter"),
        ),
    ) as app:
        # Header
        gr.HTML("""
        <div id="title-block">
            <h1 style="color:#e2e8f0;font-size:32px;margin:0;">
                🤖 OpenEnv Code Review Agent
            </h1>
            <p style="color:#94a3b8;font-size:16px;margin:8px 0 0;">
                Gymnasium-compatible environment for AI-powered pull request review
            </p>
            <p style="color:#64748b;font-size:13px;margin:4px 0 0;">
                Meta PyTorch OpenEnv Hackathon · reset() → step() → reward
            </p>
        </div>
        """)

        with gr.Row():
            with gr.Column(scale=1):
                task_dropdown = gr.Dropdown(
                    choices=get_task_choices(),
                    label="📋 Select Task",
                    info="Choose a predefined PR review task",
                )
                custom_diff = gr.Textbox(
                    label="📝 Or Paste Custom Diff",
                    placeholder="Paste a unified diff here (optional)...",
                    lines=4,
                )
                agent_mode = gr.HTML(
                    f'<p style="color:#64748b;font-size:12px;padding:4px;">Agent: {"🤖 GPT-4o (live)" if HAS_API_KEY else "🎭 Demo mode (deterministic)"}</p>'
                )
                run_btn = gr.Button(
                    "🚀 Run Review",
                    variant="primary",
                    size="lg",
                )

            with gr.Column(scale=1):
                reward_output = gr.HTML(label="🏆 Reward Score")

        with gr.Tabs():
            with gr.TabItem("📄 PR Diff"):
                diff_output = gr.HTML()

            with gr.TabItem("🔍 Agent Review"):
                issues_output = gr.HTML()

            with gr.TabItem("📊 Grading"):
                grade_output = gr.HTML()

            with gr.TabItem("🎯 Gold Standard"):
                gold_output = gr.HTML()

            with gr.TabItem("🔧 Raw JSON"):
                json_output = gr.Code(language="json", label="Agent Output (JSON)")

        # Wire up
        run_btn.click(
            fn=run_review,
            inputs=[task_dropdown, custom_diff],
            outputs=[diff_output, issues_output, grade_output, reward_output, gold_output, json_output],
        )

        # Footer
        gr.HTML("""
        <div style="text-align:center;padding:20px;color:#475569;font-size:12px;border-top:1px solid #1e293b;margin-top:20px;">
            OpenEnv Code Review Agent · Built for Meta PyTorch OpenEnv Hackathon
            · Environment: reset() → step(action) → (obs, reward, done, info)
        </div>
        """)

    return app


# ────────────────────── Entry Point ────────────────────────────

if __name__ == "__main__":
    app = build_app()
    app.launch(
        server_name="0.0.0.0",
        server_port=int(os.environ.get("PORT", 7860)),
        share=False,
    )
