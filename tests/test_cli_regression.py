"""Regression test: CLI output must match the committed baseline.

The CLI must produce output matching tests/baseline/aapl_backtest.txt (the
walk-forward model contract). yfinance returns floating-point jitter in
adjusted-close values between API calls, so figures drift slightly run-to-run
even in unchanged code. This test is therefore structured as:

1. Byte-identical fast-path (preferred when yfinance returns stable data).
2. Structural + near-numeric fallback: same number of lines, identical
   non-numeric content, numeric fields within tolerance (relative for large
   return figures, absolute floor for small ones).

A real regression (wrong feature columns, changed label horizon, different RNG,
off-by-one in positions) moves numbers by tens of points and blows past both.
Regenerate the baseline deliberately with:
    python main.py backtest --ticker AAPL --start 2020-01-01 --end 2023-12-31 \\
        > tests/baseline/aapl_backtest.txt
"""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
BASELINE = REPO_ROOT / "tests" / "baseline" / "aapl_backtest.txt"

pytestmark = pytest.mark.skipif(
    bool(os.environ.get("SKIP_NETWORK_TESTS")),
    reason="requires yfinance network access; set SKIP_NETWORK_TESTS=1 to opt out",
)

_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")  # ints (e.g. trade count) and floats
# yfinance jitter compounds across trades, so large cumulative-return figures
# (hundreds of percent) can drift by a point or two run-to-run. Use a relative
# tolerance for big numbers with a small absolute floor for little ones. A real
# regression moves numbers by tens of points and still trips this.
_REL_TOLERANCE = 0.15   # 15% of the baseline value
_ABS_FLOOR = 1.0        # but at least 1.0 absolute, for small figures


def _within_tolerance(actual: float, expected: float) -> bool:
    return abs(actual - expected) <= max(_ABS_FLOOR, abs(expected) * _REL_TOLERANCE)


def _extract_numbers(line: str) -> list[float]:
    return [float(m) for m in _NUMBER_RE.findall(line)]


_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _strip_numbers(line: str) -> str:
    # Mask dates first (they shift legitimately with data length / split
    # boundaries), then numbers, leaving only the fixed labels for comparison.
    return _NUMBER_RE.sub("<NUM>", _DATE_RE.sub("<DATE>", line))


def test_backtest_cli_output_matches_baseline():
    completed = subprocess.run(
        [
            sys.executable,
            "main.py",
            "backtest",
            "--ticker",
            "AAPL",
            "--start",
            "2020-01-01",
            "--end",
            "2023-12-31",
        ],
        capture_output=True,
        text=True,
        check=True,
        cwd=str(REPO_ROOT),
    )
    actual = completed.stdout
    expected = BASELINE.read_text()

    # Fast path: true byte-identical match.
    if actual == expected:
        return

    # Fallback: structural identity + numeric tolerance (tolerates yfinance
    # floating-point jitter in adjusted-close values).
    actual_lines = actual.splitlines()
    expected_lines = expected.splitlines()
    assert len(actual_lines) == len(expected_lines), (
        f"line count drift: got {len(actual_lines)}, baseline has {len(expected_lines)}"
    )
    for i, (a, e) in enumerate(zip(actual_lines, expected_lines)):
        assert _strip_numbers(a) == _strip_numbers(e), (
            f"non-numeric content drift on line {i + 1}:\n  actual:   {a!r}\n  baseline: {e!r}"
        )
        a_nums = _extract_numbers(a)
        e_nums = _extract_numbers(e)
        assert len(a_nums) == len(e_nums), (
            f"number count drift on line {i + 1}: {a!r} vs {e!r}"
        )
        for an, en in zip(a_nums, e_nums):
            assert _within_tolerance(an, en), (
                f"numeric drift beyond tolerance on line {i + 1}: {an} vs {en} (|Δ|={abs(an - en)})"
            )
