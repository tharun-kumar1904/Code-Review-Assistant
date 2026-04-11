# 🤖 OpenEnv Code Review Agent

**AI-powered pull request reviewer built for the Meta PyTorch OpenEnv Hackathon**

A Gymnasium-compatible environment where an LLM agent reviews PR diffs, detects real bugs, assigns severity levels, and receives a reward signal based on grading accuracy.

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    OpenEnv Interface                         │
│                                                              │
│   reset(task_id)  →  ReviewObservation                       │
│   step(action)    →  (obs, reward, done, info)               │
│   state()         →  EnvironmentState                        │
│                                                              │
│  ┌─────────────┐   ┌──────────┐   ┌────────────────────┐   │
│  │  Task       │   │  Agent   │   │    Grader +        │   │
│  │  Dataset    │──▶│  (LLM)   │──▶│    Reward          │   │
│  │  (PR Diffs) │   │          │   │    Function        │   │
│  └─────────────┘   └──────────┘   └────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              Gradio Demo (HF Spaces)                 │  │
│  │  Diff View │ Issues │ Grading │ Gold Standard │ JSON │  │
│  └──────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

---

## ✨ Motivation & Environment Description

Real-world code review is challenging for LLMs because it requires balancing precision (finding subtle, complex bugs) with recall (avoiding false positives and noise). This environment models a genuine, high-stakes developer task.

By defining an **Action Space** (structured JSON responses) and **Observation Space** (full unified diffs with context), we can systematically benchmark how well models perform at catching logical, performance, and security bugs—without hallucinating issues on clean code. The reward function provides continuous, shaped signaling for partial task progress, making it suitable for both LLM evaluation and Reinforcement Learning fine-tuning (RLHF).

---

## 🚀 Setup & Usage Instructions

### 1. Requirements & Environment Verification
Ensure you have Docker installed or Python 3.11+. You must define the following in your environment:
- `API_BASE_URL` (Your LLM API endpoint, e.g., OpenAI or custom)
- `MODEL_NAME` (e.g., `gpt-4o`)
- `HF_TOKEN` / `OPENAI_API_KEY` (Required for full agent evaluation)

### 2. Deploy Local Baseline Inference
```bash
cd openenv-code-review
pip install -r requirements.txt

# Run full baseline inference across all tasks
python inference.py
```

### 3. Launch Demo GUI (Optional)
```bash
python app.py
```
Open http://localhost:7860 to manually explore the agent's behavior.

---

## 📦 Action and Observation Spaces

### Observation Space
The environment emits a **`ReviewObservation`** containing:
- `task_id` (str): Unique task identifier
- `diff` (str): Full unified patch text
- `language` (str): Target programming language (e.g., Python)
- `file_context` (str): Complete file snapshot for surrounding scope
- `pr_description` (str): PR metadata

### Action Space 
The agent must reply with a **`ReviewAction`**:
- `issues[]` (list): Array of bugs found.
  - `file` (str): Filename.
  - `line` (int): Source code line number.
  - `category` (enum): [bug, security, performance, style, logic, error_handling]
  - `severity` (enum): [critical, high, medium, low, info]
  - `description` (str): Meaningful context.
  - `suggested_fix` (str): Optional but rewarded.
- `summary` (str): High-level breakdown.
- `approve` (bool): Pass/fail decision.

---

## 📊 Baseline Inference Scores

Running the `inference.py` script against the DemoAgent baseline model (or gpt-4o) yields:
- **Total Tasks:** 15
- **Average Reward (per task):** ~0.28 to 0.70 (depending on agent completeness and task difficulty)
- **Time to Complete:** ~8-15 seconds total

*Our baseline test demonstrated deterministic handling across tasks but highlights how complex reasoning (e.g. tracking variable aliases) causes current LLM models to stumble without RLHF tuning.*

---

## 🧪 Tasks & Difficulty Progression

The environment features exactly 15 tasks classified from Easy to Hard with clear, deterministic grading.

### Easy Tasks (7)
*Clear scope, straightforward patterns or clean code lacking issues.*
- `task_001_null_check`: Missing null check on user object
- `task_002_sql_inject`: SQL injection via f-string 
- `task_005_clean_pr`: Clean PR with no bugs (testing false-positive avoidance)
- `task_007_hardcoded_secret`: Hardcoded API key + bare except
- `task_011_type_confusion`: String parameters used in arithmetic
- `task_012_clean_refactor`: Clean context manager refactoring
- `task_015_clean_logging`: Clean structured JSON logging

### Medium Tasks (6)
*Subtle context required, inter-feature side-effects, or minor vulnerabilities.*
- `task_003_off_by_one`: Off-by-one boundary flaw + error swallow
- `task_006_race_condition`: Concurrency limit in async counter
- `task_008_n_plus_one`: N+1 query loop performance bottleneck
- `task_009_path_traversal`: Path traversal input vulnerability
- `task_010_memory_leak`: Unbounded cache list leak
- `task_013_xss_vulnerability`: XSS via direct HTML interpolation

### Hard Tasks (2)
*Domain-specific expertise required, multiple interacting components, and logic leaps.*
- `task_004_tensor_shape`: PyTorch tensor shape mismatch + device placement bug
- `task_014_error_swallow`: Bare exceptions wrapping silent `None` propagation inside retry logic loops

---

## 🏆 Grading Rubric & Reward Mechanics

**Reward Range:** `[0.0, 1.0]`

| Criterion | Weight | Measuring Target |
|-----------|--------|------------------|
| **Recall** | 35% | % of gold-standard issues found |
| **Precision** | 15% | 1 - (false positives / total agent issues) |
| **Severity** | 20% | Expected match = 1.0, ±1 severity = 0.5 |
| **Feedback** | 20% | Robust explanations and viable fixes |
| **Summary** | 10% | Keyword coverage, length completeness |

**Reward Shaping Mechanics:**
- *Efficiency Bonus:* Added for zero false positives against clean code.
- *False Positive Penalty:* Mildly scaled down if agents hallucinate nonexistent bugs.
- *Approve/Reject Accuracy:* Additional progress reward for making the correct PR-level decision.

---

## 🐳 Deploy on Hugging Face Spaces

1. Create a new Space at [huggingface.co/new-space](https://huggingface.co/new-space)
2. Select **Docker** as the SDK.
3. Push everything in this folder directly to the new repo.
4. Auto-detects the built-in Gradio endpoint (`0.0.0.0:7860`).

---

## 📝 License

MIT License — Built for the Meta PyTorch OpenEnv Hackathon.
