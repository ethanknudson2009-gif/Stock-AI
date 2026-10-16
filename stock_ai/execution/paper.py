"""Alpaca paper-trading adapter — the ONLY module that imports alpaca-py.

Conforms to the Broker Protocol. Hard-asserts the paper endpoint so a live
account can never be hit by accident (Pitfall #1), submits idempotent orders
via client_order_id (Pitfall #2), and pre-flights tradability before sending.
"""

from alpaca.common.exceptions import APIError
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest

from stock_ai.config import load_settings
from stock_ai.execution.base import Order

_PAPER_HOST = "paper-api.alpaca.markets"


class AlpacaPaperBroker:
    """Broker backed by Alpaca's paper sandbox. Refuses to run against the live API."""

    def __init__(self, client: TradingClient | None = None) -> None:
        """Build a paper TradingClient from .env keys, or use an injected one (tests).

        Asserts the client's base URL is the paper host — construction fails loudly
        otherwise, so this adapter can never be pointed at the live endpoint.
        """
        if client is None:
            settings = load_settings()
            if not (settings.alpaca_api_key and settings.alpaca_secret_key):
                raise ValueError(
                    "ALPACA_API_KEY and ALPACA_SECRET_KEY must be set in .env for paper trading"
                )
            client = TradingClient(
                api_key=settings.alpaca_api_key,
                secret_key=settings.alpaca_secret_key,
                paper=True,
            )
        base_url = str(getattr(client._base_url, "value", client._base_url))
        if _PAPER_HOST not in base_url:
            raise ValueError(
                f"Refusing to trade: client base URL {base_url!r} is not the paper endpoint"
            )
        self._client = client

    def get_account(self) -> dict:
        """Return a small account snapshot (cash, equity)."""
        acct = self._client.get_account()
        return {"cash": float(acct.cash), "equity": float(acct.equity)}

    def get_positions(self) -> dict[str, float]:
        """Return current holdings as {ticker: quantity}."""
        return {p.symbol: float(p.qty) for p in self._client.get_all_positions()}

    def get_position_details(self) -> list[dict]:
        """Open positions with cost basis and unrealized P&L (read-only)."""
        return [{"ticker": p.symbol, "qty": float(p.qty), "avg_entry": float(p.avg_entry_price),
                 "price": float(p.current_price), "value": float(p.market_value),
                 "pl": float(p.unrealized_pl), "pl_pct": float(p.unrealized_plpc)}
                for p in self._client.get_all_positions()]

    def get_account_summary(self) -> dict:
        """Equity, cash and today's change (read-only)."""
        a = self._client.get_account()
        equity, last = float(a.equity), float(a.last_equity)
        return {"equity": equity, "cash": float(a.cash), "buying_power": float(a.buying_power),
                "day_pl": equity - last, "day_pl_pct": (equity / last - 1) if last else 0.0}

    def get_order_history(self, limit: int = 100) -> list[dict]:
        """Newest-first orders of every status (read-only)."""
        from alpaca.trading.enums import QueryOrderStatus  # noqa: PLC0415
        from alpaca.trading.requests import GetOrdersRequest  # noqa: PLC0415

        orders = self._client.get_orders(GetOrdersRequest(status=QueryOrderStatus.ALL, limit=limit))
        f = lambda v: float(v) if v is not None else None  # noqa: E731
        return [{"ticker": o.symbol, "side": getattr(o.side, "value", str(o.side)),
                 "status": getattr(o.status, "value", str(o.status)), "notional": f(o.notional), "qty": f(o.qty),
                 "filled_qty": f(o.filled_qty) or 0.0, "avg_price": f(o.filled_avg_price),
                 "submitted_at": o.submitted_at, "filled_at": o.filled_at, "id": o.client_order_id}
                for o in orders]

    def get_equity_history(self, period: str = "1M") -> list[tuple]:
        """[(timestamp, equity)] from Alpaca's portfolio history, skipping days before funding (read-only)."""
        from alpaca.trading.requests import GetPortfolioHistoryRequest  # noqa: PLC0415

        h = self._client.get_portfolio_history(GetPortfolioHistoryRequest(period=period, timeframe="1D"))
        return [(t, e) for t, e in zip(h.timestamp, h.equity) if e]

    def submit_order(self, order: Order) -> Order:
        """Pre-flight tradability, then submit a market order. Idempotent via client_order_id."""
        asset = self._client.get_asset(order.ticker)
        if not getattr(asset, "tradable", False):
            raise ValueError(f"{order.ticker} is not tradable on Alpaca; skipping order")

        if order.notional is None and order.qty is None:
            raise ValueError("order must set notional or qty before live submission")

        # Alpaca requires exactly one of notional / qty. Prefer notional for buys
        # (dollar-sized entries); use share qty otherwise.
        use_notional = order.side == "buy" and order.notional is not None
        request = MarketOrderRequest(
            symbol=order.ticker,
            notional=order.notional if use_notional else None,
            qty=None if use_notional else order.qty,
            side=OrderSide.BUY if order.side == "buy" else OrderSide.SELL,
            time_in_force=TimeInForce.DAY,
            client_order_id=order.client_order_id,
        )
        try:
            self._client.submit_order(order_data=request)
        except APIError as exc:
            # Alpaca rejects a duplicate client_order_id (422). That means the order
            # already exists — treat as success so reruns/retries are idempotent.
            if "client_order_id" in str(exc).lower() or "duplicate" in str(exc).lower():
                return order
            raise
        return order

    def cancel_order(self, client_order_id: str) -> None:
        """Cancel an open order by its Alpaca order id (looked up from client_order_id)."""
        for o in self._client.get_orders():
            if getattr(o, "client_order_id", None) == client_order_id:
                self._client.cancel_order_by_id(o.id)
                return
