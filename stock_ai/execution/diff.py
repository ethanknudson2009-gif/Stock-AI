"""Pure order-diff: turn (current holdings, target tickers) into the orders to get there."""

from datetime import date

from stock_ai.execution.base import Order, make_client_order_id


def diff(
    current_positions: dict[str, float],
    target_tickers: list[str],
    trading_day: date,
    max_positions: int | None = None,
) -> list[Order]:
    """Return the buy/sell orders that move holdings from `current` to `target`.

    `current_positions` is {ticker: qty} (qty > 0 means held). `target_tickers` is
    the desired long/flat set, highest-priority first. If `max_positions` is set and
    the target is larger, only the first `max_positions` targets are kept (cap
    enforcement). Pure and deterministic: sells and buys are each emitted in sorted
    order, so the output depends only on the inputs.
    """
    if max_positions is not None:
        if max_positions < 0:
            raise ValueError("max_positions must be non-negative")
        target_tickers = target_tickers[:max_positions]

    target = set(target_tickers)
    held = {t for t, qty in current_positions.items() if qty > 0}

    sells = sorted(held - target)
    buys = sorted(target - held)

    orders = [Order(t, "sell", make_client_order_id(trading_day, t, "sell")) for t in sells]
    orders += [Order(t, "buy", make_client_order_id(trading_day, t, "buy")) for t in buys]
    return orders
