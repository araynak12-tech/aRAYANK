"""Tests for trading strategies."""

import pytest

from kalshi_bot.models import Market, OrderBook, OrderBookLevel
from kalshi_bot.strategy import (
    CompositeStrategy,
    MidPriceReversion,
    Signal,
    SpreadCapture,
    TradeSignal,
)


def _market(yes_bid=40, yes_ask=60, status="open"):
    return Market(
        ticker="TEST-1",
        title="Test Market",
        status=status,
        yes_bid=yes_bid,
        yes_ask=yes_ask,
        no_bid=100 - yes_ask,
        no_ask=100 - yes_bid,
        volume=500,
        open_interest=200,
    )


def _book(bid=48, ask=52):
    return OrderBook(
        ticker="TEST-1",
        yes_bids=[OrderBookLevel(bid, 10)],
        yes_asks=[OrderBookLevel(ask, 10)],
    )


class TestMidPriceReversion:
    def test_buy_yes_when_mid_low(self):
        strategy = MidPriceReversion(low_threshold=35, high_threshold=65)
        m = _market(yes_bid=20, yes_ask=30)  # mid = 25
        result = strategy.evaluate(m)
        assert result.signal == Signal.BUY_YES
        assert result.is_actionable

    def test_buy_no_when_mid_high(self):
        strategy = MidPriceReversion(low_threshold=35, high_threshold=65)
        m = _market(yes_bid=70, yes_ask=80)  # mid = 75
        result = strategy.evaluate(m)
        assert result.signal == Signal.BUY_NO
        assert result.is_actionable

    def test_hold_when_mid_in_band(self):
        strategy = MidPriceReversion(low_threshold=35, high_threshold=65)
        m = _market(yes_bid=45, yes_ask=55)  # mid = 50
        result = strategy.evaluate(m)
        assert result.signal == Signal.HOLD
        assert not result.is_actionable

    def test_suggested_price_is_yes_ask_for_buy_yes(self):
        strategy = MidPriceReversion(low_threshold=35)
        m = _market(yes_bid=20, yes_ask=30)
        result = strategy.evaluate(m)
        assert result.suggested_price == 30

    def test_order_quantity_passed_through(self):
        strategy = MidPriceReversion(low_threshold=35, order_quantity=7)
        m = _market(yes_bid=20, yes_ask=30)
        result = strategy.evaluate(m)
        assert result.suggested_quantity == 7


class TestSpreadCapture:
    def test_signal_when_spread_wide_enough(self):
        strategy = SpreadCapture(min_spread=3, edge=1)
        m = _market()
        book = _book(bid=45, ask=52)  # spread = 7
        result = strategy.evaluate(m, book)
        assert result.signal == Signal.BUY_YES
        assert result.suggested_price == 46  # best_bid + edge

    def test_hold_when_spread_too_narrow(self):
        strategy = SpreadCapture(min_spread=5)
        m = _market()
        book = _book(bid=49, ask=51)  # spread = 2
        result = strategy.evaluate(m, book)
        assert result.signal == Signal.HOLD

    def test_hold_when_no_book(self):
        strategy = SpreadCapture()
        result = strategy.evaluate(_market(), book=None)
        assert result.signal == Signal.HOLD

    def test_price_clamped_to_1_99(self):
        strategy = SpreadCapture(min_spread=1, edge=5)
        m = _market()
        book = _book(bid=97, ask=99)
        result = strategy.evaluate(m, book)
        assert 1 <= result.suggested_price <= 99


class TestCompositeStrategy:
    def test_returns_first_actionable(self):
        always_hold = MidPriceReversion(low_threshold=0, high_threshold=100)
        always_buy = MidPriceReversion(low_threshold=100, high_threshold=0)
        composite = CompositeStrategy([always_hold, always_buy])
        m = _market(yes_bid=45, yes_ask=55)
        result = composite.evaluate(m)
        # always_hold returns HOLD, always_buy triggers BUY_YES because mid > high_threshold=0
        assert result.is_actionable

    def test_hold_if_all_strategies_hold(self):
        always_hold = MidPriceReversion(low_threshold=0, high_threshold=100)
        composite = CompositeStrategy([always_hold])
        m = _market(yes_bid=45, yes_ask=55)
        result = composite.evaluate(m)
        assert result.signal == Signal.HOLD
