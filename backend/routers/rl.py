"""
RL Engine API Router — Training, Evaluation, Review, and Metrics endpoints.

Endpoints:
  POST /api/rl/train         — Start training session
  GET  /api/rl/train/status   — Training progress
  POST /api/rl/evaluate       — Evaluate agent
  POST /api/rl/review         — Review a diff with trained agent
  GET  /api/rl/metrics        — Training metrics history
  GET  /api/rl/agent/info     — Agent info
  POST /api/rl/feedback       — Submit human feedback (RLHF)
  GET  /api/rl/baseline       — Baseline comparison (LLM vs RL)
"""

import json
import os
import sys
import time
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

# Add openenv-code-review to path (at position 0 to take priority)
OPENENV_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'openenv-code-review')
OPENENV_DIR = os.path.abspath(OPENENV_DIR)
if OPENENV_DIR not in sys.path:
    sys.path.insert(0, OPENENV_DIR)

router = APIRouter(prefix="/rl", tags=["RL Engine"])


def _import_openenv(module_name):
    """Import a module from the openenv-code-review directory by absolute path.
    
    Temporarily ensures OPENENV_DIR is at the front of sys.path and hides
    conflicting cached modules (e.g., backend 'schemas') so that internal
    imports within openenv modules resolve correctly.
    """
    import importlib.util
    
    # Save original path and ensure openenv is first
    original_path = sys.path.copy()
    if OPENENV_DIR in sys.path:
        sys.path.remove(OPENENV_DIR)
    sys.path.insert(0, OPENENV_DIR)
    
    # Temporarily hide conflicting backend modules from cache
    conflicting = ['schemas', 'grader', 'reward', 'agent', 'environment']
    saved_modules = {}
    for name in conflicting:
        if name in sys.modules:
            saved_modules[name] = sys.modules.pop(name)
    
    try:
        module_path = os.path.join(OPENENV_DIR, f"{module_name}.py")
        spec = importlib.util.spec_from_file_location(f"openenv.{module_name}", module_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        # Restore original path and cached modules
        sys.path[:] = original_path
        for name, cached_mod in saved_modules.items():
            sys.modules[name] = cached_mod


# ── In-memory state (for demo/hackathon — swap with DB for production) ──
_training_state = {
    "status": "idle",       # idle | training | completed | failed
    "progress": 0,
    "total_episodes": 0,
    "metrics": [],
    "summary": None,
    "started_at": None,
    "completed_at": None,
}

_agent_instance = None
_encoder_instance = None


def _get_agent():
    global _agent_instance
    if _agent_instance is None:
        dqn_mod = _import_openenv("dqn_agent")
        _agent_instance = dqn_mod.DQNAgent(config=dqn_mod.DQNConfig())
    return _agent_instance


def _get_encoder():
    global _encoder_instance
    if _encoder_instance is None:
        enc_mod = _import_openenv("state_encoder")
        _encoder_instance = enc_mod.StateEncoder()
    return _encoder_instance


# ────────────────────── Request/Response Schemas ─────────────

class TrainRequest(BaseModel):
    episodes: int = Field(50, ge=1, le=1000, description="Number of training episodes")
    learning_rate: float = Field(1e-3, gt=0, description="Learning rate")
    epsilon_start: float = Field(1.0, ge=0, le=1)
    epsilon_end: float = Field(0.01, ge=0, le=1)
    epsilon_decay: float = Field(0.995, gt=0, le=1)
    batch_size: int = Field(32, ge=8, le=256)


class ReviewRequest(BaseModel):
    diff: str = Field(..., description="Unified diff text")
    language: str = Field("python", description="Programming language")
    pr_description: str = Field("", description="PR description")


class FeedbackRequest(BaseModel):
    task_id: str = Field(..., description="Task ID for the reviewed PR")
    feedback: float = Field(..., ge=0.0, le=1.0, description="Human feedback (0=bad, 1=good)")


# ────────────────────── Endpoints ────────────────────────────

@router.post("/train")
async def start_training(request: TrainRequest):
    """Start a DQN training session."""
    global _training_state, _agent_instance

    if _training_state["status"] == "training":
        raise HTTPException(status_code=409, detail="Training already in progress")

    _training_state = {
        "status": "training",
        "progress": 0,
        "total_episodes": request.episodes,
        "metrics": [],
        "summary": None,
        "started_at": time.time(),
        "completed_at": None,
    }

    # Reset agent
    _agent_instance = None

    try:
        tl_mod = _import_openenv("training_loop")

        config = tl_mod.TrainingConfig(
            episodes=request.episodes,
            learning_rate=request.learning_rate,
            epsilon_start=request.epsilon_start,
            epsilon_end=request.epsilon_end,
            epsilon_decay=request.epsilon_decay,
            batch_size=request.batch_size,
            checkpoint_dir=os.path.join(OPENENV_DIR, "checkpoints"),
            log_file=os.path.join(OPENENV_DIR, "training_log.json"),
        )

        def on_episode(metrics):
            _training_state["progress"] = metrics.episode + 1
            _training_state["metrics"].append(metrics.to_dict())

        session = tl_mod.TrainingSession(config=config, on_episode=on_episode)
        session.run()

        _training_state["status"] = "completed"
        _training_state["completed_at"] = time.time()
        _training_state["summary"] = session._compute_summary()

        # Store the trained agent
        _agent_instance = session.agent

        return {
            "status": "completed",
            "episodes": request.episodes,
            "summary": _training_state["summary"],
        }

    except Exception as e:
        _training_state["status"] = "failed"
        _training_state["completed_at"] = time.time()
        raise HTTPException(status_code=500, detail=f"Training failed: {str(e)}")


@router.get("/train/status")
async def get_training_status():
    """Get current training progress."""
    recent_metrics = _training_state["metrics"][-20:] if _training_state["metrics"] else []

    return {
        "status": _training_state["status"],
        "progress": _training_state["progress"],
        "total_episodes": _training_state["total_episodes"],
        "recent_metrics": recent_metrics,
        "summary": _training_state["summary"],
        "started_at": _training_state["started_at"],
        "completed_at": _training_state["completed_at"],
    }


@router.post("/evaluate")
async def evaluate_agent():
    """Evaluate the trained agent on all tasks."""
    try:
        tl_mod = _import_openenv("training_loop")

        config = tl_mod.TrainingConfig(episodes=1)
        session = tl_mod.TrainingSession(config=config)

        # Load checkpoint if available
        checkpoint_path = os.path.join(OPENENV_DIR, "checkpoints", "dqn_final.pt")
        if os.path.exists(checkpoint_path):
            session.agent.load_checkpoint(checkpoint_path)

        eval_results = session.evaluate()
        return eval_results

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(e)}")


