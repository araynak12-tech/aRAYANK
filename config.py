"""Configuration loader.

Settings are read from environment variables (or a ``.env`` file if
``python-dotenv`` is installed).

Required variables
------------------
KALSHI_API_KEY_ID
    The key ID shown in the Kalshi dashboard.
KALSHI_PRIVATE_KEY_PATH
    Path to the PEM-encoded RSA private key file.

Optional variables
------------------
KALSHI_BASE_URL          – override the API base URL (useful for the demo env)
KALSHI_TICKERS           – comma-separated list of market tickers to monitor
KALSHI_POLL_INTERVAL     – seconds between cycles (default: 30)
KALSHI_MAX_POSITION      – max contracts per market (default: 10)
KALSHI_DRY_RUN           – "true"/"false" (default: "true")
KALSHI_LOG_LEVEL         – Python log level (default: "INFO")
KALSHI_STRATEGY          – "mid_reversion" | "spread_capture" (default: "mid_reversion")
KALSHI_LOW_THRESHOLD     – MidPriceReversion low threshold in cents (default: 35)
KALSHI_HIGH_THRESHOLD    – MidPriceReversion high threshold in cents (default: 65)
KALSHI_ORDER_QUANTITY    – contracts per order (default: 5)
"""

import logging
import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass  # python-dotenv is optional


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise EnvironmentError(
            f"Required environment variable '{name}' is not set. "
            "Please copy .env.example to .env and fill in your credentials."
        )
    return value


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).lower() in ("1", "true", "yes")


def _int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def _float(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


def configure_logging() -> None:
    level = os.getenv("KALSHI_LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=level,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def load_config() -> dict:
    """Return a configuration dictionary populated from environment variables."""
    api_key_id = _require("KALSHI_API_KEY_ID")
    key_path = _require("KALSHI_PRIVATE_KEY_PATH")

    with open(key_path, "r") as fh:
        private_key_pem = fh.read()

    tickers_raw = os.getenv("KALSHI_TICKERS", "")
    tickers = [t.strip() for t in tickers_raw.split(",") if t.strip()]

    return {
        "api_key_id": api_key_id,
        "private_key_pem": private_key_pem,
        "base_url": os.getenv("KALSHI_BASE_URL"),
        "tickers": tickers,
        "poll_interval": _float("KALSHI_POLL_INTERVAL", 30.0),
        "max_position": _int("KALSHI_MAX_POSITION", 10),
        "dry_run": _bool("KALSHI_DRY_RUN", True),
        "strategy": os.getenv("KALSHI_STRATEGY", "mid_reversion"),
        "low_threshold": _int("KALSHI_LOW_THRESHOLD", 35),
        "high_threshold": _int("KALSHI_HIGH_THRESHOLD", 65),
        "order_quantity": _int("KALSHI_ORDER_QUANTITY", 5),
    }
