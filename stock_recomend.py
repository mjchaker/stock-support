"""Command-line entry point: score, rank and size TSX stocks.

Examples::

    python stock_recomend.py                      # score the built-in watchlist
    python stock_recomend.py CEU.TO CCO.TO SHOP   # score specific symbols
    python stock_recomend.py --all --top 25       # scan the whole TSX list
    python stock_recomend.py --all --capital 10000 --excel
    python stock_recomend.py --detail CEU.TO      # full explanation for one stock
"""

import argparse
import sys

import recommender
from support_handler import stock_handler


def get_all_data():
    Stock_Data = stock_handler()
    stock_list = Stock_Data.get_all_stock_symbols()
    return stock_list


def get_currentstock():
    return list(recommender.DEFAULT_WATCHLIST)


def _progress(done, total, symbol):
    if total >= 20:
        sys.stderr.write(f"\r  fetched {done}/{total}  ({symbol:<12})")
        sys.stderr.flush()
        if done == total:
            sys.stderr.write("\n")


def build_parser():
    p = argparse.ArgumentParser(description="Score and rank TSX stocks with a transparent factor model.")
    p.add_argument("symbols", nargs="*", help="symbols to score (default: built-in watchlist)")
    p.add_argument("--all", action="store_true", help="scan every symbol in the TSX interlisted list")
    p.add_argument("--top", type=int, default=None, help="only print the top N rows")
    p.add_argument("--detail", action="store_true", help="print the full explanation for each stock")
    p.add_argument("--capital", type=float, default=None, help="suggest position sizes for this much cash")
    p.add_argument("--excel", nargs="?", const="tsx_recommendations.xlsx", default=None,
                   metavar="FILE", help="export the ranking to an Excel file")
    p.add_argument("--workers", type=int, default=8, help="parallel fetches (default 8)")
    p.add_argument("--cache", default=".stock_cache.json", help="JSON cache for fetched data ('' to disable)")
    p.add_argument("--min-score", type=float, default=None, help="hide rows below this composite score")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    handler = stock_handler()

    if args.all:
        print("Downloading TSX symbol list...", file=sys.stderr)
        symbols = handler.get_all_stock_symbols()
    elif args.symbols:
        symbols = args.symbols
    else:
        symbols = get_currentstock()

    ranked = handler.recommend(
        symbols,
        workers=args.workers,
        cache_path=args.cache or None,
        progress=_progress,
    )

    if args.min_score is not None:
        ranked = [s for s in ranked if s.composite is not None and s.composite >= args.min_score]

    print()
    print(recommender.format_table(ranked, limit=args.top))

    if args.detail:
        print()
        for s in ranked[: args.top] if args.top else ranked:
            print(recommender.format_detail(s))
            print()

    if args.capital:
        print()
        print(f"Suggested allocation for ${args.capital:,.2f} (max 20% per name, buys only):")
        print(f"{'Symbol':<10} {'Weight':>7} {'Shares':>7} {'Amount':>12}")
        for row in recommender.suggest_allocation(ranked, args.capital):
            shares = "" if row["shares"] is None else row["shares"]
            print(f"{row['symbol']:<10} {row['weight'] * 100:6.1f}% {shares:>7} {row['amount']:>12,.2f}")

    if args.excel:
        path = recommender.export_excel(ranked, args.excel)
        print(f"\nRanking written to {path}")

    print(f"\n{recommender.DISCLAIMER}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