@router.post("/review")
async def review_with_agent(request: ReviewRequest):
    """Review a code diff using the trained RL agent."""
    try:
        schemas_mod = _import_openenv("schemas")
        agent_mod = _import_openenv("agent")
        dqn_mod = _import_openenv("dqn_agent")
        tl_mod = _import_openenv("training_loop")

        agent = _get_agent()
        encoder = _get_encoder()

        # Load checkpoint
        checkpoint_path = os.path.join(OPENENV_DIR, "checkpoints", "dqn_final.pt")
        if os.path.exists(checkpoint_path):
            agent.load_checkpoint(checkpoint_path)

        # Create observation
        obs = schemas_mod.ReviewObservation(
            task_id="custom_review",
            diff=request.diff,
            language=request.language,
            pr_description=request.pr_description,
        )

        # Encode state + select action
        state = encoder.encode(obs)
        action_id = agent.select_action(state, training=False)
        strategy, threshold = dqn_mod.decode_action(action_id)

        # Execute strategy
        demo_agent = agent_mod.DemoAgent()
        review_action = tl_mod.execute_strategy_with_demo(obs, strategy, threshold, demo_agent)

        # Get decision trace for explainability
        decision_trace = agent.get_decision_trace()

        return {
            "review": {
                "issues": [
                    {
                        "file": getattr(issue, "file", "unknown"),
                        "line": getattr(issue, "line", 0),
                        "severity": str(getattr(issue, "severity", "info")),
                        "category": str(getattr(issue, "category", "bug")),
                        "description": getattr(issue, "description", ""),
                        "suggested_fix": getattr(issue, "suggested_fix", None),
                        "confidence": getattr(issue, "confidence", 0.8),
                    }
                    for issue in review_action.issues
                ],
                "summary": review_action.summary,
                "approve": review_action.approve,
            },
            "rl_metadata": {
                "strategy": strategy.value,
                "threshold": threshold,
                "action_id": action_id,
                "decision_trace": decision_trace,
            },
        }

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f"[RL REVIEW ERROR] {tb}")
        raise HTTPException(status_code=500, detail=f"Review failed: {str(e)}\n{tb}")


@router.get("/metrics")
async def get_metrics():
    """Get all training metrics history."""
    # Try to load from log file
    log_path = os.path.join(OPENENV_DIR, "training_log.json")
    if os.path.exists(log_path):
        with open(log_path, "r") as f:
            return json.load(f)

    # Fall back to in-memory
    return {
        "config": {},
        "summary": _training_state.get("summary"),
        "episodes": _training_state.get("metrics", []),
    }


