"""Double-auction market, uniform pricing and settlement (Team B3).

The clearing algorithm follows section 6.2 of the project guide:

* bids are sorted by descending price and ascending priority;
* asks are sorted by ascending price;
* the highest bid is matched with the cheapest ask while ``bid >= ask``;
* all trades of the round use the uniform price ``(last_bid + last_ask) / 2``;
* if nothing matches, the previous clearing price is kept.

Settlement splits a consumer shortfall into flexible deferred energy and
inflexible unserved energy, and produces zero-sum payments per agent.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from market.orders import Order, Trade

EPSILON = 1e-9


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
        price: Uniform clearing price of the round, the midpoint of the last
            matched bid and ask, currency per MWh.
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
        """Clear one negotiation round."""

    @abstractmethod
    def settle(
        self,
        context: MarketContext,
        trades: Sequence[Trade],
        price: float,
    ) -> Settlement:
        """Turn the final trades into a settlement."""


class DoubleAuction(MarketInterface):
    """Uniform-price double auction with partial matching."""

    def __init__(self, config: Mapping[str, Any] | None = None) -> None:
        """Create the auction.

        Args:
            config: Validated configuration; the ``market`` section is stored
                for reference and diagnostics.
        """

        self._config = dict(config or {})
        self._last_price = 0.0
        self.last_context: MarketContext | None = None
        self.last_settlement: Settlement | None = None
        self.rounds_cleared: list[int] = []

    @property
    def last_price(self) -> float:
        """Clearing price of the most recent round."""

        return self._last_price

    def clear(
        self,
        orders: Sequence[Order],
        round: int,
        context: MarketContext,
    ) -> ClearingResult:
        """Clear one negotiation round and return the matched trades."""

        self.last_context = context
        self.rounds_cleared.append(int(round))
        bids = sorted(
            (order for order in orders if order.side == "buy"),
            key=lambda order: (-float(order.price), int(order.priority), order.agent_id),
        )
        asks = sorted(
            (order for order in orders if order.side == "sell"),
            key=lambda order: (float(order.price), int(order.priority), order.agent_id),
        )

        matched: list[tuple[str, str, float, float, float]] = []
        bid_index = ask_index = 0
        bid_remaining = float(bids[0].qty_mw) if bids else 0.0
        ask_remaining = float(asks[0].qty_mw) if asks else 0.0
        last_bid = last_ask = 0.0

        while (
            bid_index < len(bids)
            and ask_index < len(asks)
            and float(bids[bid_index].price) >= float(asks[ask_index].price)
        ):
            quantity = min(bid_remaining, ask_remaining)
            if quantity > EPSILON:
                matched.append(
                    (
                        bids[bid_index].agent_id,
                        asks[ask_index].agent_id,
                        float(quantity),
                        float(bids[bid_index].price),
                        float(asks[ask_index].price),
                    )
                )
                last_bid = float(bids[bid_index].price)
                last_ask = float(asks[ask_index].price)
            bid_remaining -= quantity
            ask_remaining -= quantity
            if bid_remaining <= EPSILON:
                bid_index += 1
                bid_remaining = float(bids[bid_index].qty_mw) if bid_index < len(bids) else 0.0
            if ask_remaining <= EPSILON:
                ask_index += 1
                ask_remaining = float(asks[ask_index].qty_mw) if ask_index < len(asks) else 0.0

        if matched:
            price = (last_bid + last_ask) / 2.0
        else:
            price = self._last_price
        self._last_price = float(price)
        trades = tuple(
            Trade(buyer_id=buyer, seller_id=seller, qty_mw=quantity, price=float(price))
            for buyer, seller, quantity, _, _ in matched
        )
        return ClearingResult(
            round=int(round),
            price=float(price),
            trades=trades,
            cleared_mw=float(sum(trade.qty_mw for trade in trades)),
        )

    def settle(
        self,
        context: MarketContext,
        trades: Sequence[Trade],
        price: float,
    ) -> Settlement:
        """Compute unserved/deferred energy and zero-sum payments."""

        bought: dict[str, float] = {}
        sold: dict[str, float] = {}
        payments: dict[str, float] = {agent_id: 0.0 for agent_id in context.demand_mw}
        for trade in trades:
            bought[trade.buyer_id] = bought.get(trade.buyer_id, 0.0) + float(trade.qty_mw)
            sold[trade.seller_id] = sold.get(trade.seller_id, 0.0) + float(trade.qty_mw)
            payments[trade.buyer_id] = payments.get(trade.buyer_id, 0.0) + float(
                trade.qty_mw
            ) * float(trade.price)
            payments[trade.seller_id] = payments.get(trade.seller_id, 0.0) - float(
                trade.qty_mw
            ) * float(trade.price)

        unserved: dict[str, float] = {}
        deferred: dict[str, float] = {}
        for agent_id, demand in context.demand_mw.items():
            demand = max(0.0, float(demand))
            shortfall = max(0.0, demand - bought.get(agent_id, 0.0))
            if shortfall <= EPSILON:
                shortfall = 0.0
            flexible = demand * float(context.flexibility.get(agent_id, 0.0))
            deferred_mw = min(shortfall, flexible)
            unserved[agent_id] = float(shortfall - deferred_mw)
            deferred[agent_id] = float(deferred_mw)

        settlement = Settlement(
            price=float(price),
            trades=tuple(trades),
            unserved=unserved,
            deferred=deferred,
            payments=payments,
        )
        self.last_settlement = settlement
        return settlement


class MockAuction(DoubleAuction):
    """Labelled orchestration-only alias of the real double auction.

    ``mode="mock"`` must never be used for experimental results. The class is
    kept because ``core.model`` imports it for the frozen constructor
    signature, and it delegates to the real auction instead of faking results.
    """


__all__ = [
    "ClearingResult",
    "DoubleAuction",
    "MarketContext",
    "MarketInterface",
    "MockAuction",
    "Settlement",
]
