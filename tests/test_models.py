"""Tests for data models."""

import pytest

from kalshi_bot.models import Market, Order, OrderBook, OrderBookLevel, Position


class TestMarket:
    def _make(self, yes_bid=40, yes_ask=60, no_bid=38, no_ask=62):
        return Market(
            ticker="TEST-1",
            title="Test Market",
            status="open",
            yes_bid=yes_bid,
            yes_ask=yes_ask,
            no_bid=no_bid,
            no_ask=no_ask,
            volume=100,
            open_interest=50,
        )

    def test_mid_price(self):
        m = self._make(yes_bid=40, yes_ask=60)
        assert m.mid_price == 50.0

    def test_mid_price_asymmetric(self):
        m = self._make(yes_bid=30, yes_ask=50)
        assert m.mid_price == 40.0


class TestOrderBook:
    def _book(self):
        return OrderBook(
            ticker="TEST-1",
            yes_bids=[OrderBookLevel(48, 10), OrderBookLevel(47, 5)],
            yes_asks=[OrderBookLevel(52, 8), OrderBookLevel(53, 3)],
        )

    def test_best_bid(self):
        assert self._book().best_bid == 48

    def test_best_ask(self):
        assert self._book().best_ask == 52

    def test_spread(self):
        assert self._book().spread == 4

    def test_empty_book(self):
        empty = OrderBook(ticker="TEST-1")
        assert empty.best_bid is None
        assert empty.best_ask is None
        assert empty.spread is None


class TestPosition:
    def test_net_position_yes(self):
        p = Position(ticker="T", yes_quantity=10, no_quantity=3)
        assert p.net_position == 7

    def test_net_position_no(self):
        p = Position(ticker="T", yes_quantity=2, no_quantity=8)
        assert p.net_position == -6