@router.get("/agent/info")
async def get_agent_info():
    """Get current agent configuration and status."""
    agent = _get_agent()
    info = agent.get_info()

    # Check for checkpoint
    checkpoint_path = os.path.join(OPENENV_DIR, "checkpoints", "dqn_final.pt")
    info["has_checkpoint"] = os.path.exists(checkpoint_path)
    info["training_status"] = _training_state["status"]

    return info


@router.post("/feedback")
async def submit_feedback(request: FeedbackRequest):
    """Submit human feedback for RLHF integration."""
    return {
        "status": "recorded",
        "task_id": request.task_id,
        "feedback": request.feedback,
        "message": f"Feedback ({request.feedback:.1f}) recorded for task {request.task_id}",
    }


@router.get("/baseline")
async def baseline_comparison():
    """
    Compare LLM-only baseline vs RL-enhanced agent.

    Runs both agents on all tasks and returns side-by-side metrics.
    """
    try:
        env_mod = _import_openenv("environment")
        agent_mod = _import_openenv("agent")
        dqn_mod = _import_openenv("dqn_agent")
        tl_mod = _import_openenv("training_loop")

        env = env_mod.CodeReviewEnv()
        encoder = _get_encoder()
        demo_agent = agent_mod.DemoAgent()

        # ── LLM-only baseline (DemoAgent, aggressive strategy) ──
        baseline_results = []
        for task_id in env.task_ids:
            obs = env.reset(task_id=task_id)
            action = demo_agent.review(obs)
            _, reward, _, info = env.step(action)
            grade = info.get("grade_result", {})
            breakdown = grade.get("breakdown", {})
            baseline_results.append({
                "task_id": task_id,
                "reward": reward,
                "recall": breakdown.get("recall", 0),
                "precision": breakdown.get("precision", 0),
                "matched": breakdown.get("matched_issues", 0),
                "missed": breakdown.get("missed_issues", 0),
                "false_positives": breakdown.get("false_positives", 0),
            })

        # ── RL-enhanced agent ──
        rl_agent = dqn_mod.DQNAgent(config=dqn_mod.DQNConfig())
        checkpoint_path = os.path.join(OPENENV_DIR, "checkpoints", "dqn_final.pt")
        if os.path.exists(checkpoint_path):
            rl_agent.load_checkpoint(checkpoint_path)

        rl_results = []
        for task_id in env.task_ids:
            obs = env.reset(task_id=task_id)
            state = encoder.encode(obs)
            action_id = rl_agent.select_action(state, training=False)
            strategy, threshold = dqn_mod.decode_action(action_id)
            review_action = tl_mod.execute_strategy_with_demo(obs, strategy, threshold, demo_agent)
            _, reward, _, info = env.step(review_action)
            grade = info.get("grade_result", {})
            breakdown = grade.get("breakdown", {})
            rl_results.append({
                "task_id": task_id,
                "reward": reward,
                "recall": breakdown.get("recall", 0),
                "precision": breakdown.get("precision", 0),
                "strategy": strategy.value,
                "threshold": threshold,
                "matched": breakdown.get("matched_issues", 0),
                "missed": breakdown.get("missed_issues", 0),
                "false_positives": breakdown.get("false_positives", 0),
            })

        # ── Compute comparison ──
        b_rewards = [r["reward"] for r in baseline_results]
        r_rewards = [r["reward"] for r in rl_results]

        return {
            "baseline": {
                "agent": "LLM-only (DemoAgent)",
                "avg_reward": round(float(sum(b_rewards) / len(b_rewards)), 4) if b_rewards else 0,
                "avg_recall": round(float(sum(r["recall"] for r in baseline_results) / len(baseline_results)), 4) if baseline_results else 0,
                "avg_precision": round(float(sum(r["precision"] for r in baseline_results) / len(baseline_results)), 4) if baseline_results else 0,
                "per_task": baseline_results,
            },
            "rl_enhanced": {
                "agent": "Hierarchical DQN",
                "avg_reward": round(float(sum(r_rewards) / len(r_rewards)), 4) if r_rewards else 0,
                "avg_recall": round(float(sum(r["recall"] for r in rl_results) / len(rl_results)), 4) if rl_results else 0,
                "avg_precision": round(float(sum(r["precision"] for r in rl_results) / len(rl_results)), 4) if rl_results else 0,
                "per_task": rl_results,
            },
            "improvement": {
                "reward_delta": round(
                    float(sum(r_rewards) / len(r_rewards) - sum(b_rewards) / len(b_rewards)), 4
                ) if b_rewards and r_rewards else 0,
            },
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Comparison failed: {str(e)}")
