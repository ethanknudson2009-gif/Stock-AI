"""CLI entry point: fetch data, train a model, and backtest a ticker."""

import argparse
from datetime import date

from stock_ai.backtest.engine import run_backtest
from stock_ai.data.loader import fetch_price_history
from stock_ai.features.indicators import add_features
from stock_ai.models.classifier import train_model
from stock_ai.strategy.signal import generate_signals


def cmd_fetch(args):
    df = fetch_price_history(args.ticker, args.start, args.end)
    print(df.tail())


def cmd_train(args):
    df = fetch_price_history(args.ticker, args.start, args.end)
    df = add_features(df)
    model, accuracy, _train_df, _test_df = train_model(df)
    print(f"Test accuracy for {args.ticker}: {accuracy:.2%}")


def _print_results(label: str, df, results) -> None:
    start, end = df.index[0].date(), df.index[-1].date()
    print(f"{label} ({start} → {end}):")
    print(f"  Strategy return: {results['total_return']:.2%}")
    print(f"  Buy & hold:      {results['buy_hold_return']:.2%}")
    print(f"  Sharpe ratio:    {results['sharpe_ratio']:.2f}")
    print(f"  Trades:          {results['n_trades']} @ {results['cost_bps']:.1f} bps")


def cmd_backtest(args):
    df = fetch_price_history(args.ticker, args.start, args.end)
    df = add_features(df)
    model, accuracy, train_df, test_df = train_model(df)

    oos_positions = generate_signals(model, test_df, threshold=args.threshold)
    oos_results = run_backtest(test_df, oos_positions, cost_bps=args.cost_bps)

    is_positions = generate_signals(model, train_df, threshold=args.threshold)
    is_results = run_backtest(train_df, is_positions, cost_bps=args.cost_bps)

    print(f"Test accuracy: {accuracy:.2%}  (threshold: {args.threshold:.2f})\n")
    _print_results("Out-of-sample (honest)", test_df, oos_results)
    print()
    _print_results("In-sample (training data — overfitting-prone)", train_df, is_results)


def main():
    parser = argparse.ArgumentParser(description="AI stock trading toolkit")
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--ticker", required=True, help="Stock ticker, e.g. AAPL")
    common.add_argument("--start", default="2015-01-01", help="Start date YYYY-MM-DD")
    common.add_argument("--end", default=str(date.today()), help="End date YYYY-MM-DD")

    fetch_p = sub.add_parser("fetch", parents=[common], help="Fetch price history")
    fetch_p.set_defaults(func=cmd_fetch)

    train_p = sub.add_parser("train", parents=[common], help="Train the classifier")
    train_p.set_defaults(func=cmd_train)

    backtest_p = sub.add_parser("backtest", parents=[common], help="Backtest the strategy")
    backtest_p.add_argument(
        "--cost-bps",
        type=float,
        default=10.0,
        help="Per-trade cost in basis points (10 bps = 0.1%%). Default 10.",
    )
    backtest_p.add_argument(
        "--threshold",
        type=float,
        default=0.5,
        help="Min predicted probability to go long (default 0.5 = argmax; "
        "try 0.55-0.60 for high-conviction only).",
    )
    backtest_p.set_defaults(func=cmd_backtest)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
