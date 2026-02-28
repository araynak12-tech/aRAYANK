"""HTTP client for the Kalshi Trade API v2.

Reference: https://trading-api.readme.io/reference

All monetary values are in *cents* (1 cent = $0.01).
"""

from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import requests

from .auth import KalshiAuth
from .models import Market, Order, OrderBook, OrderBookLevel, Position


class KalshiClientError(Exception):
    """Raised when the Kalshi API returns a non-2xx response."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(f"HTTP {status_code}: {detail}")
        self.status_code = status_code
        self.detail = detail


class KalshiClient:
    """Thin wrapper around the Kalshi REST API."""

    BASE_URL = "https://trading-api.kalshi.com/trade-api/v2"

    def __init__(self, auth: KalshiAuth, base_url: Optional[str] = None) -> None:
        self._auth = auth
        self._base_url = (base_url or self.BASE_URL).rstrip("/")
        self._session = requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})

    # ------------------------------------------------------------------
    # Account
    # ------------------------------------------------------------------

    def get_balance(self) -> int:
        """Return the available balance in cents."""
        data = self._get("/portfolio/balance")
        return data["balance"]

    def get_positions(self) -> List[Position]:
        """Return all current positions."""
        data = self._get("/portfolio/positions")
        positions = []
        for item in data.get("market_positions", []):
            positions.append(
                Position(
                    ticker=item["ticker"],
                    yes_quantity=item.get("position", 0),
                    no_quantity=0,  # Kalshi collapses yes/no into signed position
                    total_cost=item.get("total_traded", 0),
                )
            )
        return positions

    # ------------------------------------------------------------------
    # Markets
    # ------------------------------------------------------------------

    def get_markets(
        self,
        status: str = "open",
        limit: int = 100,
        cursor: Optional[str] = None,
    ) -> List[Market]:
        """Fetch a page of markets.

        Parameters
        ----------
        status:
            Filter by market status: ``"open"``, ``"closed"``, or ``"settled"``.
        limit:
            Number of results to return (max 200).
        cursor:
            Pagination cursor from a previous response.
        """
        params: Dict[str, Any] = {"status": status, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        data = self._get("/markets", params=params)
        return [self._parse_market(m) for m in data.get("markets", [])]

    def get_market(self, ticker: str) -> Market:
        """Fetch a single market by its ticker symbol."""
        data = self._get(f"/markets/{ticker}")
        return self._parse_market(data["market"])

    def get_orderbook(self, ticker: str, depth: int = 10) -> OrderBook:
        """Fetch the order book for a market."""
        data = self._get(f"/markets/{ticker}/orderbook", params={"depth": depth})
        book_data = data.get("orderbook", {})
        yes_bids = [
            OrderBookLevel(price=lvl[0], quantity=lvl[1])
            for lvl in book_data.get("yes", [])
        ]
        yes_asks = [
            OrderBookLevel(price=lvl[0], quantity=lvl[1])
            for lvl in book_data.get("no", [])  # API returns NO bids as YES asks (complementary side)
        ]
        return OrderBook(ticker=ticker, yes_bids=yes_bids, yes_asks=yes_asks)

    # ------------------------------------------------------------------
    # Orders
    # ------------------------------------------------------------------

    def place_order(
        self,
        ticker: str,
        side: str,
        action: str,
        price: int,
        quantity: int,
        order_type: str = "limit",
    ) -> Order:
        """Place a new order.

        Parameters
        ----------
        ticker:
            Market ticker symbol.
        side:
            ``"yes"`` or ``"no"``.
        action:
            ``"buy"`` or ``"sell"``.
        price:
            Limit price in cents (1-99).
        quantity:
            Number of contracts.
        order_type:
            ``"limit"`` (default) or ``"market"``.
        """
        payload = {
            "ticker": ticker,
            "side": side,
            "action": action,
            "type": order_type,
            "count": quantity,
            "yes_price": price if side == "yes" else (100 - price),
        }
        data = self._post("/portfolio/orders", json=payload)
        return self._parse_order(data["order"])

    def cancel_order(self, order_id: str) -> None:
        """Cancel a resting order."""
        self._delete(f"/portfolio/orders/{order_id}")

    def get_orders(self, ticker: Optional[str] = None, status: str = "resting") -> List[Order]:
        """Return orders, optionally filtered by ticker and status."""
        params: Dict[str, Any] = {"status": status}
        if ticker:
            params["ticker"] = ticker
        data = self._get("/portfolio/orders", params=params)
        return [self._parse_order(o) for o in data.get("orders", [])]

    # ------------------------------------------------------------------
    # Low-level HTTP helpers
    # ------------------------------------------------------------------

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict:
        full_path = path
        if params:
            full_path = f"{path}?{urlencode(params)}"
        headers = self._auth.build_headers("GET", f"/trade-api/v2{full_path}")
        resp = self._session.get(f"{self._base_url}{full_path}", headers=headers)
        return self._handle(resp)

    def _post(self, path: str, json: Optional[Dict] = None) -> Dict:
        headers = self._auth.build_headers("POST", f"/trade-api/v2{path}")
        resp = self._session.post(f"{self._base_url}{path}", json=json, headers=headers)
        return self._handle(resp)

    def _delete(self, path: str) -> Dict:
        headers = self._auth.build_headers("DELETE", f"/trade-api/v2{path}")
        resp = self._session.delete(f"{self._base_url}{path}", headers=headers)
        return self._handle(resp)

    @staticmethod
    def _handle(resp: requests.Response) -> Dict:
        if not resp.ok:
            raise KalshiClientError(resp.status_code, resp.text)
        return resp.json() if resp.content else {}

    # ------------------------------------------------------------------
    # Parsers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_market(data: Dict) -> Market:
        return Market(
            ticker=data["ticker"],
            title=data.get("title", ""),
            status=data.get("status", ""),
            yes_bid=data.get("yes_bid", 0),
            yes_ask=data.get("yes_ask", 100),
            no_bid=data.get("no_bid", 0),
            no_ask=data.get("no_ask", 100),
            volume=data.get("volume", 0),
            open_interest=data.get("open_interest", 0),
        )

    @staticmethod
    def _parse_order(data: Dict) -> Order:
        return Order(
            order_id=data["order_id"],
            ticker=data["ticker"],
            side=data["side"],
            action=data["action"],
            price=data.get("yes_price", 0),
            quantity=data.get("count", 0),
            status=data.get("status", ""),
            filled_quantity=data.get("filled_count", 0),
        )
