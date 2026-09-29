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
    model, accuracy = train_model(df)
    print(f"Test accuracy for {args.ticker}: {accuracy:.2%}")


def cmd_backtest(args):
    df = fetch_price_history(args.ticker, args.start, args.end)
    df = add_features(df)
    model, accuracy = train_model(df)
    positions = generate_signals(model, df)
    results = run_backtest(df, positions)

    print(f"Test accuracy: {accuracy:.2%}")
    print(f"Strategy return: {results['total_return']:.2%}")
    print(f"Buy & hold return: {results['buy_hold_return']:.2%}")
    print(f"Sharpe ratio: {results['sharpe_ratio']:.2f}")


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
    backtest_p.set_defaults(func=cmd_backtest)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
