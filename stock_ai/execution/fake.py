"""In-memory FakeBroker: deterministic, idempotent, and DRY_RUN-aware. No SDK, no network."""

import os

from stock_ai.execution.base import Order


def _dry_run_default() -> bool:
    """Read DRY_RUN from the environment. Truthy values: 1, true, yes, on (any case)."""
    return os.getenv("DRY_RUN", "").strip().lower() in {"1", "true", "yes", "on"}


class FakeBroker:
    """A test-double broker that records submissions in memory instead of hitting an API.

    Deterministic and side-effect-free beyond its own state, so bot logic can be unit
    tested. Duplicate `client_order_id`s collapse to a single submission (Pitfall #2).
    When `dry_run` is true, `submit_order` logs a no-op and changes no state.
    """

    def __init__(self, cash: float = 100_000.0, dry_run: bool | None = None) -> None:
        self._cash = cash
        self._positions: dict[str, float] = {}
        self.submissions: list[Order] = []
        self.dry_run_log: list[Order] = []
        self._seen_ids: set[str] = set()
        self.dry_run = _dry_run_default() if dry_run is None else dry_run

    def get_account(self) -> dict:
        """Return a simple account snapshot."""
        return {"cash": self._cash, "equity": self._cash}

    def get_positions(self) -> dict[str, float]:
        """Return a copy of current holdings as {ticker: quantity}."""
        return dict(self._positions)

    def submit_order(self, order: Order) -> Order:
        """Record `order` and apply it to positions. Idempotent; a no-op under dry_run."""
        if self.dry_run:
            self.dry_run_log.append(order)
            return order

        if order.client_order_id in self._seen_ids:
            return order  # already submitted — do not double-apply (idempotent)

        self._seen_ids.add(order.client_order_id)
        self.submissions.append(order)
        if order.side == "buy":
            self._positions[order.ticker] = 1.0
        elif order.side == "sell":
            self._positions.pop(order.ticker, None)
        return order

    def cancel_order(self, client_order_id: str) -> None:
        """Drop a submission by its client order id (no-op if unknown)."""
        self._seen_ids.discard(client_order_id)
        self.submissions = [o for o in self.submissions if o.client_order_id != client_order_id]
