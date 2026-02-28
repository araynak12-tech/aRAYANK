"""Main bot orchestration loop."""

import logging
import time
from typing import List, Optional

from .client import KalshiClient, KalshiClientError
from .models import Market
from .strategy import BaseStrategy, Signal

logger = logging.getLogger(__name__)


class KalshiBot:
    """Polls Kalshi markets and executes trades based on a strategy.

    Parameters
    ----------
    client:
        Authenticated :class:`~kalshi_bot.client.KalshiClient` instance.
    strategy:
        A :class:`~kalshi_bot.strategy.BaseStrategy` that returns trade signals.
    tickers:
        List of market tickers to monitor.  If *None* the bot fetches all open
        markets on every cycle (can be slow for large accounts).
    poll_interval:
        Seconds between each evaluation cycle.
    max_position:
        Maximum number of contracts held per market (across YES and NO).
    dry_run:
        When *True* the bot logs what it would do but never places real orders.
    """

    def __init__(
        self,
        client: KalshiClient,
        strategy: BaseStrategy,
        tickers: Optional[List[str]] = None,
        poll_interval: float = 30.0,
        max_position: int = 10,
        dry_run: bool = True,
    ) -> None:
        self._client = client
        self._strategy = strategy
        self._tickers = tickers or []
        self._poll_interval = poll_interval
        self._max_position = max_position
        self._dry_run = dry_run

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(self, cycles: Optional[int] = None) -> None:
        """Start the bot loop.

        Parameters
        ----------
        cycles:
            If given, stop after this many evaluation cycles (useful for
            testing).  If *None* the loop runs indefinitely.
        """
        mode = "DRY-RUN" if self._dry_run else "LIVE"
        logger.info("KalshiBot starting (%s mode)", mode)

        cycle = 0
        while cycles is None or cycle < cycles:
            try:
                self._run_cycle()
            except KalshiClientError as exc:
                logger.error("API error during cycle %d: %s", cycle, exc)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Unexpected error during cycle %d: %s", cycle, exc)

            cycle += 1
            if cycles is None or cycle < cycles:
                logger.debug("Sleeping %.1f s…", self._poll_interval)
                time.sleep(self._poll_interval)

        logger.info("KalshiBot finished after %d cycle(s).", cycle)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _run_cycle(self) -> None:
        markets = self._fetch_markets()
        logger.info("Evaluating %d market(s)…", len(markets))

        for market in markets:
            if market.status != "open":
                continue
            try:
                self._evaluate_market(market)
            except KalshiClientError as exc:
                logger.warning("Skipping %s: %s", market.ticker, exc)

    def _fetch_markets(self) -> List[Market]:
        if self._tickers:
            markets = []
            for ticker in self._tickers:
                try:
                    markets.append(self._client.get_market(ticker))
                except KalshiClientError as exc:
                    logger.warning("Could not fetch market %s: %s", ticker, exc)
            return markets
        return self._client.get_markets(status="open")

    def _evaluate_market(self, market: Market) -> None:
        book = None
        try:
            book = self._client.get_orderbook(market.ticker)
        except KalshiClientError:
            logger.debug("Could not fetch order book for %s", market.ticker)

        signal = self._strategy.evaluate(market, book)

        if not signal.is_actionable:
            logger.debug("%s → HOLD (%s)", market.ticker, signal.reason)
            return

        # Check current position against the maximum allowed.
        # For BUY_YES: position must be below +max_position.
        # For BUY_NO: position must be above -max_position.
        position = self._get_position(market.ticker)
        buying_yes = signal.signal == Signal.BUY_YES
        if buying_yes and position >= self._max_position:
            logger.info(
                "%s → %s skipped: position %d >= max %d",
                market.ticker,
                signal.signal.value,
                position,
                self._max_position,
            )
            return
        if not buying_yes and position <= -self._max_position:
            logger.info(
                "%s → %s skipped: position %d <= -%d",
                market.ticker,
                signal.signal.value,
                position,
                self._max_position,
            )
            return

        side = "yes" if buying_yes else "no"
        price = signal.suggested_price
        if buying_yes:
            available = self._max_position - position
        else:
            available = self._max_position + position
        qty = min(signal.suggested_quantity, available)

        if self._dry_run:
            logger.info(
                "[DRY-RUN] %s → BUY %s @ %d¢ × %d  (%s)",
                market.ticker,
                side.upper(),
                price,
                qty,
                signal.reason,
            )
            return

        order = self._client.place_order(
            ticker=market.ticker,
            side=side,
            action="buy",
            price=price,
            quantity=qty,
        )
        logger.info(
            "Placed order %s: BUY %s @ %d¢ × %d on %s",
            order.order_id,
            side.upper(),
            price,
            qty,
            market.ticker,
        )

    def _get_position(self, ticker: str) -> int:
        """Return the signed net position for *ticker* (positive = YES)."""
        try:
            positions = self._client.get_positions()
            for pos in positions:
                if pos.ticker == ticker:
                    return pos.net_position
        except KalshiClientError as exc:
            logger.warning("Could not fetch positions: %s", exc)
        return 0
