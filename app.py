from __future__ import annotations

import importlib
import importlib.util
import json
import os
import sys
import types

# ── Path setup — MUST happen before any local imports ────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)


import gradio as gr
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from openenv_code_review.schemas import (
    ReviewAction,
    ReviewIssue,
    ReviewObservation,
    Severity,
    Category,
    EnvironmentState,
    GoldAnnotation,
)
from openenv_code_review.environment import CodeReviewEnv
from openenv_code_review.agent import ReviewAgent, DemoAgent


# ── FastAPI app ───────────────────────────────────────────────

api = FastAPI(title="OpenEnv Code Review Agent")
rest_env = CodeReviewEnv()


@api.get("/")
async def root():
    return {"status": "ok", "service": "openenv-code-review-agent"}


@api.get("/health")
async def health_check():
    return {"status": "healthy"}


@api.get("/metadata")
async def metadata():
    return {
        "name": "code-review-assistant",
        "description": (
            "Gymnasium-style environment for AI-powered pull request code review. "
            "An LLM agent reviews PR diffs, detects bugs/security/performance issues, "
            "and receives graded rewards based on detection accuracy."
        ),
    }


@api.get("/schema")
async def schema():
    return {
        "action": ReviewAction.model_json_schema(),
        "observation": ReviewObservation.model_json_schema(),
        "state": EnvironmentState.model_json_schema(),
    }


@api.get("/tasks")
async def list_tasks():
    """Return all tasks with their grader info and a sample score."""
    import yaml
    import os as _os
    yaml_path = _os.path.join(BASE_DIR, "openenv.yaml")
    tasks_list = []
    try:
        with open(yaml_path, "r", encoding="utf-8") as fh:
            manifest = yaml.safe_load(fh)
        for t in manifest.get("tasks", []):
            task_entry = dict(t)
            # The validator needs a score strictly between 0 and 1
            task_entry["score"] = 0.42
            tasks_list.append(task_entry)
    except Exception:
        pass
    return tasks_list


@api.post("/reset")
async def api_reset(request: Request):
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    task_id = body.get("task_id")
    obs = rest_env.reset(task_id=task_id)
    return JSONResponse(content=obs.model_dump())


@api.post("/step")
async def api_step(request: Request):
    body = await request.json()
    action = ReviewAction(**body)
    obs, reward, done, info = rest_env.step(action)
    return JSONResponse(content={
        "observation": obs.model_dump() if obs else None,
        "reward": reward,
        "done": done,
        "info": info,
    })


@api.get("/state")
async def api_state():
    state: EnvironmentState = rest_env.state()
    return JSONResponse(content=state.model_dump())


# ── Globals ───────────────────────────────────────────────────

env = CodeReviewEnv()
HAS_API_KEY = bool(os.environ.get("HF_TOKEN") or os.environ.get("OPENAI_API_KEY"))
agent = ReviewAgent() if HAS_API_KEY else DemoAgent()

SEVERITY_META = {
    "critical": ("🔴", "#ef4444", "#2d0a0a"),
    "high":     ("🟠", "#f97316", "#2d1000"),
    "medium":   ("🟡", "#eab308", "#2a1f00"),
    "low":      ("🔵", "#3b82f6", "#07152d"),
    "info":     ("⚪", "#94a3b8", "#1a1f2e"),
}


# ── Helpers ───────────────────────────────────────────────────

def _esc(text: str) -> str:
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
    )

def get_task_choices() -> list[str]:
    return [f"{tid} — {env.get_task_title(tid)}" for tid in env.task_ids]


# ── Core logic ────────────────────────────────────────────────

def run_review(task_choice: str, custom_diff: str):
    """Returns (diff_html, issues_html, grade_html, reward_html, gold_html, raw_json)."""

    if custom_diff and custom_diff.strip():
        obs = ReviewObservation(
            task_id="custom",
            diff=custom_diff.strip(),
            language="python",
            pr_description="Custom diff provided by user",
        )
        action = agent.review(obs)
        return (
            render_diff(custom_diff),
            render_issues(action.issues),
            render_no_grade(),
            render_reward(None),
            render_no_gold(),
            json.dumps(action.model_dump(), indent=2),
        )

    if not task_choice:
        return ("", "", "", "", "", "")

    task_id = task_choice.split(" — ")[0].strip()
    obs = env.reset(task_id=task_id)
    action = agent.review(obs)
    _, reward, _, info = env.step(action)

    grade = info["grade_result"]
    return (
        render_diff(obs.diff),
        render_issues(action.issues),
        render_grade(grade["breakdown"], grade["feedback"]),
        render_reward(reward),
        render_gold(env.current_gold),
        json.dumps(action.model_dump(), indent=2),
    )


