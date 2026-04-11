"""
Hierarchical Deep Q-Network Agent for Code Review.

Architecture:
  Level 1 (Strategy): Selects review strategy (6 actions)
  Level 2 (Threshold): Selects confidence threshold (3 actions)

Combined action space: 6 × 3 = 18 total actions
Mapped back to strategy + threshold for LLM execution.

Features:
  - Dual-network (policy + target) with soft update
  - ε-greedy + Boltzmann exploration
  - Q-value explainability for decision traces
  - Checkpoint save/load
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import numpy as np

# PyTorch — optional; graceful fallback to random policy if unavailable
try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    import torch.optim as optim
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False


# ────────────────────── Action Space ──────────────────────────

class ReviewStrategy(str, Enum):
    """Level-1 actions — review strategy selection."""
    APPROVE       = "approve"
    BUGS_ONLY     = "bugs_only"
    SECURITY_ONLY = "security_only"
    STYLE_ONLY    = "style_only"
    AGGRESSIVE    = "aggressive"
    CONSERVATIVE  = "conservative"


STRATEGY_DESCRIPTIONS: dict[ReviewStrategy, str] = {
    ReviewStrategy.APPROVE:       "Approve the PR — no issues to report",
    ReviewStrategy.BUGS_ONLY:     "Focus exclusively on bug detection",
    ReviewStrategy.SECURITY_ONLY: "Focus exclusively on security vulnerabilities",
    ReviewStrategy.STYLE_ONLY:    "Focus on code style and quality improvements",
    ReviewStrategy.AGGRESSIVE:    "Report ALL detected issues across all categories",
    ReviewStrategy.CONSERVATIVE:  "Report only high-confidence issues",
}

STRATEGIES:             list[ReviewStrategy] = list(ReviewStrategy)
NUM_STRATEGIES:         int   = len(STRATEGIES)
CONFIDENCE_THRESHOLDS:  list[float] = [0.5, 0.7, 0.9]
NUM_THRESHOLDS:         int   = len(CONFIDENCE_THRESHOLDS)
NUM_ACTIONS:            int   = NUM_STRATEGIES * NUM_THRESHOLDS  # 18


def decode_action(action_id: int) -> tuple[ReviewStrategy, float]:
    """Decode flat action ID → (strategy, confidence_threshold)."""
    # BUG FIX: original had no bounds check — an out-of-range action_id
    # would silently index into STRATEGIES with a wrong value.
    action_id = int(np.clip(action_id, 0, NUM_ACTIONS - 1))
    strategy_idx  = action_id // NUM_THRESHOLDS
    threshold_idx = action_id % NUM_THRESHOLDS
    return STRATEGIES[strategy_idx], CONFIDENCE_THRESHOLDS[threshold_idx]


def encode_action(strategy: ReviewStrategy, threshold: float) -> int:
    """Encode (strategy, threshold) → flat action ID."""
    # BUG FIX: original raised ValueError if threshold not in list.
    # Now snaps to the nearest valid threshold instead.
    if threshold not in CONFIDENCE_THRESHOLDS:
        threshold = min(CONFIDENCE_THRESHOLDS, key=lambda t: abs(t - threshold))
    s_idx = STRATEGIES.index(strategy)
    t_idx = CONFIDENCE_THRESHOLDS.index(threshold)
    return s_idx * NUM_THRESHOLDS + t_idx


# ────────────────────── Neural Network ────────────────────────

if HAS_TORCH:
    class DQNNetwork(nn.Module):
        """
        3-layer MLP for Q-value estimation.

        Input:  state vector  (400-dim)
        Output: Q-values      (18-dim)
        """

        def __init__(self, state_dim: int = 400, action_dim: int = NUM_ACTIONS):
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(state_dim, 256),
                nn.ReLU(),
                nn.Dropout(0.1),
                nn.Linear(256, 128),
                nn.ReLU(),
                nn.Dropout(0.1),
                nn.Linear(128, 64),
                nn.ReLU(),
                nn.Linear(64, action_dim),
            )

        def forward(self, x: "torch.Tensor") -> "torch.Tensor":
            return self.net(x)


# ────────────────────── Config ────────────────────────────────

@dataclass
class DQNConfig:
    """Hyperparameters for the DQN agent."""
    state_dim:       int   = 400
    action_dim:      int   = NUM_ACTIONS
    learning_rate:   float = 1e-3
    gamma:           float = 0.99
    epsilon_start:   float = 1.0
    epsilon_end:     float = 0.01
    epsilon_decay:   float = 0.995
    tau:             float = 0.005   # Soft update coefficient
    batch_size:      int   = 32
    boltzmann_temp:  float = 1.0     # Initial temperature for Boltzmann exploration
    use_boltzmann:   bool  = False   # Toggle: Boltzmann vs ε-greedy
    grad_clip:       float = 10.0   # Max gradient norm


# ────────────────────── DQN Agent ─────────────────────────────

class DQNAgent:
    """
    Hierarchical DQN Agent for code review strategy selection.

    Selects (strategy, confidence_threshold) pairs that steer how the
    LLM reviews a diff. Learns which strategies earn the highest reward
    for different diff types via Double DQN + soft target updates.
    """

    def __init__(self, config: DQNConfig | None = None):
        self.config        = config or DQNConfig()
        self.epsilon       = self.config.epsilon_start
        self.training_step = 0
        self.episode_count = 0

        self._last_q_values:  np.ndarray | None    = None
        self._action_history: list[dict[str, Any]] = []

        if HAS_TORCH:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            self.policy_net = DQNNetwork(
                self.config.state_dim, self.config.action_dim
            ).to(self.device)
            self.target_net = DQNNetwork(
                self.config.state_dim, self.config.action_dim
            ).to(self.device)
            self.target_net.load_state_dict(self.policy_net.state_dict())
            self.target_net.eval()
            self.optimizer = optim.Adam(
                self.policy_net.parameters(),
                lr=self.config.learning_rate,
            )
        else:
            self.device     = None
            self.policy_net = None
            self.target_net = None
            self.optimizer  = None

    # ── Action selection ──────────────────────────────────────

    def select_action(self, state: np.ndarray, training: bool = True) -> int:
        """
        Select an action using ε-greedy or Boltzmann exploration.

        Args:
            state:    State vector of shape (state_dim,).
            training: If True, apply exploration noise. False = pure greedy.

        Returns:
            Action ID in [0, NUM_ACTIONS).
        """
        if not HAS_TORCH or self.policy_net is None:
            return int(np.random.randint(0, self.config.action_dim))

        # BUG FIX: policy_net must be in eval() during inference so Dropout
        # is disabled. Original always ran in train mode, adding random noise
        # even during exploitation.
        self.policy_net.eval()
        with torch.no_grad():
            state_t  = torch.FloatTensor(state).unsqueeze(0).to(self.device)
            q_values = self.policy_net(state_t).cpu().numpy().flatten()
        if training:
            self.policy_net.train()

        self._last_q_values = q_values.copy()

        if training:
            if self.config.use_boltzmann:
                # Boltzmann (softmax) exploration — temperature anneals over episodes
                temp    = max(0.1, self.config.boltzmann_temp * (0.995 ** self.episode_count))
                shifted = q_values - q_values.max()          # numerical stability
                exp_q   = np.exp(shifted / temp)
                probs   = exp_q / exp_q.sum()
                action  = int(np.random.choice(self.config.action_dim, p=probs))
            else:
                # ε-greedy
                if np.random.random() < self.epsilon:
                    action = int(np.random.randint(0, self.config.action_dim))
                else:
                    action = int(np.argmax(q_values))
        else:
            action = int(np.argmax(q_values))

        strategy, threshold = decode_action(action)
        self._action_history.append({
            "action_id": action,
            "strategy":  strategy.value,
            "threshold": threshold,
            "q_values":  q_values.tolist(),
            "epsilon":   self.epsilon,
            "training":  training,
        })

        return action

    # ── Training ──────────────────────────────────────────────

    def train_step(
        self,
        states:      np.ndarray,
        actions:     np.ndarray,
        rewards:     np.ndarray,
        next_states: np.ndarray,
        dones:       np.ndarray,
        weights:     np.ndarray | None = None,
    ) -> tuple[float, np.ndarray]:
        """
        One gradient step on a batch from the replay buffer.

        Args:
            states:      (batch, state_dim)
            actions:     (batch,)   int
            rewards:     (batch,)   float
            next_states: (batch, state_dim)
            dones:       (batch,)   float  (1.0 = terminal)
            weights:     (batch,)   importance-sampling weights (PER)

        Returns:
            (loss_value, td_errors) — td_errors used for PER priority update.
        """
        if not HAS_TORCH or self.policy_net is None:
            return 0.0, np.zeros(len(states), dtype=np.float32)

        self.policy_net.train()

        s  = torch.FloatTensor(states).to(self.device)
        a  = torch.LongTensor(actions).to(self.device)
        r  = torch.FloatTensor(rewards).to(self.device)
        ns = torch.FloatTensor(next_states).to(self.device)
        d  = torch.FloatTensor(dones).to(self.device)
        w  = torch.FloatTensor(
            weights if weights is not None else np.ones(len(states), dtype=np.float32)
        ).to(self.device)

        # Current Q(s, a)
        current_q = self.policy_net(s).gather(1, a.unsqueeze(1)).squeeze(1)

        # Target: Double DQN — policy net picks action, target net scores it
        with torch.no_grad():
            next_actions = self.policy_net(ns).argmax(dim=1)
            next_q       = self.target_net(ns).gather(
                1, next_actions.unsqueeze(1)
            ).squeeze(1)
            # BUG FIX: original used (1 - d) which is correct BUT dones must
            # be float. Added explicit cast above; noted here for clarity.
            target_q = r + (1.0 - d) * self.config.gamma * next_q

        td_errors = (current_q - target_q).detach().cpu().numpy()

        # Huber loss with importance-sampling weights
        elementwise_loss = F.smooth_l1_loss(current_q, target_q, reduction="none")
        loss = (w * elementwise_loss).mean()

        self.optimizer.zero_grad()
        loss.backward()
        nn.utils.clip_grad_norm_(self.policy_net.parameters(), self.config.grad_clip)
        self.optimizer.step()

        self._soft_update()
        self.training_step += 1

        return float(loss.item()), td_errors

    def _soft_update(self) -> None:
        """θ_target ← τ·θ_policy + (1-τ)·θ_target"""
        if not HAS_TORCH or self.target_net is None:
            return
        tau = self.config.tau
        for t_param, p_param in zip(
            self.target_net.parameters(), self.policy_net.parameters()
        ):
            t_param.data.copy_(tau * p_param.data + (1.0 - tau) * t_param.data)

    def decay_epsilon(self) -> None:
        """Decay ε after each episode (call once per episode end)."""
        self.epsilon = max(
            self.config.epsilon_end,
            self.epsilon * self.config.epsilon_decay,
        )
        self.episode_count += 1

    # ── Explainability ────────────────────────────────────────

    def get_decision_trace(self) -> dict[str, Any]:
        """
        Return the last action's decision trace.

        Shows Q-values for every (strategy, threshold) pair, ranked by
        max Q-value, plus the selected action and exploration metadata.
        """
        if not self._action_history:
            return {"error": "No actions taken yet."}

        last   = self._action_history[-1]
        q_vals = last["q_values"]

        strategy_analysis = []
        for i, strategy in enumerate(STRATEGIES):
            strat_qs  = [q_vals[i * NUM_THRESHOLDS + j] for j in range(NUM_THRESHOLDS)]
            best_t_idx = int(np.argmax(strat_qs))
            strategy_analysis.append({
                "strategy":    strategy.value,
                "description": STRATEGY_DESCRIPTIONS[strategy],
                "q_values": {
                    f"threshold_{CONFIDENCE_THRESHOLDS[j]}": round(strat_qs[j], 4)
                    for j in range(NUM_THRESHOLDS)
                },
                "best_threshold": CONFIDENCE_THRESHOLDS[best_t_idx],
                "max_q":          round(float(max(strat_qs)), 4),
            })

        strategy_analysis.sort(key=lambda x: x["max_q"], reverse=True)

        return {
            "selected_action": {
                "strategy":  last["strategy"],
                "threshold": last["threshold"],
                "action_id": last["action_id"],
            },
            "exploration": {
                "epsilon":      round(float(last["epsilon"]), 4),
                "mode":         "boltzmann" if self.config.use_boltzmann else "epsilon_greedy",
                "was_training": last["training"],
            },
            "strategy_ranking": strategy_analysis,
            "q_value_spread":   round(float(max(q_vals) - min(q_vals)), 4),
            # BUG FIX: original used max(q_vals) as "confidence" which is
            # Q-value magnitude, not a probability. Renamed to "best_q" to
            # avoid misleading callers.
            "best_q": round(float(max(q_vals)), 4),
        }

    def get_q_values_for_state(self, state: np.ndarray) -> dict[str, float]:
        """Return Q-values for all 18 actions given a state vector."""
        if not HAS_TORCH or self.policy_net is None:
            return {}

        self.policy_net.eval()
        with torch.no_grad():
            state_t  = torch.FloatTensor(state).unsqueeze(0).to(self.device)
            q_values = self.policy_net(state_t).cpu().numpy().flatten()

        return {
            f"{decode_action(i)[0].value}_t{decode_action(i)[1]}": round(float(q), 4)
            for i, q in enumerate(q_values)
        }

    # ── Checkpointing ─────────────────────────────────────────

    def save_checkpoint(self, path: str | Path) -> None:
        """Save model weights, optimizer state, and training metadata."""
        if not HAS_TORCH or self.policy_net is None:
            return

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        torch.save({
            "policy_net":    self.policy_net.state_dict(),
            "target_net":    self.target_net.state_dict(),
            "optimizer":     self.optimizer.state_dict(),
            "epsilon":       self.epsilon,
            "training_step": self.training_step,
            "episode_count": self.episode_count,
            "config": {
                "state_dim":      self.config.state_dim,
                "action_dim":     self.config.action_dim,
                "learning_rate":  self.config.learning_rate,
                "gamma":          self.config.gamma,
                "epsilon_start":  self.config.epsilon_start,
                "epsilon_end":    self.config.epsilon_end,
                "epsilon_decay":  self.config.epsilon_decay,
                "tau":            self.config.tau,
                "batch_size":     self.config.batch_size,
                "grad_clip":      self.config.grad_clip,
            },
        }, str(path))

    def load_checkpoint(self, path: str | Path) -> None:
        """Load model weights and training metadata from a checkpoint."""
        if not HAS_TORCH or self.policy_net is None:
            return

        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Checkpoint not found: {path}")

        # BUG FIX: weights_only=False is needed for checkpoints that contain
        # non-tensor objects (optimizer state, config dict). Explicit map_location
        # ensures CPU checkpoints load correctly on GPU machines and vice versa.
        checkpoint = torch.load(
            str(path), map_location=self.device, weights_only=False
        )
        self.policy_net.load_state_dict(checkpoint["policy_net"])
        self.target_net.load_state_dict(checkpoint["target_net"])
        self.optimizer.load_state_dict(checkpoint["optimizer"])
        self.epsilon       = checkpoint["epsilon"]
        self.training_step = checkpoint["training_step"]
        self.episode_count = checkpoint["episode_count"]

        # Keep target net in eval mode after loading
        self.target_net.eval()

    # ── Info ──────────────────────────────────────────────────

    def get_info(self) -> dict[str, Any]:
        """Return agent metadata (safe to serialize to JSON)."""
        return {
            "type":           "Hierarchical DQN (Double DQN + soft update)",
            "state_dim":      self.config.state_dim,
            "action_dim":     self.config.action_dim,
            "num_strategies": NUM_STRATEGIES,
            "num_thresholds": NUM_THRESHOLDS,
            "epsilon":        round(self.epsilon, 4),
            "training_step":  self.training_step,
            "episode_count":  self.episode_count,
            "device":         str(self.device) if self.device else "cpu",
            "has_torch":      HAS_TORCH,
            "strategies":     [s.value for s in STRATEGIES],
            "thresholds":     CONFIDENCE_THRESHOLDS,
            "exploration":    "boltzmann" if self.config.use_boltzmann else "epsilon_greedy",
        }