"""Execution layer: the Broker Protocol, a pure order-diff, and an in-memory FakeBroker.

No broker SDK is imported here. The real Alpaca adapter lands in `paper.py` (Phase F);
everything else stays SDK-free so bot logic is fully unit-testable.
"""

from stock_ai.execution.base import Broker, Order, make_client_order_id
from stock_ai.execution.diff import diff
from stock_ai.execution.fake import FakeBroker

__all__ = ["Broker", "Order", "make_client_order_id", "diff", "FakeBroker"]