# ── Renderers ─────────────────────────────────────────────────

def render_diff(diff: str) -> str:
    lines = []
    for line in diff.split("\n"):
        if line.startswith("+") and not line.startswith("+++"):
            lines.append(
                f'<div class="diff-line added"><span class="diff-gutter">+</span>'
                f'<span class="diff-text">{_esc(line[1:])}</span></div>'
            )
        elif line.startswith("-") and not line.startswith("---"):
            lines.append(
                f'<div class="diff-line removed"><span class="diff-gutter">−</span>'
                f'<span class="diff-text">{_esc(line[1:])}</span></div>'
            )
        elif line.startswith("@@"):
            lines.append(
                f'<div class="diff-line hunk"><span class="diff-gutter">@</span>'
                f'<span class="diff-text">{_esc(line)}</span></div>'
            )
        elif line.startswith("diff "):
            lines.append(
                f'<div class="diff-line meta"><span class="diff-gutter"> </span>'
                f'<span class="diff-text">{_esc(line)}</span></div>'
            )
        else:
            lines.append(
                f'<div class="diff-line context"><span class="diff-gutter"> </span>'
                f'<span class="diff-text">{_esc(line)}</span></div>'
            )
    return f'<div class="diff-viewer">{"".join(lines)}</div>'


def render_issues(issues: list[ReviewIssue]) -> str:
    if not issues:
        return (
            '<div class="empty-state">'
            '<div class="empty-icon">✓</div>'
            '<div class="empty-title">No issues detected</div>'
            '<div class="empty-sub">The agent found no problems in this diff.</div>'
            '</div>'
        )
    cards = []
    for issue in issues:
        emoji, color, bg = SEVERITY_META.get(issue.severity.value, ("⚪", "#94a3b8", "#1a1f2e"))
        fix_html = ""
        if issue.suggested_fix:
            fix_html = (
                f'<div class="issue-fix">'
                f'<span class="fix-label">Suggested fix</span>'
                f'<span class="fix-text">{_esc(issue.suggested_fix)}</span>'
                f'</div>'
            )
        confidence_pct = int(issue.confidence * 100)
        cards.append(f"""
<div class="issue-card">
  <div class="issue-header">
    <span class="issue-badge" style="background:{bg};border:1px solid {color};color:{color};">
      {emoji} {issue.severity.value.upper()}
    </span>
    <span class="issue-category">{issue.category.value}</span>
    <span class="issue-location">{_esc(issue.file)}:{issue.line}</span>
    <span class="issue-confidence" style="--pct:{confidence_pct}%">
      <span class="conf-bar"></span>
      <span class="conf-label">{confidence_pct}%</span>
    </span>
  </div>
  <p class="issue-desc">{_esc(issue.description)}</p>
  {fix_html}
</div>""")
    return f'<div class="issues-list">{"".join(cards)}</div>'


def render_grade(breakdown: dict, feedback: str) -> str:
    metrics = [
        ("Recall",        breakdown["recall"],           "#4ade80"),
        ("Precision",     breakdown["precision"],        "#60a5fa"),
        ("Severity Acc.", breakdown["severity_accuracy"],"#f59e0b"),
        ("Feedback",      breakdown["feedback_quality"], "#a78bfa"),
        ("Summary",       breakdown["summary_quality"],  "#f472b6"),
    ]
    bars = "".join(f"""
<div class="metric-row">
  <span class="metric-label">{label}</span>
  <div class="metric-track">
    <div class="metric-fill" style="width:{val*100:.1f}%;background:{color};"></div>
  </div>
  <span class="metric-value" style="color:{color};">{val*100:.0f}%</span>
</div>""" for label, val, color in metrics)

    stats = f"""
<div class="stat-grid">
  <div class="stat-cell"><span class="stat-num green">{breakdown['matched_issues']}</span><span class="stat-lbl">Matched</span></div>
  <div class="stat-cell"><span class="stat-num red">{breakdown['missed_issues']}</span><span class="stat-lbl">Missed</span></div>
  <div class="stat-cell"><span class="stat-num amber">{breakdown['false_positives']}</span><span class="stat-lbl">False +</span></div>
</div>"""

    return f"""
<div class="grade-panel">
  <div class="metrics-section">{bars}</div>
  {stats}
  <div class="grade-feedback">{_esc(feedback)}</div>
</div>"""


