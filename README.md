# aRAYANK – Kalshi Trading Bot

A Python trading bot for [Kalshi](https://kalshi.com), the regulated prediction-markets exchange.  
The bot polls Kalshi markets, evaluates them against a configurable strategy, and places limit orders automatically.

---

## Features

| Component | Description |
|-----------|-------------|
| `kalshi_bot/auth.py` | RSA-PSS request signing (Kalshi v2 auth) |
| `kalshi_bot/client.py` | REST API client – markets, order book, orders, positions |
| `kalshi_bot/models.py` | Typed dataclasses: `Market`, `OrderBook`, `Order`, `Position` |
| `kalshi_bot/strategy.py` | Pluggable strategies: `MidPriceReversion`, `SpreadCapture`, `CompositeStrategy` |
| `kalshi_bot/bot.py` | Main loop with position limits, dry-run mode, and error recovery |
| `config.py` | Environment-variable configuration loader |
| `main.py` | Entry point |

---

## Quick Start

### 1 – Prerequisites

```
Python 3.10+
```

### 2 – Install dependencies

```bash
pip install -r requirements.txt
```

### 3 – Configure credentials

```bash
cp .env.example .env
# Edit .env and set KALSHI_API_KEY_ID and KALSHI_PRIVATE_KEY_PATH
```

Generate an API key from the [Kalshi dashboard](https://kalshi.com/profile/api).  
Download the RSA private key (PEM format) and store it somewhere safe.

### 4 – Run in dry-run mode (no real orders placed)

```bash
python main.py
```

### 5 – Run in live mode

```bash
KALSHI_DRY_RUN=false python main.py
```

---

## Configuration

All settings are read from environment variables (or a `.env` file).

| Variable | Default | Description |
|----------|---------|-------------|
| `KALSHI_API_KEY_ID` | *(required)* | API key ID from Kalshi dashboard |
| `KALSHI_PRIVATE_KEY_PATH` | *(required)* | Path to PEM RSA private key |
| `KALSHI_BASE_URL` | production URL | Override for the demo environment |
| `KALSHI_TICKERS` | all open markets | Comma-separated tickers to watch |
| `KALSHI_POLL_INTERVAL` | `30` | Seconds between evaluation cycles |
| `KALSHI_MAX_POSITION` | `10` | Max contracts per market |
| `KALSHI_DRY_RUN` | `true` | Log signals without placing orders |
| `KALSHI_LOG_LEVEL` | `INFO` | Python logging level |
| `KALSHI_STRATEGY` | `mid_reversion` | `mid_reversion` \| `spread_capture` \| `composite` |
| `KALSHI_LOW_THRESHOLD` | `35` | MidPriceReversion: buy YES below this (cents) |
| `KALSHI_HIGH_THRESHOLD` | `65` | MidPriceReversion: buy NO above this (cents) |
| `KALSHI_ORDER_QUANTITY` | `5` | Contracts per order |

---

## Strategies

### `mid_reversion` (default)
Buys YES when the mid-price is below `KALSHI_LOW_THRESHOLD` and buys NO when it is above `KALSHI_HIGH_THRESHOLD`.  
Simple mean-reversion suitable for markets that oscillate around 50 cents.

### `spread_capture`
Posts limit orders on the buy side of a wide spread, aiming to capture the bid-ask difference.

### `composite`
Runs `spread_capture` first, then falls back to `mid_reversion`.

---

## Running tests

```bash
pip install pytest
pytest tests/ -v
```

---

## Project Structure

```
.
├── kalshi_bot/
│   ├── __init__.py
│   ├── auth.py       # RSA-PSS authentication
│   ├── client.py     # Kalshi REST API client
│   ├── models.py     # Data models
│   ├── strategy.py   # Trading strategies
│   └── bot.py        # Main bot loop
├── tests/
│   ├── test_models.py
│   ├── test_strategy.py
│   └── test_bot.py
├── config.py         # Config loader
├── main.py           # Entry point
├── requirements.txt
├── .env.example
└── .gitignore
```

---

## Disclaimer

> **This software is provided for educational purposes only.**  
> Trading prediction markets involves financial risk.  
> Always start with `KALSHI_DRY_RUN=true` and review all signals before enabling live trading.  
> The authors are not responsible for any financial losses.