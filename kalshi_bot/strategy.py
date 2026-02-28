"""Trading strategies for the Kalshi bot.

Each strategy receives a :class:`~kalshi_bot.models.Market` (plus an optional
order-book snapshot) and returns a trading signal:

    * ``Signal.BUY_YES``  – buy YES contracts
    * ``Signal.BUY_NO``   – buy NO contracts
    * ``Signal.HOLD``     – do nothing
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

from .models import Market, OrderBook

logger = logging.getLogger(__name__)


class Signal(Enum):
    """Trading signal produced by a strategy."""

    BUY_YES = "buy_yes"
    BUY_NO = "buy_no"
    HOLD = "hold"


@dataclass
class TradeSignal:
    """Full signal including suggested price and size."""

    signal: Signal
    suggested_price: int  # cents
    suggested_quantity: int
    reason: str = ""

    @property
    def is_actionable(self) -> bool:
        return self.signal != Signal.HOLD


class BaseStrategy:
    """Abstract base class for all strategies."""

    def evaluate(self, market: Market, book: Optional[OrderBook] = None) -> TradeSignal:
        raise NotImplementedError


class MidPriceReversion(BaseStrategy):
    """Simple mean-reversion strategy based on the YES mid price.

    * If mid price < ``low_threshold`` → signal BUY_YES (market looks cheap)
    * If mid price > ``high_threshold`` → signal BUY_NO  (YES looks expensive)
    * Otherwise → HOLD

    Prices and thresholds are in *cents* (1-99).
    """

    def __init__(
        self,
        low_threshold: int = 35,
        high_threshold: int = 65,
        order_quantity: int = 5,
    ) -> None:
        self.low_threshold = low_threshold
        self.high_threshold = high_threshold
        self.order_quantity = order_quantity

    def evaluate(self, market: Market, book: Optional[OrderBook] = None) -> TradeSignal:
        mid = market.mid_price

        if mid < self.low_threshold:
            price = int(market.yes_ask)
            logger.debug(
                "%s mid=%.1f < %d → BUY_YES @ %d",
                market.ticker,
                mid,
                self.low_threshold,
                price,
            )
            return TradeSignal(
                signal=Signal.BUY_YES,
                suggested_price=price,
                suggested_quantity=self.order_quantity,
                reason=f"mid {mid:.1f} below low threshold {self.low_threshold}",
            )

        if mid > self.high_threshold:
            price = int(market.no_ask)
            logger.debug(
                "%s mid=%.1f > %d → BUY_NO @ %d",
                market.ticker,
                mid,
                self.high_threshold,
                price,
            )
            return TradeSignal(
                signal=Signal.BUY_NO,
                suggested_price=price,
                suggested_quantity=self.order_quantity,
                reason=f"mid {mid:.1f} above high threshold {self.high_threshold}",
            )

        return TradeSignal(
            signal=Signal.HOLD,
            suggested_price=0,
            suggested_quantity=0,
            reason=f"mid {mid:.1f} within band [{self.low_threshold}, {self.high_threshold}]",
        )


class SpreadCapture(BaseStrategy):
    """Market-making strategy that posts limit orders on both sides of the spread.

    Places a buy order just above the best bid and a sell order just below the
    best ask, capturing the spread when both legs fill.

    Only active when:
    * the spread is at least ``min_spread`` cents wide, and
    * the book has liquidity on both sides.
    """

    def __init__(
        self,
        min_spread: int = 3,
        edge: int = 1,
        order_quantity: int = 3,
    ) -> None:
        self.min_spread = min_spread
        self.edge = edge
        self.order_quantity = order_quantity

    def evaluate(self, market: Market, book: Optional[OrderBook] = None) -> TradeSignal:
        if book is None or book.spread is None:
            return TradeSignal(Signal.HOLD, 0, 0, "no book data")

        spread = book.spread
        if spread < self.min_spread:
            return TradeSignal(Signal.HOLD, 0, 0, f"spread {spread} < min {self.min_spread}")

        bid_price = (book.best_bid or 1) + self.edge
        bid_price = max(1, min(bid_price, 99))

        logger.debug(
            "%s spread=%d → SpreadCapture BUY_YES @ %d",
            market.ticker,
            spread,
            bid_price,
        )
        return TradeSignal(
            signal=Signal.BUY_YES,
            suggested_price=bid_price,
            suggested_quantity=self.order_quantity,
            reason=f"spread {spread} >= min {self.min_spread}, bid+edge={bid_price}",
        )


class CompositeStrategy(BaseStrategy):
    """Run multiple strategies and return the first actionable signal."""

    def __init__(self, strategies: List[BaseStrategy]) -> None:
        self._strategies = strategies

    def evaluate(self, market: Market, book: Optional[OrderBook] = None) -> TradeSignal:
        for strategy in self._strategies:
            result = strategy.evaluate(market, book)
            if result.is_actionable:
                return result
        return TradeSignal(Signal.HOLD, 0, 0, "no strategy triggered")
