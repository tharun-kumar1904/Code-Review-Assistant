"""
Multi-Episode Training Loop for the DQN Code Review Agent.

Orchestrates:
  1. Environment reset → observation
  2. State encoding → state vector
  3. DQN action selection → strategy + threshold
  4. Strategy execution via LLM or DemoAgent → ReviewAction
  5. Environment step → reward
  6. Experience storage → replay buffer
  7. DQN training step → loss
  8. Metrics logging → JSON history

Supports:
  - CLI execution: python training_loop.py --episodes 100
  - API execution: TrainingSession.run(episodes=100)
  - Checkpoint save/load
  - Real-time metrics streaming
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import numpy as np

# Ensure local imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from schemas import ReviewAction, ReviewObservation, Category
from environment import CodeReviewEnv
from agent import DemoAgent, ReviewAgent
from dqn_agent import (
    DQNAgent, DQNConfig, ReviewStrategy, decode_action, NUM_ACTIONS,
)
from state_encoder import StateEncoder
from experience_buffer import ReplayBuffer


# ────────────────────── Strategy → LLM Prompt ────────────────

# Strategy-specific system prompt suffixes
STRATEGY_PROMPTS = {
    ReviewStrategy.APPROVE: (
        "You believe this code is correct. Only report issues if you are "
        "extremely confident (>95%). It is fine to return an empty issues list."
    ),
    ReviewStrategy.BUGS_ONLY: (
        "Focus ONLY on bug detection: null references, off-by-one errors, "
        "type errors, race conditions, logic errors. Ignore style, security, "
        "and performance issues entirely."
    ),
    ReviewStrategy.SECURITY_ONLY: (
        "Focus ONLY on security vulnerabilities: SQL injection, XSS, "
        "hardcoded secrets, path traversal, insecure functions. "
        "Ignore bugs, style, and performance issues."
    ),
    ReviewStrategy.STYLE_ONLY: (
        "Focus ONLY on code style and quality: naming conventions, "
        "code organization, documentation, best practices. "
        "Ignore bugs and security issues."
    ),
    ReviewStrategy.AGGRESSIVE: (
        "Be thorough and report ALL issues you can find across all "
        "categories: bugs, security, performance, style, logic. "
        "Better to over-report than miss something."
    ),
    ReviewStrategy.CONSERVATIVE: (
        "Be very selective. Only report issues you are highly confident "
        "about (>85%). Better to miss a minor issue than report a false positive."
    ),
}


def execute_strategy_with_demo(
    observation: ReviewObservation,
    strategy: ReviewStrategy,
    threshold: float,
    demo_agent: DemoAgent,
) -> ReviewAction:
    """
    Execute a review strategy using the DemoAgent.

    For the demo, we use the DemoAgent's canned responses and filter
    based on strategy + threshold. In production, this would call the
    LLM with strategy-specific prompts.
    """
    # Get base review from DemoAgent
    base_action = demo_agent.review(observation)

    # Apply strategy filter
    if strategy == ReviewStrategy.APPROVE:
        return ReviewAction(issues=[], summary="Code looks clean.", approve=True)

    filtered_issues = []
    for issue in base_action.issues:
        # Apply confidence threshold
        if issue.confidence < threshold:
            continue

        # Apply category filter based on strategy
        if strategy == ReviewStrategy.BUGS_ONLY:
            if issue.category not in (Category.BUG, Category.LOGIC, Category.ERROR_HANDLING):
                continue
        elif strategy == ReviewStrategy.SECURITY_ONLY:
            if issue.category != Category.SECURITY:
                continue
        elif strategy == ReviewStrategy.STYLE_ONLY:
            if issue.category != Category.STYLE:
                continue
        # AGGRESSIVE and CONSERVATIVE keep all categories

        filtered_issues.append(issue)

    return ReviewAction(
        issues=filtered_issues,
        summary=base_action.summary,
        approve=len(filtered_issues) == 0,
    )


# ────────────────────── Episode Metrics ──────────────────────

@dataclass
class EpisodeMetrics:
    """Metrics for a single training episode."""
    episode: int
    task_id: str
    reward: float
    loss: float
    epsilon: float
    q_value_mean: float
    q_value_max: float
    strategy: str
    threshold: float
    action_id: int
    issues_found: int
    issues_correct: int
    false_positives: int
    missed_issues: int
    recall: float
    precision: float
    duration_ms: float
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "episode": self.episode,
            "task_id": self.task_id,
            "reward": round(self.reward, 4),
            "loss": round(self.loss, 6),
            "epsilon": round(self.epsilon, 4),
            "q_value_mean": round(self.q_value_mean, 4),
            "q_value_max": round(self.q_value_max, 4),
            "strategy": self.strategy,
            "threshold": self.threshold,
            "action_id": self.action_id,
            "issues_found": self.issues_found,
            "issues_correct": self.issues_correct,
            "false_positives": self.false_positives,
            "missed_issues": self.missed_issues,
            "recall": round(self.recall, 4),
            "precision": round(self.precision, 4),
            "duration_ms": round(self.duration_ms, 2),
            "timestamp": self.timestamp,
        }


# ────────────────────── Training Session ─────────────────────

@dataclass
class TrainingConfig:
    """Configuration for a training session."""
    episodes: int = 100
    learning_rate: float = 1e-3
    gamma: float = 0.99
    epsilon_start: float = 1.0
    epsilon_end: float = 0.01
    epsilon_decay: float = 0.995
    batch_size: int = 32
    buffer_capacity: int = 10_000
    checkpoint_every: int = 25
    checkpoint_dir: str = "checkpoints"
    use_llm: bool = False  # Use DemoAgent by default (no API key needed)
    log_file: str = "training_log.json"


class TrainingSession:
    """
    Orchestrates multi-episode DQN training on code review tasks.

    Usage:
        session = TrainingSession(config=TrainingConfig(episodes=50))
        history = session.run()
    """

    def __init__(
        self,
        config: TrainingConfig | None = None,
        on_episode: Callable[[EpisodeMetrics], None] | None = None,
    ):
        self.config = config or TrainingConfig()
        self.on_episode = on_episode  # Callback for real-time updates

        # Initialize components
        self.env = CodeReviewEnv()
        self.encoder = StateEncoder()
        self.buffer = ReplayBuffer(
            capacity=self.config.buffer_capacity,
            use_prioritized=True,
        )

        dqn_config = DQNConfig(
            learning_rate=self.config.learning_rate,
            gamma=self.config.gamma,
            epsilon_start=self.config.epsilon_start,
            epsilon_end=self.config.epsilon_end,
            epsilon_decay=self.config.epsilon_decay,
            batch_size=self.config.batch_size,
        )
        self.agent = DQNAgent(config=dqn_config)

        # Agent for executing strategies
        if self.config.use_llm:
            self.executor = ReviewAgent()
        else:
            self.executor = DemoAgent()

        self.history: list[EpisodeMetrics] = []
        self._running = False

    def run(self, episodes: int | None = None) -> list[dict[str, Any]]:
        """
        Run the training loop.

        Args:
            episodes: Override number of episodes.

        Returns:
            List of per-episode metrics as dicts.
        """
        num_episodes = episodes or self.config.episodes
        self._running = True

        checkpoint_dir = Path(self.config.checkpoint_dir)
        checkpoint_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n{'='*60}")
        print(f"  [DQN] Training -- {num_episodes} episodes")
        print(f"  Tasks: {len(self.env.task_ids)} | Actions: {NUM_ACTIONS}")
        print(f"  Device: {self.agent.device}")
        print(f"{'='*60}\n")

        for ep in range(num_episodes):
            if not self._running:
                break

            t_start = time.time()

            # ── Reset environment ──
            obs = self.env.reset()
            state = self.encoder.encode(obs)

            # ── Select action ──
            action_id = self.agent.select_action(state, training=True)
            strategy, threshold = decode_action(action_id)

            # ── Execute strategy ──
            review_action = execute_strategy_with_demo(
                obs, strategy, threshold, self.executor
            )

            # ── Step environment → reward ──
            _, reward, done, info = self.env.step(review_action)

            # ── Store transition ──
            # For single-step episodes, next_state = zeros (terminal)
            next_state = np.zeros_like(state)
            self.buffer.push_transition(state, action_id, reward, next_state, done)

            # ── Train DQN ──
            loss = 0.0
            if self.buffer.is_ready:
                batch = self.buffer.sample(self.config.batch_size)
                states, actions, rewards_b, next_states, dones, weights, indices = batch
                loss, td_errors = self.agent.train_step(
                    states, actions, rewards_b, next_states, dones, weights
                )
                self.buffer.update_priorities(indices, td_errors)

            # ── Decay epsilon ──
            self.agent.decay_epsilon()

            # ── Compute metrics ──
            grade = info.get("grade_result", {})
            breakdown = grade.get("breakdown", {})
            q_vals = self.agent._last_q_values
            q_mean = float(np.mean(q_vals)) if q_vals is not None else 0.0
            q_max = float(np.max(q_vals)) if q_vals is not None else 0.0

            duration_ms = (time.time() - t_start) * 1000

            metrics = EpisodeMetrics(
                episode=ep,
                task_id=info.get("task_id", ""),
                reward=reward,
                loss=loss,
                epsilon=self.agent.epsilon,
                q_value_mean=q_mean,
                q_value_max=q_max,
                strategy=strategy.value,
                threshold=threshold,
                action_id=action_id,
                issues_found=breakdown.get("total_agent", 0),
                issues_correct=breakdown.get("matched_issues", 0),
                false_positives=breakdown.get("false_positives", 0),
                missed_issues=breakdown.get("missed_issues", 0),
                recall=breakdown.get("recall", 0.0),
                precision=breakdown.get("precision", 0.0),
                duration_ms=duration_ms,
            )

            self.history.append(metrics)

            # ── Callback ──
            if self.on_episode:
                self.on_episode(metrics)

            # ── Print progress ──
            marker = "[++]" if reward >= 0.8 else "[OK]" if reward >= 0.6 else "[??]" if reward >= 0.3 else "[XX]"
            print(
                f"  Ep {ep:4d}/{num_episodes} | "
                f"{marker} R={reward:.3f} | "
                f"e={self.agent.epsilon:.3f} | "
                f"L={loss:.5f} | "
                f"Strategy={strategy.value:15s} | "
                f"Task={info.get('task_id', '')}"
            )

            # ── Checkpoint ──
            if (ep + 1) % self.config.checkpoint_every == 0:
                ckpt_path = checkpoint_dir / f"dqn_ep{ep+1}.pt"
                self.agent.save_checkpoint(ckpt_path)
                print(f"  [SAVE] Checkpoint saved: {ckpt_path}")

        # ── Final checkpoint ──
        final_path = checkpoint_dir / "dqn_final.pt"
        self.agent.save_checkpoint(final_path)

        # ── Save training log ──
        log_path = Path(self.config.log_file)
        log_data = {
            "config": {
                "episodes": num_episodes,
                "learning_rate": self.config.learning_rate,
                "gamma": self.config.gamma,
                "epsilon_start": self.config.epsilon_start,
                "epsilon_end": self.config.epsilon_end,
                "epsilon_decay": self.config.epsilon_decay,
                "batch_size": self.config.batch_size,
            },
            "summary": self._compute_summary(),
            "episodes": [m.to_dict() for m in self.history],
        }
        with open(log_path, "w") as f:
            json.dump(log_data, f, indent=2)
        print(f"\n  [LOG] Training log saved: {log_path}")

        # ── Summary ──
        summary = self._compute_summary()
        print(f"\n{'='*60}")
        print("  Training Complete!")
        print(f"  Avg Reward: {summary['avg_reward']:.4f}")
        print(f"  Best Reward: {summary['best_reward']:.4f}")
        print(f"  Final ε: {summary['final_epsilon']:.4f}")
        print(f"  Total Training Steps: {self.agent.training_step}")
        print(f"{'='*60}\n")

        return [m.to_dict() for m in self.history]

    def stop(self) -> None:
        """Stop training (for async/API use)."""
        self._running = False

    def _compute_summary(self) -> dict[str, Any]:
        """Compute summary statistics."""
        if not self.history:
            return {"avg_reward": 0, "best_reward": 0, "final_epsilon": 1.0}

        rewards = [m.reward for m in self.history]
        last_10 = rewards[-10:] if len(rewards) >= 10 else rewards

        return {
            "total_episodes": len(self.history),
            "avg_reward": float(np.mean(rewards)),
            "best_reward": float(max(rewards)),
            "worst_reward": float(min(rewards)),
            "last_10_avg": float(np.mean(last_10)),
            "final_epsilon": self.history[-1].epsilon,
            "total_training_steps": self.agent.training_step,
            "strategy_distribution": self._strategy_distribution(),
            "reward_trend": self._reward_trend(),
        }

    def _strategy_distribution(self) -> dict[str, int]:
        """Count how often each strategy was selected."""
        dist: dict[str, int] = {}
        for m in self.history:
            dist[m.strategy] = dist.get(m.strategy, 0) + 1
        return dist

    def _reward_trend(self, window: int = 10) -> list[float]:
        """Compute moving average of rewards."""
        rewards = [m.reward for m in self.history]
        if len(rewards) < window:
            return rewards
        trend = []
        for i in range(len(rewards) - window + 1):
            trend.append(float(np.mean(rewards[i:i + window])))
        return trend

    def evaluate(self, num_episodes: int | None = None) -> dict[str, Any]:
        """
        Evaluate the agent without training (no exploration).

        Returns:
            Evaluation metrics dict.
        """
        num_episodes = num_episodes or len(self.env.task_ids)
        results = []

        for ep in range(num_episodes):
            obs = self.env.reset()
            state = self.encoder.encode(obs)

            # Pure exploitation (no exploration)
            action_id = self.agent.select_action(state, training=False)
            strategy, threshold = decode_action(action_id)

            review_action = execute_strategy_with_demo(
                obs, strategy, threshold, self.executor
            )

            _, reward, _, info = self.env.step(review_action)
            grade = info.get("grade_result", {})
            breakdown = grade.get("breakdown", {})

            results.append({
                "task_id": info.get("task_id", ""),
                "reward": reward,
                "strategy": strategy.value,
                "threshold": threshold,
                "recall": breakdown.get("recall", 0),
                "precision": breakdown.get("precision", 0),
                "severity_accuracy": breakdown.get("severity_accuracy", 0),
                "feedback_quality": breakdown.get("feedback_quality", 0),
                "matched": breakdown.get("matched_issues", 0),
                "missed": breakdown.get("missed_issues", 0),
                "false_positives": breakdown.get("false_positives", 0),
                "decision_trace": self.agent.get_decision_trace(),
            })

        rewards = [r["reward"] for r in results]
        recalls = [r["recall"] for r in results]
        precisions = [r["precision"] for r in results]

        f1_scores = []
        for r, p in zip(recalls, precisions):
            f1 = 2 * r * p / (r + p) if (r + p) > 0 else 0
            f1_scores.append(f1)

        return {
            "num_tasks": num_episodes,
            "avg_reward": round(float(np.mean(rewards)), 4),
            "avg_recall": round(float(np.mean(recalls)), 4),
            "avg_precision": round(float(np.mean(precisions)), 4),
            "avg_f1": round(float(np.mean(f1_scores)), 4),
            "per_task": results,
        }


# ────────────────────── CLI Entry Point ──────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Train DQN Code Review Agent")
    parser.add_argument("--episodes", type=int, default=100, help="Number of episodes")
    parser.add_argument("--lr", type=float, default=1e-3, help="Learning rate")
    parser.add_argument("--gamma", type=float, default=0.99, help="Discount factor")
    parser.add_argument("--epsilon-start", type=float, default=1.0)
    parser.add_argument("--epsilon-end", type=float, default=0.01)
    parser.add_argument("--epsilon-decay", type=float, default=0.995)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--checkpoint-dir", type=str, default="checkpoints")
    parser.add_argument("--log-file", type=str, default="training_log.json")
    parser.add_argument("--evaluate", action="store_true", help="Evaluate after training")
    parser.add_argument("--dry-run", action="store_true", help="Run 3 episodes only")

    args = parser.parse_args()

    if args.dry_run:
        args.episodes = 3

    config = TrainingConfig(
        episodes=args.episodes,
        learning_rate=args.lr,
        gamma=args.gamma,
        epsilon_start=args.epsilon_start,
        epsilon_end=args.epsilon_end,
        epsilon_decay=args.epsilon_decay,
        batch_size=args.batch_size,
        checkpoint_dir=args.checkpoint_dir,
        log_file=args.log_file,
    )

    session = TrainingSession(config=config)
    session.run()

    if args.evaluate:
        print("\n[EVAL] Evaluating agent...")
        eval_results = session.evaluate()
        print(f"  Avg Reward: {eval_results['avg_reward']}")
        print(f"  Avg Recall: {eval_results['avg_recall']}")
        print(f"  Avg Precision: {eval_results['avg_precision']}")
        print(f"  Avg F1: {eval_results['avg_f1']}")


if __name__ == "__main__":
    main()
