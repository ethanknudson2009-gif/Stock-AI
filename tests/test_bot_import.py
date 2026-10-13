"""Pitfall #20 / BL-07 guard: importing bot must make ZERO network calls.

Run with sockets disabled; if `import bot` tried to reach the network (or
submit an order on import), the socket ban would raise here.
"""

import pytest

pytest_socket = pytest.importorskip("pytest_socket")


@pytest.fixture(autouse=True)
def _no_sockets():
    pytest_socket.disable_socket()
    yield
    pytest_socket.enable_socket()


def test_bot_import_no_network():
    import bot  # noqa: F401 — the import itself is the assertion

    # And the module exposes the scheduled entry point without having run it.
    assert hasattr(bot, "run_eod")
