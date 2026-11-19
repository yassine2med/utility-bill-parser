from datetime import date

import pytest

from bill_parser.__main__ import main
from bill_parser.core import Bill, monthly_series, parse_date, parse_money, read_bills

HEADER = "Account,Service,Period Start,Period End,Usage,Unit,Amount\n"


def write(tmp_path, body):
    p = tmp_path / "b.csv"
    p.write_text(HEADER + body)
    return p


@pytest.mark.parametrize("text", ["2025-03-06", "03/06/2025", "03/06/25", "Mar 6, 2025", "March 6, 2025"])
def test_parse_date_formats(text):
    assert parse_date(text) == date(2025, 3, 6)


def test_parse_date_rejects_garbage():
    with pytest.raises(ValueError, match="unrecognised"):
        parse_date("last Tuesday")


@pytest.mark.parametrize("text,value", [("$1,234.50", 1234.5), ("99", 99.0), ("($150.00)", -150.0), (" $0.00 ", 0.0)])
def test_parse_money(text, value):
    assert parse_money(text) == value


def test_parse_money_empty():
    with pytest.raises(ValueError):
        parse_money("$")


def test_read_bills_cleans_service_and_numbers(tmp_path):
    p = write(tmp_path, 'A1,electric,2025-01-01,2025-02-01,"1,000",kWh,"$100.00"\n')
    bills, problems = read_bills(p)
    assert problems == []
    assert bills[0].service == "Electric" and bills[0].usage == 1000


def test_duplicates_are_reported_and_removed(tmp_path):
    row = "A1,Gas,2025-01-01,2025-02-01,10,therm,$5.00\n"
    bills, problems = read_bills(write(tmp_path, row * 2))
    assert len(bills) == 1 and "duplicate" in problems[0]


def test_zero_length_period_reported(tmp_path):
    bills, problems = read_bills(write(tmp_path, "A1,Gas,2025-01-01,2025-01-01,10,therm,($5.00)\n"))
    assert bills == [] and "not allocated" in problems[0]


def test_end_before_start_reported(tmp_path):
    _, problems = read_bills(write(tmp_path, "A1,Gas,2025-02-01,2025-01-01,10,therm,$5.00\n"))
    assert "before it starts" in problems[0]


def test_bad_usage_reported_with_line(tmp_path):
    _, problems = read_bills(write(tmp_path, "A1,Gas,2025-01-01,2025-02-01,abc,therm,$5.00\n"))
    assert problems[0].startswith("line 2")


def test_proration_splits_by_days():
    bill = Bill("A", "Gas", date(2025, 1, 21), date(2025, 2, 10), 200.0, "therm", 400.0)
    rows = monthly_series([bill])
    assert [r["month"] for r in rows] == ["2025-01", "2025-02"]
    assert rows[0]["usage"] == 110.0 and rows[1]["usage"] == 90.0
    assert sum(r["cost"] for r in rows) == pytest.approx(400.0)


def test_totals_are_preserved_across_example():
    bills, _ = read_bills("examples/bills.csv")
    total_in = sum(b.usage for b in bills)
    total_out = sum(r["usage"] for r in monthly_series(bills))
    assert total_out == pytest.approx(total_in, abs=1.0)


def test_cli_writes_output(tmp_path, capsys):
    out = tmp_path / "m.csv"
    assert main(["examples/bills.csv", "--out", str(out)]) == 0
    assert out.read_text().startswith("account,service,month")
    assert "skipped" in capsys.readouterr().err


def test_cli_missing_file():
    assert main(["missing.csv"]) == 1
