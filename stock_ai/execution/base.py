"""The Broker Protocol and the Order value object shared by every broker implementation."""

from dataclasses import dataclass
from datetime import date
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class Order:
    """A single intended trade. `client_order_id` makes submission idempotent.

    `notional` (dollar amount) sizes a buy; `qty` (share count) sizes either side.
    Both default to None — the FakeBroker and order-diff ignore them; the live
    Alpaca adapter requires one to be set before it will submit.
    """

    ticker: str
    side: str  # "buy" or "sell"
    client_order_id: str
    notional: float | None = None
    qty: float | None = None


def make_client_order_id(day: date, ticker: str, side: str) -> str:
    """Deterministic id keyed on the trading day, ticker, and side.

    The same (day, ticker, side) always yields the same id, so re-running the bot
    or a Streamlit rerun can't create a duplicate order (Pitfall #2). `day` should
    be the US/Eastern trading date (Pitfall #7), decided by the caller.
    """
    return f"{day:%Y-%m-%d}_{ticker}_{side}"


@runtime_checkable
class Broker(Protocol):
    """What every broker (FakeBroker, future AlpacaPaperBroker) must provide."""

    def get_account(self) -> dict:
        """Return account snapshot (e.g. {'cash': float, 'equity': float})."""
        ...

    def get_positions(self) -> dict[str, float]:
        """Return current holdings as {ticker: quantity}."""
        ...

    def submit_order(self, order: Order) -> Order:
        """Submit `order`; idempotent on `client_order_id`. Returns the recorded order."""
        ...

    def cancel_order(self, client_order_id: str) -> None:
        """Cancel a previously submitted order by its client order id."""
        ...
