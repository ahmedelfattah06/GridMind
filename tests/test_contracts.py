"""Frozen integration-contract tests (no unfinished component is required).

These tests instantiate only the frozen data structures and the validated
market domain objects. They never execute ``GridModel``, an agent policy, the
auction, the LP or Q-learning.

Ownership: shared contract tests, guarded by A3 (test ownership). See
``tests/README.md``.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from core.model import StepResult
from market.orders import Order, Trade

STEP_RESULT_FIELDS = {
    "t",
    "price",
    "supply_mw",
    "demand_mw",
    "unserved",
    "deferred",
    "trades",
    "orders",
    "messages",
    "soc",
    "generation",
}


def test_order_validation() -> None:
    with pytest.raises(ValueError, match="qty_mw"):
        Order(agent_id="a", side="buy", qty_mw=0.0, price=10.0)
    with pytest.raises(ValueError, match="side"):
        Order(agent_id="a", side="hold", qty_mw=1.0, price=10.0)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="round"):
        Order(agent_id="a", side="buy", qty_mw=1.0, price=10.0, round=0)


def test_trade_validation() -> None:
    with pytest.raises(ValueError, match="qty_mw"):
        Trade(buyer_id="a", seller_id="b", qty_mw=-1.0, price=10.0)


def test_step_result_has_the_frozen_fields_and_is_immutable() -> None:
    result = StepResult(
        t=0,
        price=0.0,
        supply_mw=0.0,
        demand_mw=0.0,
        unserved={},
        deferred={},
        trades=[],
        orders=[],
        messages=0,
        soc={},
        generation={},
    )

    assert set(StepResult.__dataclass_fields__) == STEP_RESULT_FIELDS
    with pytest.raises(FrozenInstanceError):
        result.price = 999.0  # type: ignore[misc]
