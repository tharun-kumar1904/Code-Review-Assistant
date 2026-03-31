# 🤖 OpenEnv Code Review Agent

**AI-powered pull request reviewer built for the Meta PyTorch OpenEnv Hackathon**

A Gymnasium-compatible environment where an LLM agent reviews PR diffs, detects real bugs, assigns severity levels, and receives a reward signal based on grading accuracy.

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    OpenEnv Interface                         │
│                                                              │
│   reset(task_id)  →  ReviewObservation                      │
│   step(action)    →  (obs, reward, done, info)              │
│   state()         →  EnvironmentState                       │
│                                                              │
│  ┌─────────────┐   ┌──────────┐   ┌────────────────────┐   │
│  │  Task       │   │  Agent   │   │    Grader +        │   │
│  │  Dataset    │──▶│  (LLM)   │──▶│    Reward          │   │
│  │  (PR Diffs) │   │          │   │    Function        │   │
│  └─────────────┘   └──────────┘   └────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Gradio Demo (HF Spaces)                 │   │
│  │  Diff View │ Issues │ Grading │ Gold Standard │ JSON │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🎯 **OpenEnv Compliant** | `reset()`, `step()`, `state()` API with Pydantic-typed schemas |
| 🐛 **Bug Detection** | Null checks, SQL injection, off-by-one, PyTorch tensor bugs |
| ⚖️ **5-Criterion Grading** | Recall, Precision, Severity Accuracy, Feedback Quality, Summary |
| 🏆 **Reward Function** | Weighted [0,1] reward with configurable weights |
| 🤖 **LLM Agent** | GPT-4o with structured JSON output and hallucination controls |
| 🎭 **Demo Mode** | Works without API key using deterministic canned responses |
| 🔥 **PyTorch-Specific** | Tasks include tensor shape/device bugs (Meta-relevant!) |
| 📊 **Rich Gradio UI** | Styled diff viewer, issue cards, grading dashboard, reward gauge |

---

## 📁 Project Structure

```
openenv-code-review/
├── environment.py         # OpenEnv environment (reset/step/state)
├── grader.py              # 5-criterion grading logic
├── reward.py              # Weighted reward computation
├── agent.py               # LLM agent + deterministic demo agent
├── schemas.py             # Pydantic models (Action, Observation, etc.)
├── diff_parser.py         # Unified diff parser
├── app.py                 # Gradio demo for HF Spaces
├── tasks/
│   ├── task_001_null_check.json      # Missing null check bug
│   ├── task_002_sql_inject.json      # SQL injection vulnerability
│   ├── task_003_off_by_one.json      # Off-by-one + bare except
│   ├── task_004_tensor_shape.json    # PyTorch shape/device bugs
│   └── task_005_clean_pr.json        # Clean PR (no issues)
├── tests/
│   ├── test_environment.py
│   ├── test_grader.py
│   ├── test_reward.py
│   └── test_diff_parser.py
├── requirements.txt
├── Dockerfile
├── .env.example
└── README.md
```

---

## 🚀 Quick Start

### 1. Install Dependencies
```bash
cd openenv-code-review
pip install -r requirements.txt
```

### 2. Run Tests
```bash
python -m pytest tests/ -v
```

### 3. Launch Demo
```bash
# Without API key (demo mode with canned responses)
python app.py

# With API key (live LLM reviews)
OPENAI_API_KEY=sk-xxx python app.py
```

Open http://localhost:7860 in your browser.

### 4. Programmatic Usage
```python
from environment import CodeReviewEnv
from agent import DemoAgent

env = CodeReviewEnv()
agent = DemoAgent()

# Episode loop
obs = env.reset(task_id="task_001_null_check")
action = agent.review(obs)
_, reward, done, info = env.step(action)

print(f"Reward: {reward:.2f}")
print(f"Grade: {info['grade_result']['breakdown']}")
```

---

## 📊 Grading Rubric

| Criterion | Weight | What It Measures |
|-----------|--------|------------------|
| **Bug Detection (Recall)** | 35% | % of gold-standard issues found |
| **Precision** | 15% | 1 - (false positives / total agent issues) |
| **Severity Accuracy** | 20% | Exact match = 1.0, ±1 level = 0.5 |
| **Feedback Quality** | 20% | Description length + suggested fix bonus |
| **Summary Quality** | 10% | Non-empty + keyword coverage |

**Reward** = Σ (weight × criterion), clamped to [0.0, 1.0]

---

## 🧪 Test Tasks

| Task | Bug Type | Severity | Domain |
|------|----------|----------|--------|
| 001 | Missing null check | High | Web API |
| 002 | SQL injection | Critical | Security |
| 003 | Off-by-one + bare except | High/Medium | Data processing |
| 004 | Tensor shape + device | Critical/High | **PyTorch ML** |
| 005 | Clean PR (no bugs) | N/A | Configuration |

---

## 🐳 Deploy on Hugging Face Spaces

### Option A: Dockerfile
1. Create a new Space at [huggingface.co/new-space](https://huggingface.co/new-space)
2. Select **Docker** as the SDK
3. Push this directory to the Space repo
4. Add `OPENAI_API_KEY` as a Space Secret (optional — works without it)

### Option B: Gradio SDK
1. Create a new Space with **Gradio** SDK
2. Push all files to the Space repo
3. HF auto-detects `app.py` and runs it

### Docker Build & Run (local)
```bash
docker build -t openenv-cr .
docker run -p 7860:7860 -e OPENAI_API_KEY=sk-xxx openenv-cr
```

---

## 🏆 Differentiation

1. **PyTorch-Specific Bug Detection** — Tasks include tensor shape mismatches and device placement errors, directly relevant to Meta's ecosystem
2. **Confidence-Calibrated Reviews** — Agent reports confidence per issue; grader can bonus well-calibrated confidence scores
3. **Multi-Granularity Feedback** — Issues include line-level precision + function-level architectural suggestions

---

## 📝 License

MIT License — Built for the Meta PyTorch OpenEnv Hackathon.
