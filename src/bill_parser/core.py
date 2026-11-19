"""Parse messy utility bill rows and spread each bill across calendar months."""
from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%b %d, %Y", "%B %d, %Y")


@dataclass(frozen=True)
class Bill:
    """One cleaned bill. The period runs from start up to, not including, end."""

    account: str
    service: str
    start: date
    end: date
    usage: float
    unit: str
    amount: float


def parse_date(text: str) -> date:
    """Parse a date written in one of the supported formats."""
    cleaned = text.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"unrecognised date {text!r}")


def parse_money(text: str) -> float:
    """Parse '$1,234.50', '1234.5' or '($150.00)' (a credit, returned negative)."""
    cleaned = text.strip().replace("$", "").replace(",", "")
    negative = cleaned.startswith("(") and cleaned.endswith(")")
    cleaned = cleaned.strip("()")
    if not cleaned:
        raise ValueError("empty amount")
    value = float(cleaned)
    return -value if negative else value


def read_bills(path: str | Path) -> tuple[list[Bill], list[str]]:
    """Return (bills, problems). Unreadable rows, exact duplicates and zero-length
    periods are left out and each one is described in problems with its line number."""
    bills: list[Bill] = []
    problems: list[str] = []
    seen: set[Bill] = set()
    with open(path, newline="", encoding="utf-8") as handle:
        for line_no, row in enumerate(csv.DictReader(handle), start=2):
            try:
                bill = Bill(
                    account=row["Account"].strip(),
                    service=row["Service"].strip().title(),
                    start=parse_date(row["Period Start"]),
                    end=parse_date(row["Period End"]),
                    usage=float(row["Usage"].replace(",", "")),
                    unit=row["Unit"].strip(),
                    amount=parse_money(row["Amount"]),
                )
            except (KeyError, ValueError) as exc:
                problems.append(f"line {line_no}: {exc}")
                continue
            if bill.end < bill.start:
                problems.append(f"line {line_no}: period ends before it starts")
                continue
            if bill.end == bill.start:
                problems.append(f"line {line_no}: zero-length period, amount {bill.amount:.2f} not allocated")
                continue
            if bill in seen:
                problems.append(f"line {line_no}: duplicate of an earlier row")
                continue
            seen.add(bill)
            bills.append(bill)
    return bills, problems


def monthly_series(bills: list[Bill]) -> list[dict[str, str | float]]:
    """Spread each bill over the days of its period and total by account, service and month."""
    usage: dict[tuple[str, str, str, str], float] = defaultdict(float)
    cost: dict[tuple[str, str, str, str], float] = defaultdict(float)
    for bill in bills:
        days = (bill.end - bill.start).days
        day = bill.start
        while day < bill.end:
            key = (bill.account, bill.service, f"{day.year}-{day.month:02d}", bill.unit)
            usage[key] += bill.usage / days
            cost[key] += bill.amount / days
            day += timedelta(days=1)
    return [
        {
            "account": k[0],
            "service": k[1],
            "month": k[2],
            "usage": round(usage[k], 1),
            "unit": k[3],
            "cost": round(cost[k], 2),
        }
        for k in sorted(usage)
    ]
