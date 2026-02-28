#!/usr/bin/env python3
"""Entry point for the Kalshi trading bot.

Usage
-----
    python main.py

Environment variables (see config.py for full list):
    KALSHI_API_KEY_ID        – your Kalshi key ID
    KALSHI_PRIVATE_KEY_PATH  – path to your RSA private key (.pem)
    KALSHI_DRY_RUN           – set to "false" to trade with real money
    KALSHI_TICKERS           – comma-separated tickers to watch (optional)
"""

import logging

from config import configure_logging, load_config
from kalshi_bot.auth import KalshiAuth
from kalshi_bot.bot import KalshiBot
from kalshi_bot.client import KalshiClient
from kalshi_bot.strategy import CompositeStrategy, MidPriceReversion, SpreadCapture

logger = logging.getLogger(__name__)


def build_strategy(cfg: dict):
    name = cfg["strategy"]
    qty = cfg["order_quantity"]

    if name == "spread_capture":
        return SpreadCapture(order_quantity=qty)

    if name == "composite":
        return CompositeStrategy(
            [
                SpreadCapture(order_quantity=qty),
                MidPriceReversion(
                    low_threshold=cfg["low_threshold"],
                    high_threshold=cfg["high_threshold"],
                    order_quantity=qty,
                ),
            ]
        )

    # Default: mid_reversion
    return MidPriceReversion(
        low_threshold=cfg["low_threshold"],
        high_threshold=cfg["high_threshold"],
        order_quantity=qty,
    )


def main() -> None:
    configure_logging()

    try:
        cfg = load_config()
    except EnvironmentError as exc:
        logger.error("Configuration error: %s", exc)
        raise SystemExit(1) from exc

    auth = KalshiAuth(
        api_key_id=cfg["api_key_id"],
        private_key_pem=cfg["private_key_pem"],
    )

    client_kwargs = {}
    if cfg.get("base_url"):
        client_kwargs["base_url"] = cfg["base_url"]

    client = KalshiClient(auth, **client_kwargs)
    strategy = build_strategy(cfg)

    bot = KalshiBot(
        client=client,
        strategy=strategy,
        tickers=cfg["tickers"],
        poll_interval=cfg["poll_interval"],
        max_position=cfg["max_position"],
        dry_run=cfg["dry_run"],
    )

    bot.run()


if __name__ == "__main__":
    main()