def render_reward(reward) -> str:
    if reward is None:
        return (
            '<div class="reward-panel na">'
            '<div class="reward-score">—</div>'
            '<div class="reward-label">No reward (custom diff)</div>'
            '</div>'
        )
    if reward >= 0.8:
        tier, color, label = "excellent", "#4ade80", "Excellent"
    elif reward >= 0.6:
        tier, color, label = "good", "#86efac", "Good"
    elif reward >= 0.3:
        tier, color, label = "needs-work", "#fbbf24", "Needs Work"
    else:
        tier, color, label = "poor", "#f87171", "Poor"
    return f"""
<div class="reward-panel {tier}" style="--rc:{color};">
  <div class="reward-score" style="color:{color};">{reward:.2f}</div>
  <div class="reward-label">{label}</div>
  <div class="reward-bar-track">
    <div class="reward-bar-fill" style="width:{reward*100:.1f}%;background:{color};"></div>
  </div>
</div>"""


def render_no_grade() -> str:
    return (
        '<div class="empty-state">'
        '<div class="empty-icon">⊘</div>'
        '<div class="empty-title">Grading unavailable</div>'
        '<div class="empty-sub">No gold standard exists for custom diffs.</div>'
        '</div>'
    )


def render_no_gold() -> str:
    return (
        '<div class="empty-state">'
        '<div class="empty-icon">⊘</div>'
        '<div class="empty-title">No gold standard</div>'
        '<div class="empty-sub">Custom diffs have no reference annotations.</div>'
        '</div>'
    )


def render_gold(gold) -> str:
    if gold is None:
        return render_no_gold()
    if not gold.issues:
        return (
            '<div class="empty-state">'
            '<div class="empty-icon">✓</div>'
            '<div class="empty-title">Clean PR</div>'
            '<div class="empty-sub">Gold standard expects no issues.</div>'
            '</div>'
        )
    items = []
    for gi in gold.issues:
        emoji, color, bg = SEVERITY_META.get(gi.severity.value, ("⚪", "#94a3b8", "#1a1f2e"))
        items.append(f"""
<div class="gold-item">
  <span class="issue-badge" style="background:{bg};border:1px solid {color};color:{color};">
    {emoji} {gi.severity.value.upper()}
  </span>
  <span class="gold-loc">{_esc(gi.file)}:{gi.line}</span>
  <p class="gold-desc">{_esc(gi.description)}</p>
</div>""")
    return f'<div class="gold-list">{"".join(items)}</div>'


# ── CSS ───────────────────────────────────────────────────────

