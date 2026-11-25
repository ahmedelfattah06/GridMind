"""Storage agents and the pluggable storage policy (Team B2).

A battery buys to charge and sells to discharge. Charging and discharging are
limited by capacity, power rate and efficiency:

``soc(t+1) = soc(t) + efficiency*charge - discharge/efficiency``

with ``soc`` stored as a ratio in ``[0, 1]`` and converted to MWh through the
configured capacity. The decision comes from a :class:`StoragePolicy`, which
makes the rule-based baseline and the tabular Q-learning policy
interchangeable without touching the storage agent.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Mapping

from agents.base import BaseAgent
from market.orders import Order

EPSILON = 1e-9


class StoragePolicy(ABC):
    """Decision policy for one storage agent."""

    @abstractmethod
    def act(self, obs: dict[str, Any]) -> int:
        """Return 0 (wait), 1 (charge) or 2 (discharge)."""

    def update(self, result: dict[str, Any], agent: "StorageAgent") -> None:
        """Receive the settlement of the step. Default is a no-op."""


class RulePolicy(StoragePolicy):
    """Fixed mean-reversion rule from the project guide.

    Charge when the last price is below ``low_ratio`` times the 24 hour mean,
    discharge when it is above ``high_ratio`` times the mean, otherwise wait.
    """

    def __init__(self, config: Mapping[str, Any]) -> None:
        """Create the rule policy from configuration."""

        policy = config.get("storage_policy", {}) if isinstance(config, Mapping) else {}
        self._low_ratio = float(policy.get("low_price_ratio", 0.85))
        self._high_ratio = float(policy.get("high_price_ratio", 1.15))

    @property
    def low_ratio(self) -> float:
        """Charge below this fraction of the 24 hour mean price."""

        return self._low_ratio

    @property
    def high_ratio(self) -> float:
        """Discharge above this fraction of the 24 hour mean price."""

        return self._high_ratio

    def act(self, obs: dict[str, Any]) -> int:
        """Select charge, discharge or wait from the price history."""

        own = obs.get("own_agent", {})
        average = float(own.get("avg_price_24h", 0.0))
        last_price = float(obs.get("last_price", 0.0))
        if average <= EPSILON:
            return 0
        if last_price < self._low_ratio * average:
            return 1
        if last_price > self._high_ratio * average:
            return 2
        return 0


class StorageAgent(BaseAgent):
    """Battery agent with capacity, rate and efficiency limits."""

    def __init__(
        self,
        spec: Mapping[str, Any],
        config: Mapping[str, Any],
        seed: int = 0,
        policy: StoragePolicy | None = None,
    ) -> None:
        """Create a storage agent.

        Args:
            spec: Resolved agent specification.
            config: Full validated configuration.
            seed: Simulation seed (used by learning policies).
            policy: Optional decision policy; defaults to :class:`RulePolicy`.
        """

        self._spec = dict(spec)
        self._config = config
        self._capacity_mwh = float(spec["capacity_mwh"])
        self._max_rate_mw = float(spec["max_rate_mw"])
        self._efficiency = float(spec["efficiency"])
        self._soc = float(spec["initial_soc"])
        self._seed = int(seed)
        self._flex_price = float(config["max_prices"]["flex"])
        self._raise_factor = float(config["market"]["raise_factor"])
        self._producer_step = float(config["market"]["producer_step"])
        self._policy: StoragePolicy = policy if policy is not None else RulePolicy(config)
        self._price_history: list[float] = []
        self._last_action = 0
        self._step_action: int | None = None
        self._last_bought_mw = 0.0
        self._last_sold_mw = 0.0
        super().__init__(
            agent_id=str(spec["id"]),
            role="storage",
            agent_type=str(spec["type"]),
        )

    @property
    def state_of_charge(self) -> float:
        """Current state of charge as a ratio in ``[0, 1]``."""

        return self._soc

    @property
    def capacity_mwh(self) -> float:
        """Usable battery capacity in MWh."""

        return self._capacity_mwh

    @property
    def avg_price_24h(self) -> float:
        """Mean clearing price over the most recent (at most) 24 hours."""

        if not self._price_history:
            return 0.0
        return float(sum(self._price_history) / len(self._price_history))

    @property
    def policy(self) -> StoragePolicy:
        """The active decision policy."""

        return self._policy

    def set_policy(self, policy: StoragePolicy) -> None:
        """Replace the decision policy without changing the agent."""

        if not isinstance(policy, StoragePolicy):
            raise TypeError("policy must implement StoragePolicy")
        self._policy = policy

    def _on_observe(self, obs: dict[str, Any]) -> None:
        # Observation construction happens before the new step is executed, so
        # the price history must already contain the price that was settled at
        # the end of the previous step. It is appended in ``_on_update`` below.
        self._step_action = None

    def _reference_price(self) -> float:
        average = self.avg_price_24h
        if average > EPSILON:
            return average
        if self._last_price > EPSILON:
            return self._last_price
        return 1.0

    def decide(self, round: int) -> list[Order]:
        """Translate the policy action into a buy or sell order.

        Args:
            round: Negotiation round, starting at ``1``.
        """

        if round < 1:
            raise ValueError(f"round must be positive, got {round}")
        # A policy is queried once per simulated hour, not once per negotiation
        # round. Repeated calls would make a learning policy close several
        # transitions for the same state and attribute the step reward to the
        # last round only.
        if self._step_action is None:
            observation = self._observation or {}
            action = int(self._policy.act(observation))
            if action not in (0, 1, 2):
                raise ValueError(f"storage policy returned unknown action {action!r}")
            self._step_action = action
            self._last_action = action
        action = self._step_action

        reference = self._reference_price()
        if action == 1:
            headroom_mwh = max(0.0, (1.0 - self._soc) * self._capacity_mwh)
            max_charge = min(self._max_rate_mw, headroom_mwh / self._efficiency)
            if max_charge <= EPSILON:
                return []
            price = min(
                self._flex_price,
                reference * (self._raise_factor ** (round - 1)),
            )
            return [
                Order(
                    agent_id=self.agent_id,
                    side="buy",
                    qty_mw=float(max_charge),
                    price=float(max(0.0, price)),
                    priority=4,
                    round=round,
                )
            ]
        if action == 2:
            available_mwh = self._soc * self._capacity_mwh
            max_discharge = min(self._max_rate_mw, available_mwh * self._efficiency)
            if max_discharge <= EPSILON:
                return []
            price = reference * ((1.0 - self._producer_step) ** (round - 1))
            return [
                Order(
                    agent_id=self.agent_id,
                    side="sell",
                    qty_mw=float(max_discharge),
                    price=float(max(0.0, price)),
                    priority=4,
                    round=round,
                )
            ]
        return []

    def _on_update(self, result: dict[str, Any]) -> None:
        bought = float(result.get("bought_mw", 0.0))
        sold = float(result.get("sold_mw", 0.0))
        delta = (self._efficiency * bought - sold / self._efficiency) / self._capacity_mwh
        self._soc = float(min(1.0, max(0.0, self._soc + delta)))
        self._last_bought_mw = bought
        self._last_sold_mw = sold
        self._policy.update(result, self)
        self._last_price = float(result.get("price", self._last_price))
        if self._last_price > 0.0:
            self._price_history.append(self._last_price)
            if len(self._price_history) > 24:
                self._price_history.pop(0)

    def snapshot(self) -> dict[str, Any]:
        """Return the public storage state, including the contract SoC."""

        payload = super().snapshot()
        payload.update(
            {
                "soc": float(self._soc),
                "soc_mwh": float(self._soc * self._capacity_mwh),
                "capacity_mwh": float(self._capacity_mwh),
                "max_rate_mw": float(self._max_rate_mw),
                "efficiency": float(self._efficiency),
                "avg_price_24h": float(self.avg_price_24h),
                "last_action": int(self._last_action),
                "bought_mw": float(self._last_bought_mw),
                "sold_mw": float(self._last_sold_mw),
                "policy": type(self._policy).__name__,
            }
        )
        return payload
