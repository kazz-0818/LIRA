from __future__ import annotations

from app.horizontal_summary import extract_horizontal_monthly, looks_like_horizontal_month_header


def test_horizontal_month_header_detection() -> None:
    values = [
        ["項目", "2026/3", "2026/4", "2026/5"],
        ["売上", "100000", "200000", "300000"],
    ]
    assert looks_like_horizontal_month_header(values, 0) is True


def test_extract_horizontal_monthly() -> None:
    values = [
        ["項目", "2026-03", "2026-04"],
        ["売上", "100000", "200000"],
        ["経費", "40000", "50000"],
        ["利益", "60000", "150000"],
    ]
    m = extract_horizontal_monthly(values, 0, "2026-03")
    assert m is not None
    assert m.month == "2026-03"
    assert m.sales == 100000
    assert m.expenses == 40000
    assert m.profit == 60000
