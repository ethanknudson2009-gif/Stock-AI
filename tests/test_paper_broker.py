"""Tests for the Alpaca paper adapter and the Eastern-time trading-day helper.

Uses a fake TradingClient — no network, no API keys. These prove the safety
contracts (paper-only endpoint, idempotency, pre-flight, timezone) offline;
live paper trading is a human checkpoint once real keys are in .env.
"""

from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from alpaca.common.exceptions import APIError

from stock_ai.execution import Broker, Order
from stock_ai.execution.clock import trading_day_today
from stock_ai.execution.paper import AlpacaPaperBroker

REPO_ROOT = Path(__file__).resolve().parent.parent


class FakeTradingClient:
    """Minimal stand-in for alpaca-py's TradingClient."""

    def __init__(self, base_url="https://paper-api.alpaca.markets", tradable=True):
        self._base_url = SimpleNamespace(value=base_url)
        self._tradable = tradable
        self.submitted = []
        self._seen_ids = set()

    def get_account(self):
        return SimpleNamespace(cash="1000.0", equity="1500.0")

    def get_all_positions(self):
        return [SimpleNamespace(symbol="AAPL", qty="3")]

    def get_asset(self, symbol):
        return SimpleNamespace(symbol=symbol, tradable=self._tradable, fractionable=True)

    def submit_order(self, order_data):
        coid = order_data.client_order_id
        if coid in self._seen_ids:
            raise APIError('{"message":"client_order_id must be unique"}')
        self._seen_ids.add(coid)
        self.submitted.append(order_data)
        return SimpleNamespace(id="srv-1", client_order_id=coid)


def _order(side="buy"):
    return Order("AAPL", side, "2026-10-13_AAPL_" + side, notional=100.0, qty=1.0)


def test_adapter_conforms_to_broker_protocol():
    assert isinstance(AlpacaPaperBroker(client=FakeTradingClient()), Broker)


def test_paper_endpoint_assertion():
    # Paper endpoint is accepted.
    AlpacaPaperBroker(client=FakeTradingClient(base_url="https://paper-api.alpaca.markets"))
    # Live endpoint is refused loudly.
    with pytest.raises(ValueError, match="paper endpoint"):
        AlpacaPaperBroker(client=FakeTradingClient(base_url="https://api.alpaca.markets"))


def test_idempotent_submission():
    client = FakeTradingClient()
    broker = AlpacaPaperBroker(client=client)
    order = _order("buy")
    broker.submit_order(order)
    broker.submit_order(order)  # duplicate client_order_id → caught, no second submit
    assert len(client.submitted) == 1


def test_preflight_rejects_non_tradable():
    broker = AlpacaPaperBroker(client=FakeTradingClient(tradable=False))
    with pytest.raises(ValueError, match="not tradable"):
        broker.submit_order(_order("buy"))


def test_submit_requires_size():
    broker = AlpacaPaperBroker(client=FakeTradingClient())
    with pytest.raises(ValueError, match="notional or qty"):
        broker.submit_order(Order("AAPL", "buy", "cid-x"))


def test_get_positions_and_account():
    broker = AlpacaPaperBroker(client=FakeTradingClient())
    assert broker.get_positions() == {"AAPL": 3.0}
    assert broker.get_account() == {"cash": 1000.0, "equity": 1500.0}


def test_trading_day_timezone():
    # 11:59pm Pacific on 2026-03-01 is already 2026-03-02 in New York.
    pt = datetime(2026, 3, 1, 23, 59, tzinfo=ZoneInfo("America/Los_Angeles"))
    assert trading_day_today(pt) == date(2026, 3, 2)
    # And an Eastern afternoon stays on its own date.
    et = datetime(2026, 3, 1, 15, 0, tzinfo=ZoneInfo("America/New_York"))
    assert trading_day_today(et) == date(2026, 3, 1)


def test_paper_is_sole_alpaca_trading_importer():
    """Only paper.py may touch alpaca-py's trading side; data/news.py may use the read-only data client."""
    allowed = {"paper.py": None, "news.py": "alpaca.data"}
    offenders = []
    for p in (REPO_ROOT / "stock_ai").rglob("*.py"):
        text = p.read_text()
        if "import alpaca" not in text and "from alpaca" not in text:
            continue
        if p.name not in allowed:
            offenders.append(p.relative_to(REPO_ROOT).as_posix())
        elif allowed[p.name] and "alpaca.trading" in text:
            offenders.append(f"{p.name} (imports alpaca.trading)")
    assert offenders == [], f"alpaca-py imported outside its allowed place: {offenders}"
