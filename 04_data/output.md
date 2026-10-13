# 04 · Data — Output

## Source
yfinance daily OHLCV, auto-adjusted. Universe: `DEFAULT_UNIVERSE` (30 large-cap US).
Cadence: EOD. No persistence — every run recomputes from the API.

## Features (`FEATURE_COLUMNS`)
`return_1d`, `sma_10`, `sma_50`, `rsi_14`. Rows with NaN (warm-up) dropped.

## Label
`label = 1 if next-day Close > today Close else 0` (next-day direction).

## Split (no leakage)
Chronological `train_test_split(shuffle=False)`, 80/20. Test slice is strictly after
train. Positions shifted 1 day in the backtester so a signal can't trade its own bar.

## Multi-ticker integrity
Canonical trading-day calendar = union of all tickers' dates; each ticker reindexed,
≤2-session gaps forward-filled, longer gaps left NaN (no fabricated prices). Portfolio
return built as ONE combined series.

## Survivorship bias
Universe is a current snapshot → historical backtests are survivorship-biased by
construction. Bounded via short default windows + loud UI/README/docstring disclosure.
Point-in-time membership feed is a v2 item.