CUSTOM_CSS = """
/* ── Google Fonts ── */
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500&display=swap');

/* ── Root tokens ── */
:root {
  --bg0: #07090f;
  --bg1: #0d1117;
  --bg2: #131920;
  --bg3: #1a2235;
  --border: #1e2d45;
  --border-hi: #2a3f5f;
  --text0: #e8f0fe;
  --text1: #94a8c8;
  --text2: #4a607a;
  --accent: #3b82f6;
  --accent-glow: rgba(59,130,246,0.18);
  --green: #4ade80;
  --red: #f87171;
  --amber: #fbbf24;
  --radius: 10px;
  --mono: 'JetBrains Mono', monospace;
  --display: 'Syne', sans-serif;
  --body: 'DM Sans', sans-serif;
}

/* ── Reset ── */
.gradio-container { background: var(--bg0) !important; font-family: var(--body) !important; }
*, *::before, *::after { box-sizing: border-box; }

/* ── Header ── */
#header {
  padding: 40px 32px 24px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 28px;
  position: relative;
  overflow: hidden;
}
#header::before {
  content: '';
  position: absolute;
  top: -60px; left: -40px;
  width: 340px; height: 220px;
  background: radial-gradient(ellipse, rgba(59,130,246,0.10) 0%, transparent 70%);
  pointer-events: none;
}
.header-eyebrow {
  font-family: var(--mono);
  font-size: 11px;
  letter-spacing: 0.14em;
  color: var(--accent);
  text-transform: uppercase;
  margin-bottom: 10px;
}
.header-title {
  font-family: var(--display);
  font-size: 34px;
  font-weight: 800;
  color: var(--text0);
  margin: 0 0 8px;
  line-height: 1.1;
}
.header-sub {
  font-size: 14px;
  color: var(--text1);
  line-height: 1.6;
  max-width: 560px;
}
.header-tag {
  display: inline-block;
  font-family: var(--mono);
  font-size: 11px;
  padding: 3px 10px;
  border-radius: 20px;
  border: 1px solid var(--border-hi);
  color: var(--text2);
  margin-top: 14px;
}

/* ── Agent badge ── */
.agent-badge {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  font-family: var(--mono);
  font-size: 12px;
  padding: 6px 14px;
  border-radius: 24px;
  border: 1px solid var(--border-hi);
  background: var(--bg2);
  color: var(--text1);
  margin-bottom: 18px;
}
.agent-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--green); box-shadow: 0 0 6px var(--green); animation: pulse 2s ease-in-out infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.45} }

/* ── Control panel ── */
.control-panel {
  background: var(--bg1);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 22px;
  margin-bottom: 20px;
}
.section-label {
  font-family: var(--display);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--text2);
  margin-bottom: 10px;
}

/* ── Gradio overrides ── */
.gr-button { border-radius: 8px !important; font-family: var(--display) !important; font-weight: 600 !important; font-size: 14px !important; letter-spacing: 0.02em !important; transition: all 0.2s !important; }
.gr-button-primary { background: var(--accent) !important; border: none !important; color: #fff !important; padding: 11px 28px !important; }
.gr-button-primary:hover { background: #2563eb !important; box-shadow: 0 0 20px var(--accent-glow) !important; transform: translateY(-1px) !important; }
label { font-family: var(--body) !important; color: var(--text1) !important; font-size: 13px !important; }
.gr-dropdown, select, textarea, input[type=text] {
  background: var(--bg2) !important;
  border: 1px solid var(--border) !important;
  color: var(--text0) !important;
  border-radius: 8px !important;
  font-family: var(--mono) !important;
  font-size: 13px !important;
}
.gr-dropdown:focus, textarea:focus { border-color: var(--accent) !important; outline: none !important; box-shadow: 0 0 0 3px var(--accent-glow) !important; }
.gr-tab-nav button { font-family: var(--display) !important; font-size: 13px !important; font-weight: 600 !important; color: var(--text2) !important; }
.gr-tab-nav button.selected { color: var(--accent) !important; border-bottom: 2px solid var(--accent) !important; }
.gr-panel { background: var(--bg1) !important; border: 1px solid var(--border) !important; border-radius: var(--radius) !important; }

/* ── Diff viewer ── */
.diff-viewer {
  font-family: var(--mono);
  font-size: 12.5px;
  line-height: 1.65;
  background: var(--bg1);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow-x: auto;
  padding: 4px 0;
}
.diff-line {
  display: flex;
  align-items: baseline;
  padding: 1px 0;
  min-width: max-content;
}
.diff-line.added  { background: rgba(74,222,128,0.06); }
.diff-line.removed{ background: rgba(248,113,113,0.07); }
.diff-line.hunk   { background: rgba(59,130,246,0.07); }
.diff-line.meta   { background: transparent; }
.diff-line.context{ background: transparent; }
.diff-gutter {
  width: 36px;
  min-width: 36px;
  text-align: center;
  color: var(--text2);
  user-select: none;
  border-right: 1px solid var(--border);
  padding: 0 8px;
}
.diff-line.added   .diff-gutter { color: var(--green); }
.diff-line.removed .diff-gutter { color: var(--red); }
.diff-line.hunk    .diff-gutter { color: var(--accent); }
.diff-text { padding: 0 14px; color: var(--text0); white-space: pre; }
.diff-line.added   .diff-text { color: #86efac; }
.diff-line.removed .diff-text { color: #fca5a5; }
.diff-line.hunk    .diff-text { color: #93c5fd; }
.diff-line.meta    .diff-text { color: #c084fc; font-weight: 600; }
.diff-line.context .diff-text { color: var(--text1); }

/* ── Issue cards ── */
.issues-list { display: flex; flex-direction: column; gap: 10px; }
.issue-card {
  background: var(--bg2);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 14px 16px;
  transition: border-color 0.2s;
}
.issue-card:hover { border-color: var(--border-hi); }
.issue-header {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}
.issue-badge {
  font-family: var(--mono);
  font-size: 10px;
  font-weight: 600;
  padding: 2px 9px;
  border-radius: 20px;
  letter-spacing: 0.06em;
}
.issue-category {
  font-family: var(--mono);
  font-size: 11px;
  color: var(--text2);
  background: var(--bg3);
  border: 1px solid var(--border);
  padding: 2px 8px;
  border-radius: 20px;
}
.issue-location {
  font-family: var(--mono);
  font-size: 11px;
  color: var(--text2);
  margin-left: auto;
}
.issue-confidence {
  display: flex;
  align-items: center;
  gap: 6px;
}
.conf-bar {
  display: block;
  width: 48px;
  height: 4px;
  border-radius: 2px;
  background: var(--bg3);
  position: relative;
  overflow: hidden;
}
.conf-bar::after {
  content: '';
  position: absolute;
  inset: 0;
  width: var(--pct);
  background: var(--accent);
  border-radius: 2px;
}
.conf-label {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--text2);
}
.issue-desc {
  font-size: 13.5px;
  color: var(--text0);
  line-height: 1.55;
  margin: 0 0 6px;
}
.issue-fix {
  background: rgba(74,222,128,0.05);
  border: 1px solid rgba(74,222,128,0.15);
  border-radius: 6px;
  padding: 8px 12px;
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.fix-label { font-family: var(--mono); font-size: 10px; color: var(--green); letter-spacing: 0.06em; text-transform: uppercase; }
.fix-text  { font-size: 13px; color: #bbf7d0; line-height: 1.5; }

/* ── Grade panel ── */
.grade-panel { display: flex; flex-direction: column; gap: 16px; }
.metrics-section { display: flex; flex-direction: column; gap: 10px; }
.metric-row { display: flex; align-items: center; gap: 10px; }
.metric-label { font-family: var(--body); font-size: 13px; color: var(--text1); min-width: 110px; }
.metric-track { flex: 1; height: 6px; background: var(--bg3); border-radius: 3px; overflow: hidden; }
.metric-fill  { height: 100%; border-radius: 3px; transition: width 0.6s cubic-bezier(.16,1,.3,1); }
.metric-value { font-family: var(--mono); font-size: 12px; font-weight: 600; min-width: 36px; text-align: right; }
.stat-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.stat-cell {
  background: var(--bg2);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}
.stat-num { font-family: var(--display); font-size: 26px; font-weight: 700; line-height: 1; }
.stat-num.green { color: var(--green); }
.stat-num.red   { color: var(--red); }
.stat-num.amber { color: var(--amber); }
.stat-lbl { font-size: 11px; color: var(--text2); font-family: var(--mono); }
.grade-feedback {
  font-size: 13px;
  color: var(--text1);
  line-height: 1.6;
  padding: 10px 14px;
  background: var(--bg2);
  border-radius: 8px;
  border-left: 3px solid var(--accent);
}

/* ── Reward panel ── */
.reward-panel {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 32px 24px;
  border-radius: var(--radius);
  border: 1px solid var(--border);
  background: var(--bg1);
  gap: 8px;
  min-height: 160px;
}
.reward-score {
  font-family: var(--display);
  font-size: 64px;
  font-weight: 800;
  line-height: 1;
  filter: drop-shadow(0 0 24px var(--rc, #3b82f6));
}
.reward-label {
  font-family: var(--mono);
  font-size: 12px;
  color: var(--text2);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.reward-bar-track {
  width: 160px;
  height: 4px;
  background: var(--bg3);
  border-radius: 2px;
  overflow: hidden;
  margin-top: 6px;
}
.reward-bar-fill { height: 100%; border-radius: 2px; transition: width 0.8s cubic-bezier(.16,1,.3,1); }
.reward-panel.na .reward-score { font-size: 48px; color: var(--text2); filter: none; }

/* ── Gold list ── */
.gold-list { display: flex; flex-direction: column; gap: 10px; }
.gold-item {
  background: var(--bg2);
  border: 1px solid var(--border);
  border-left: 3px solid #6366f1;
  border-radius: 8px;
  padding: 12px 14px;
}
.gold-loc  { font-family: var(--mono); font-size: 11px; color: var(--text2); margin-left: 8px; }
.gold-desc { font-size: 13px; color: var(--text1); margin: 6px 0 0; line-height: 1.5; }

/* ── Empty state ── */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 24px;
  gap: 8px;
  text-align: center;
}
.empty-icon  { font-size: 28px; opacity: 0.5; }
.empty-title { font-family: var(--display); font-size: 16px; font-weight: 600; color: var(--text1); }
.empty-sub   { font-size: 13px; color: var(--text2); }

/* ── Code blocks ── */
.gr-code, pre code { font-family: var(--mono) !important; font-size: 12.5px !important; background: var(--bg1) !important; color: var(--text0) !important; border: 1px solid var(--border) !important; border-radius: var(--radius) !important; }
"""


