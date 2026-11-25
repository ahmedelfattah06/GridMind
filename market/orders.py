"""Market domain objects shared by every team - frozen contract.

Owner: B3 (Market, Auction and Negotiation) for the market algorithm. The
:class:`Order` and :class:`Trade` structures themselves are frozen integration
contracts (see ``docs/contracts.md``, section "Order and Trade").

Status: CONTRACT ONLY. ``__post_init__`` enforces the frozen field constraints;
no market, auction or settlement logic is implemented here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

Side = Literal["buy", "sell"]
VALID_SIDES: tuple[str, ...] = ("buy", "sell")


@dataclass(frozen=True)
class Order:
    """One bid or ask submitted to the market.

    Attributes:
        agent_id: Id of the submitting agent.
        side: ``"buy"`` for demand, ``"sell"`` for supply.
        qty_mw: Requested energy for this hour, in MW. Must be positive.
        price: Limit price in currency units per MWh. Must be non-negative.
        priority: Lower values are served first. Consumers use hospital
            ``1``, residential ``2``, factory ``3`` and flexible ``4``;
            producers and storage use ``4``. Defaults to ``0``.
        round: Negotiation round in which the order was submitted, starting
            at ``1``.
    """

    agent_id: str
    side: Side
    qty_mw: float
    price: float
    priority: int = 0
    round: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.agent_id, str) or not self.agent_id:
            raise ValueError("order agent_id must be a non-empty string")
        if self.side not in VALID_SIDES:
            raise ValueError(f"order side must be one of {VALID_SIDES}, got {self.side!r}")
        _validate_positive(self.qty_mw, "order qty_mw")
        _validate_non_negative(self.price, "order price")
        if isinstance(self.priority, bool) or not isinstance(self.priority, int):
            raise ValueError("order priority must be an integer")
        if isinstance(self.round, bool) or not isinstance(self.round, int) or self.round < 1:
            raise ValueError("order round must be a positive integer")


@dataclass(frozen=True)
class Trade:
    """One executed bilateral trade for a single simulation hour.

    Attributes:
        buyer_id: Consumer or storage agent that buys energy.
        seller_id: Producer or storage agent that sells energy.
        qty_mw: Traded energy for this hour, in MWh. Must be positive.
        price: Agreed price in currency units per MWh. Must be non-negative.
    """

    buyer_id: str
    seller_id: str
    qty_mw: float
    price: float

    def __post_init__(self) -> None:
        if not isinstance(self.buyer_id, str) or not self.buyer_id:
            raise ValueError("trade buyer_id must be a non-empty string")
        if not isinstance(self.seller_id, str) or not self.seller_id:
            raise ValueError("trade seller_id must be a non-empty string")
        _validate_positive(self.qty_mw, "trade qty_mw")
        _validate_non_negative(self.price, "trade price")


def _validate_positive(value: Any, label: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a number, got {value!r}")
    if float(value) <= 0.0 or float(value) != float(value):
        raise ValueError(f"{label} must be a positive finite number, got {value!r}")


def _validate_non_negative(value: Any, label: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a number, got {value!r}")
    if float(value) < 0.0 or float(value) != float(value):
        raise ValueError(f"{label} must be a non-negative finite number, got {value!r}")
