"""Tests for the KalshiBot orchestration loop."""

from unittest.mock import MagicMock, patch

import pytest

from kalshi_bot.bot import KalshiBot
from kalshi_bot.client import KalshiClientError
from kalshi_bot.models import Market, Order, Position
from kalshi_bot.strategy import MidPriceReversion, Signal, TradeSignal


def _open_market(ticker="TEST-1", yes_bid=20, yes_ask=30):
    return Market(
        ticker=ticker,
        title="Test",
        status="open",
        yes_bid=yes_bid,
        yes_ask=yes_ask,
        no_bid=70,
        no_ask=80,
        volume=100,
        open_interest=50,
    )


def _make_bot(dry_run=True, tickers=None, max_position=10):
    client = MagicMock()
    client.get_markets.return_value = []
    client.get_positions.return_value = []
    strategy = MidPriceReversion(low_threshold=35, high_threshold=65)
    return KalshiBot(
        client=client,
        strategy=strategy,
        tickers=tickers or [],
        poll_interval=0,
        max_position=max_position,
        dry_run=dry_run,
    ), client


class TestKalshiBotDryRun:
    def test_no_order_placed_in_dry_run(self):
        bot, client = _make_bot(dry_run=True)
        client.get_markets.return_value = [_open_market()]
        client.get_positions.return_value = []
        client.get_orderbook.side_effect = KalshiClientError(404, "not found")
        bot.run(cycles=1)
        client.place_order.assert_not_called()

    def test_order_placed_in_live_mode(self):
        bot, client = _make_bot(dry_run=False)
        market = _open_market(yes_bid=20, yes_ask=30)  # mid=25 < threshold 35
        client.get_markets.return_value = [market]
        client.get_positions.return_value = []
        client.get_orderbook.side_effect = KalshiClientError(404, "not found")
        client.place_order.return_value = Order(
            order_id="ord-1",
            ticker="TEST-1",
            side="yes",
            action="buy",
            price=30,
            quantity=5,
            status="resting",
        )
        bot.run(cycles=1)
        client.place_order.assert_called_once()

    def test_position_limit_prevents_order(self):
        bot, client = _make_bot(dry_run=False, max_position=5)
        market = _open_market(yes_bid=20, yes_ask=30)
        client.get_markets.return_value = [market]
        # Already at max YES position
        client.get_positions.return_value = [Position(ticker="TEST-1", yes_quantity=5)]
        client.get_orderbook.side_effect = KalshiClientError(404, "not found")
        bot.run(cycles=1)
        client.place_order.assert_not_called()

    def test_no_position_limit_prevents_buy_no(self):
        """Bot should not buy NO when already at the max NO position."""
        # Use a market that triggers BUY_NO (mid_price > 65)
        bot, client = _make_bot(dry_run=False, max_position=5)
        market = _open_market(yes_bid=70, yes_ask=80)  # mid=75 > high_threshold=65
        client.get_markets.return_value = [market]
        # Already at max NO position (net = -5)
        client.get_positions.return_value = [Position(ticker="TEST-1", yes_quantity=0, no_quantity=5)]
        client.get_orderbook.side_effect = KalshiClientError(404, "not found")
        bot.run(cycles=1)
        client.place_order.assert_not_called()

    def test_skips_closed_markets(self):
        bot, client = _make_bot(dry_run=False)
        closed = Market(
            ticker="CLOSED-1",
            title="Closed",
            status="closed",
            yes_bid=20,
            yes_ask=30,
            no_bid=70,
            no_ask=80,
            volume=0,
            open_interest=0,
        )
        client.get_markets.return_value = [closed]
        bot.run(cycles=1)
        client.place_order.assert_not_called()

    def test_api_error_does_not_crash_loop(self):
        bot, client = _make_bot(dry_run=False)
        client.get_markets.side_effect = KalshiClientError(500, "server error")
        # Should not raise
        bot.run(cycles=1)

    def test_uses_specified_tickers(self):
        bot, client = _make_bot(dry_run=True, tickers=["TICK-A", "TICK-B"])
        client.get_market.return_value = _open_market()
        client.get_positions.return_value = []
        client.get_orderbook.side_effect = KalshiClientError(404, "not found")
        bot.run(cycles=1)
        assert client.get_market.call_count == 2
        client.get_markets.assert_not_called()
