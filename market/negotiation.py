"""Multi-round negotiation interface (Team B3) - interface skeleton.

Owner: B3 (Market, Auction and Negotiation).
Status: TODO. No counter offers, raise factor or producer step logic is
implemented in this skeleton.

``GridModel`` (Team A1) drives the rounds and calls :meth:`refine` before each
clearing. See ``docs/contracts.md``, section "Negotiation contract".
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Sequence

from market.auction import ClearingResult, MarketContext
from market.orders import Order


class NegotiationProtocol(ABC):
    """Contract for the multi-round negotiation behaviour."""

    @property
    @abstractmethod
    def rounds(self) -> int:
        """Maximum number of rounds, configured in ``simulation.rounds``."""

    @abstractmethod
    def refine(
        self,
        round: int,
        orders: Sequence[Order],
        previous: ClearingResult | None,
        context: MarketContext,
    ) -> list[Order]:
        """Adjust the orders of a negotiation round before clearing.

        Args:
            round: Current round, starting at ``2``.
            orders: Orders produced by the agents for this round.
            previous: Clearing result of the previous round, if any.
            context: Current market context.

        Returns:
            The orders to clear in this round.

        TODO(B3): implement counter offers, ``raise_factor`` and
        ``producer_step``.
        """


class StubNegotiation(NegotiationProtocol):
    """Removed identity stub, kept only for import compatibility.

    ``core/model.py`` imports this symbol. The bootstrap stub returned the
    orders unchanged, which the skeleton phase does not allow because it could
    be mistaken for the official negotiation.

    TODO(B3): delete this class once ``GridModel`` no longer imports it, or
    replace it with the real negotiation protocol.
    """

    def __init__(self, rounds: int) -> None:
        """Store the configured number of rounds.

        Args:
            rounds: Maximum number of negotiation rounds.
        """

        self._rounds = rounds

    @property
    def rounds(self) -> int:
        """Maximum number of rounds, configured in ``simulation.rounds``."""

        return self._rounds

    def refine(
        self,
        round: int,
        orders: Sequence[Order],
        previous: ClearingResult | None,
        context: MarketContext,
    ) -> list[Order]:
        """Not implemented; see :class:`NegotiationProtocol`."""

        raise NotImplementedError(
            "TODO(B3): negotiation is not implemented in the skeleton; "
            "inject a NegotiationProtocol implementation"
        )