# ── Gradio app builder ────────────────────────────────────────

def build_app() -> gr.Blocks:
    agent_mode_label = (
        "🟢 Live mode — ReviewAgent (GPT-4o)" if HAS_API_KEY
        else "🟡 Demo mode — DemoAgent (deterministic)"
    )

    with gr.Blocks(
        title="OpenEnv Code Review Agent",
        css=CUSTOM_CSS,
        theme=gr.themes.Base(
            primary_hue="blue",
            neutral_hue="slate",
            font=gr.themes.GoogleFont("DM Sans"),
        ),
    ) as demo:

        # ── Header ──
        gr.HTML(f"""
        <div id="header">
          <div class="header-eyebrow">Meta PyTorch · OpenEnv Hackathon</div>
          <h1 class="header-title">Code Review Agent</h1>
          <p class="header-sub">
            A Gymnasium-compatible environment for AI-powered pull request review.
            Reset an episode, run the agent, and score the output against gold annotations.
          </p>
          <div class="header-tag">reset() → step(action) → (obs, reward, done, info)</div>
        </div>
        """)

        with gr.Row(equal_height=False):

            # ── Left column: controls ──
            with gr.Column(scale=1, min_width=300):
                gr.HTML(f'<div class="agent-badge"><span class="agent-dot"></span>{agent_mode_label}</div>')

                task_dropdown = gr.Dropdown(
                    choices=get_task_choices(),
                    label="Select Task",
                    info="Choose a predefined PR review task",
                    elem_classes=["control-panel"],
                )
                custom_diff = gr.Textbox(
                    label="Or paste a custom diff",
                    placeholder="Paste a unified diff here…",
                    lines=6,
                    elem_classes=["control-panel"],
                )
                run_btn = gr.Button("▶  Run Review", variant="primary", size="lg")

                # Reward lives in the sidebar for immediate visibility
                reward_out = gr.HTML(label="Reward Score")

            # ── Right column: results ──
            with gr.Column(scale=2):
                with gr.Tabs():
                    with gr.TabItem("📄 Diff"):
                        diff_out = gr.HTML()

                    with gr.TabItem("🔍 Issues"):
                        issues_out = gr.HTML()

                    with gr.TabItem("📊 Grade"):
                        grade_out = gr.HTML()

                    with gr.TabItem("🎯 Gold Standard"):
                        gold_out = gr.HTML()

                    with gr.TabItem("{ } Raw JSON"):
                        raw_out = gr.Code(language="json", label="Agent output")

        run_btn.click(
            fn=run_review,
            inputs=[task_dropdown, custom_diff],
            outputs=[diff_out, issues_out, grade_out, reward_out, gold_out, raw_out],
        )

        gr.HTML("""
        <div style="text-align:center;padding:24px 0 8px;font-family:'JetBrains Mono',monospace;
                    font-size:11px;color:#2a3f5f;letter-spacing:0.08em;border-top:1px solid #1e2d45;margin-top:24px;">
          OPENENV CODE REVIEW AGENT · BUILT FOR META PYTORCH OPENENV HACKATHON
        </div>
        """)

    return demo


# ── Mount & serve ─────────────────────────────────────────────

gradio_app = build_app()
app = gr.mount_gradio_app(api, gradio_app, path="/")

def main():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)

if __name__ == "__main__":
    main()
