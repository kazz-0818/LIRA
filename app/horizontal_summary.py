"""横持ち（月が列方向）の月次サマリー表を読む。"""

from __future__ import annotations

import re
from typing import Any

from app.mapping import MonthlySummaryRow
from app.parse_util import parse_jpy_amount, parse_month_key_from_cell

# 行ラベル（第1列想定）から売上・経費・利益を推定
_SALES_LABELS = re.compile(
    r"(売上|売上合計|売上高|収入|売上実績|売上計)",
)
_EXPENSE_LABELS = re.compile(
    r"(経費|経費合計|支出|費用|原価|広告費|外注費|費用合計)",
)
_PROFIT_LABELS = re.compile(
    r"(利益|営業利益|粗利|純利益|差引|収支)",
)


def looks_like_horizontal_month_header(values: list[list[Any]], header_row_index: int) -> bool:
    """見出し行に複数の「月」列が並んでいれば横持ち月次とみなす。"""
    if header_row_index >= len(values):
        return False
    row = values[header_row_index]
    months: list[str] = []
    for cell in row[1:]:  # 左端は「項目」列のことが多い
        mk = parse_month_key_from_cell(cell)
        if mk and mk not in months:
            months.append(mk)
    return len(months) >= 2


def _row_label(values: list[list[Any]], r: int) -> str:
    if r >= len(values) or not values[r]:
        return ""
    row = values[r]
    for c in range(min(3, len(row))):
        t = str(row[c]).strip() if row[c] is not None else ""
        if t:
            return t
    return ""


def extract_horizontal_monthly(
    values: list[list[Any]],
    header_row_index: int,
    month: str,
) -> MonthlySummaryRow | None:
    """
    形式B: 1行目が月列、左列が項目名の表から指定月の MonthlySummaryRow を構築。
    """
    if header_row_index >= len(values):
        return None
    header = values[header_row_index]
    col_idx: int | None = None
    for j, cell in enumerate(header):
        mk = parse_month_key_from_cell(cell)
        if mk == month:
            col_idx = j
            break
    if col_idx is None:
        return None

    sales = expenses = profit = None
    for r in range(header_row_index + 1, len(values)):
        label = _row_label(values, r)
        if not label:
            continue
        row = values[r]
        raw = row[col_idx] if col_idx < len(row) else None
        val = parse_jpy_amount(raw)
        if val is None:
            continue
        if _SALES_LABELS.search(label):
            sales = val
        elif _EXPENSE_LABELS.search(label):
            expenses = val
        elif _PROFIT_LABELS.search(label):
            profit = val

    if sales is None and expenses is None and profit is None:
        return None

    if profit is None and sales is not None and expenses is not None:
        profit = sales - expenses

    margin_rate = None
    if profit is not None and sales not in (None, 0):
        margin_rate = profit / sales if sales else None

    return MonthlySummaryRow(
        month=month,
        sales=sales,
        expenses=expenses,
        profit=profit,
        margin_rate=margin_rate,
    )
