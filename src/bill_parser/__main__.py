"""Command line: python -m bill_parser BILLS.csv [--out monthly.csv]."""
from __future__ import annotations

import argparse
import csv
import sys

from .core import monthly_series, read_bills


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns a process exit code."""
    parser = argparse.ArgumentParser(prog="bill_parser", description="Monthly series from utility bills")
    parser.add_argument("csv", help="CSV: Account,Service,Period Start,Period End,Usage,Unit,Amount")
    parser.add_argument("--out", help="also write the monthly series to this CSV")
    args = parser.parse_args(argv)
    try:
        bills, problems = read_bills(args.csv)
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    series = monthly_series(bills)
    print(f"{'account':<10}{'service':<10}{'month':<9}{'usage':>10} {'unit':<6}{'cost':>10}")
    for r in series:
        print(f"{r['account']:<10}{r['service']:<10}{r['month']:<9}{r['usage']:>10.1f} {r['unit']:<6}{r['cost']:>10.2f}")
    for problem in problems:
        print(f"skipped {problem}", file=sys.stderr)
    if args.out:
        with open(args.out, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["account", "service", "month", "usage", "unit", "cost"])
            writer.writeheader()
            writer.writerows(series)
    return 0


if __name__ == "__main__":
    sys.exit(main())
