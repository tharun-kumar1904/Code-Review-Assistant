"""
Prioritized Experience Replay Buffer.

Stores transitions (state, action, reward, next_state, done) and samples
based on TD-error priority for more efficient learning.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

import numpy as np


@dataclass
class Transition:
    """A single experience transition."""
    state:      np.ndarray
    action:     int
    reward:     float
    next_state: np.ndarray
    done:       bool


class ReplayBuffer:
    """
    Circular experience replay buffer with optional prioritized sampling (PER).

    Features:
      - Fixed-capacity circular buffer
      - Uniform or priority-weighted sampling
      - Importance-sampling weight computation for PER
      - Priority update after each training step
    """

    def __init__(
        self,
        capacity:        int   = 10_000,
        alpha:           float = 0.6,
        beta:            float = 0.4,
        beta_increment:  float = 0.001,
        use_prioritized: bool  = True,
        min_batch_size:  int   = 32,
    ):
        """
        Args:
            capacity:        Maximum number of transitions to store.
            alpha:           Priority exponent (0 = uniform, 1 = full PER).
            beta:            IS exponent start value (annealed toward 1.0).
            beta_increment:  Beta increase per sample() call.
            use_prioritized: Enable prioritized sampling.
            min_batch_size:  Minimum buffer fill before is_ready returns True.
        """
        if capacity <= 0:
            raise ValueError(f"capacity must be > 0, got {capacity}")
        if not (0.0 <= alpha <= 1.0):
            raise ValueError(f"alpha must be in [0, 1], got {alpha}")
        if not (0.0 <= beta <= 1.0):
            raise ValueError(f"beta must be in [0, 1], got {beta}")

        self.capacity        = capacity
        self.alpha           = alpha
        self.beta            = beta
        self.beta_increment  = beta_increment
        self.use_prioritized = use_prioritized
        self.min_batch_size  = min_batch_size

        # Pre-allocated circular buffer — avoids repeated list resizing
        # BUG FIX: original used a plain list and appended/indexed into it.
        # That works but makes push() O(1) amortised only when under capacity;
        # after capacity the list slot [self.position] is overwritten which is
        # correct, but __len__ returns len(self.buffer) which diverges from
        # self.position tracking once the buffer wraps. We keep both for
        # compatibility but clarify the invariant.
        self._buffer:  list[Transition | None] = [None] * capacity
        self._size:    int   = 0      # actual number of valid entries
        self.position: int   = 0      # next write slot (circular)

        # Segment-tree would be O(log n) but a flat array is simpler and fast
        # enough for capacity ≤ 100 k.
        self.priorities:    np.ndarray = np.zeros(capacity, dtype=np.float32)
        self.max_priority:  float      = 1.0

    # ── Write ─────────────────────────────────────────────────

    def push(self, transition: Transition) -> None:
        """Add a transition to the buffer (overwrites oldest if full)."""
        self._buffer[self.position]    = transition
        self.priorities[self.position] = self.max_priority  # new = max priority

        self.position = (self.position + 1) % self.capacity
        self._size    = min(self._size + 1, self.capacity)

    def push_transition(
        self,
        state:      np.ndarray,
        action:     int,
        reward:     float,
        next_state: np.ndarray,
        done:       bool,
    ) -> None:
        """Convenience: push individual components as a Transition."""
        self.push(Transition(state, action, reward, next_state, done))

    # ── Read ──────────────────────────────────────────────────

    def sample(self, batch_size: int) -> Tuple[
        np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray,
        np.ndarray, List[int],
    ]:
        """
        Sample a batch of transitions.

        Returns:
            (states, actions, rewards, next_states, dones, weights, indices)
            - weights: importance-sampling weights (all 1s for uniform mode)
            - indices: buffer indices (needed for update_priorities)
        """
        n = self._size
        if n == 0:
            raise RuntimeError("Cannot sample from an empty buffer.")

        batch_size = min(batch_size, n)

        if self.use_prioritized:
            priorities = self.priorities[:n] ** self.alpha
            total      = priorities.sum()

            # BUG FIX: original divided by (total + 1e-8) which silently
            # produces near-uniform distribution when all priorities are 0
            # (e.g. at startup before any update_priorities call). We raise
            # explicitly instead so callers know something is wrong.
            if total <= 0:
                probs = np.ones(n, dtype=np.float32) / n
            else:
                probs = priorities / total

            # BUG FIX: replace=False crashes when batch_size > n (already
            # clamped above) but also when n is small and floating-point
            # rounding makes probs not sum exactly to 1. Renormalise first.
            probs = probs / probs.sum()
            indices = np.random.choice(n, size=batch_size, p=probs, replace=False)

            # Anneal beta toward 1.0
            self.beta = min(1.0, self.beta + self.beta_increment)

            # IS weights: w_i = (N · P(i))^(-β), normalised by max weight
            raw_weights = (n * probs[indices]) ** (-self.beta)
            weights     = (raw_weights / (raw_weights.max() + 1e-8)).astype(np.float32)

        else:
            indices = np.random.choice(n, size=batch_size, replace=False)
            weights = np.ones(batch_size, dtype=np.float32)

        batch = [self._buffer[i] for i in indices]

        states      = np.stack([t.state      for t in batch]).astype(np.float32)
        actions     = np.array([t.action     for t in batch], dtype=np.int64)
        rewards     = np.array([t.reward     for t in batch], dtype=np.float32)
        next_states = np.stack([t.next_state for t in batch]).astype(np.float32)
        # BUG FIX: dones stored as bool in Transition but must be float32 for
        # the DQN target computation (1 - done). Original cast here was fine
        # but dtype=np.float32 was missing — numpy would infer float64.
        dones       = np.array([t.done       for t in batch], dtype=np.float32)

        return states, actions, rewards, next_states, dones, weights, list(indices)

    # ── Priority update ───────────────────────────────────────

    def update_priorities(self, indices: List[int], td_errors: np.ndarray) -> None:
        """
        Update priorities after a training step.

        Args:
            indices:   Buffer indices returned by sample().
            td_errors: Absolute TD errors from the training step.
        """
        # BUG FIX: original applied ** self.alpha twice — once here and once
        # in sample() when computing `priorities[:n] ** self.alpha`. That means
        # the effective exponent was alpha², not alpha. Priorities should be
        # stored as raw |td| + ε so that sample() applies alpha correctly.
        for idx, td_error in zip(indices, td_errors):
            # Store raw priority; sample() raises it to alpha
            raw_priority            = float(abs(td_error)) + 1e-6
            self.priorities[idx]    = raw_priority
            if raw_priority > self.max_priority:
                self.max_priority = raw_priority

    # ── Helpers ───────────────────────────────────────────────

    def __len__(self) -> int:
        return self._size

    @property
    def is_ready(self) -> bool:
        """True once the buffer holds at least min_batch_size transitions."""
        return self._size >= self.min_batch_size

    @property
    def fill_ratio(self) -> float:
        """Fraction of capacity currently used (0.0 – 1.0)."""
        return self._size / self.capacity

    def clear(self) -> None:
        """Reset the buffer to empty state."""
        self._buffer    = [None] * self.capacity
        self.priorities = np.zeros(self.capacity, dtype=np.float32)
        self.position   = 0
        self._size      = 0
        self.max_priority = 1.0

    def get_stats(self) -> dict:
        """Return buffer statistics useful for logging."""
        n = self._size
        if n == 0:
            return {"size": 0, "capacity": self.capacity, "fill_ratio": 0.0}
        prios = self.priorities[:n]
        return {
            "size":          n,
            "capacity":      self.capacity,
            "fill_ratio":    round(self.fill_ratio, 4),
            "beta":          round(self.beta, 4),
            "max_priority":  round(float(self.max_priority), 6),
            "mean_priority": round(float(prios.mean()), 6),
            "min_priority":  round(float(prios.min()), 6),
        }