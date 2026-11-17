"""Market clearing interface (Team B3) - interface skeleton.

Owner: B3 (Market, Auction and Negotiation).
Status: TODO. No double auction, negotiation, settlement or raise-factor logic
is implemented in this skeleton.

The data structures below are the frozen integration contract shared with
``GridModel`` (Team A1) and the central planner adapter (Team C1). See
``docs/contracts.md``, section "Market contract".
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from market.orders import Order, Trade


@dataclass(frozen=True)
class MarketContext:
    """Read-only view of the simulation state needed to clear the market.

    Attributes:
        t: Current simulation step.
        demand_mw: Requested demand per consumer agent, in MW.
        generation_mw: Available generation per producer agent, in MW.
        flexibility: Flexibility ratio per consumer agent, in ``[0, 1]``.
        consumer_types: Consumer agent id to consumer type.
        producer_types: Producer agent id to producer type.
        storage_soc: Storage agent id to state of charge, in ``[0, 1]``.
        voll: Value of lost load per consumer type, currency per MWh.
        max_price: Bid ceiling per consumer type, currency per MWh.
        settings: The ``market`` configuration section.
    """

    t: int
    demand_mw: Mapping[str, float]
    generation_mw: Mapping[str, float]
    flexibility: Mapping[str, float]
    consumer_types: Mapping[str, str]
    producer_types: Mapping[str, str]
    storage_soc: Mapping[str, float] = field(default_factory=dict)
    voll: Mapping[str, float] = field(default_factory=dict)
    max_price: Mapping[str, float] = field(default_factory=dict)
    settings: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ClearingResult:
    """Outcome of clearing one negotiation round.

    Attributes:
        round: Negotiation round that produced the result.
        price: Quantity weighted clearing price, currency per MWh.
        trades: Matched trades, in matching order.
        cleared_mw: Total traded volume in MW.
    """

    round: int
    price: float
    trades: tuple[Trade, ...] = ()
    cleared_mw: float = 0.0


@dataclass(frozen=True)
class Settlement:
    """Financial and energy settlement of one simulation step.

    Attributes:
        price: Final clearing price, currency per MWh.
        trades: Trades of the final round.
        unserved: Unserved energy per consumer agent, in MW.
        deferred: Deferred (flexible) energy per consumer agent, in MW.
        payments: Net payment per agent, positive means the agent pays.
    """

    price: float
    trades: tuple[Trade, ...]
    unserved: dict[str, float]
    deferred: dict[str, float]
    payments: dict[str, float]


class MarketInterface(ABC):
    """Contract that every GridMind market implementation must satisfy."""

    @abstractmethod
    def clear(
        self,
        orders: Sequence[Order],
        round: int,
        context: MarketContext,
    ) -> ClearingResult:
        """Clear one negotiation round.

        Args:
            orders: Orders submitted in this round.
            round: Round number, starting at ``1``.
            context: Current market context.

        Returns:
            The clearing outcome of this round.

        TODO(B3): implement the official double auction.
        """

    @abstractmethod
    def settle(
        self,
        context: MarketContext,
        trades: Sequence[Trade],
        price: float,
    ) -> Settlement:
        """Turn the final trades into a settlement.

        Args:
            context: Current market context.
            trades: Trades of the final round.
            price: Final clearing price.

        Returns:
            The settlement of this step.

        TODO(B3): implement the settlement and the deferred/unserved split.
        """


class MockAuction(MarketInterface):
    """Removed orchestration stub, kept only for import compatibility.

    ``core/model.py`` imports this symbol. The bootstrap mock performed greedy
    matching, which the skeleton phase does not allow because it could be
    mistaken for the official auction.

    TODO(B3): delete this class once ``GridModel`` no longer imports it, or
    replace it with the real double auction.
    """

    def clear(
        self,
        orders: Sequence[Order],
        round: int,
        context: MarketContext,
    ) -> ClearingResult:
        """Not implemented; see :class:`MarketInterface`."""

        raise NotImplementedError(
            "TODO(B3): the auction is not implemented in the skeleton; "
            "inject a MarketInterface implementation"
        )

    def settle(
        self,
        context: MarketContext,
        trades: Sequence[Trade],
        price: float,
    ) -> Settlement:
        """Not implemented; see :class:`MarketInterface`."""

        raise NotImplementedError(
            "TODO(B3): the settlement is not implemented in the skeleton; "
            "inject a MarketInterface implementation"
        )
