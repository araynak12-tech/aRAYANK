"""Lightweight data models used throughout the bot."""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Market:
    """A single Kalshi prediction-market contract."""

    ticker: str
    title: str
    status: str  # "open" | "closed" | "settled"
    yes_bid: float  # best bid for the YES side in cents (1-99)
    yes_ask: float  # best ask for the YES side in cents (1-99)
    no_bid: float
    no_ask: float
    volume: int  # total contracts traded
    open_interest: int

    @property
    def mid_price(self) -> float:
        """Mid-market price of the YES side in cents."""
        return (self.yes_bid + self.yes_ask) / 2.0


@dataclass
class OrderBookLevel:
    """A single price level inside an order book."""

    price: int  # cents (1-99)
    quantity: int


@dataclass
class OrderBook:
    """Snapshot of one side of a market's order book."""

    ticker: str
    yes_bids: List[OrderBookLevel] = field(default_factory=list)
    yes_asks: List[OrderBookLevel] = field(default_factory=list)

    @property
    def best_bid(self) -> Optional[int]:
        """Highest YES bid price, or None if the book is empty."""
        return max((lvl.price for lvl in self.yes_bids), default=None)

    @property
    def best_ask(self) -> Optional[int]:
        """Lowest YES ask price, or None if the book is empty."""
        return min((lvl.price for lvl in self.yes_asks), default=None)

    @property
    def spread(self) -> Optional[int]:
        """Bid-ask spread in cents, or None if either side is empty."""
        if self.best_bid is None or self.best_ask is None:
            return None
        return self.best_ask - self.best_bid


@dataclass
class Order:
    """A resting or filled order on Kalshi."""

    order_id: str
    ticker: str
    side: str  # "yes" | "no"
    action: str  # "buy" | "sell"
    price: int  # limit price in cents
    quantity: int  # number of contracts
    status: str  # "resting" | "filled" | "canceled"
    filled_quantity: int = 0


@dataclass
class Position:
    """Current holding in a single market."""

    ticker: str
    yes_quantity: int = 0
    no_quantity: int = 0
    total_cost: float = 0.0  # total amount spent (cents)

    @property
    def net_position(self) -> int:
        """Positive = net YES, negative = net NO."""
        return self.yes_quantity - self.no_quantity
