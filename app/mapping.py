from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from app.parse_util import (
    is_paid_status,
    is_unpaid_receivable,
    parse_date,
    parse_jpy_amount,
    parse_month_key,
)


def _norm_header(h: str) -> str:
    return str(h).strip()


def rows_to_dicts(
    values: list[list[Any]],
    header_row_index: int,
) -> tuple[list[str], list[dict[str, Any]]]:
    """header_row_index: 0-based index within `values` for header row."""
    if not values or header_row_index >= len(values):
        return [], []
    headers = [_norm_header(c) for c in values[header_row_index]]
    rows: list[dict[str, Any]] = []
    for line in values[header_row_index + 1 :]:
        padded = list(line) + [""] * max(0, len(headers) - len(line))
        row = {headers[i]: padded[i] for i in range(len(headers))}
        rows.append(row)
    return headers, rows


@dataclass
class MonthlySummaryRow:
    month: str
    sales: int | None
    expenses: int | None
    profit: int | None
    margin_rate: float | None


def pick(row: dict[str, Any], *keys: str) -> Any:
    for k in keys:
        if k in row and row[k] not in ("", None):
            return row[k]
    return None


def row_to_monthly_summary(row: dict[str, Any]) -> MonthlySummaryRow | None:
    mk = parse_month_key(pick(row, "対象月", "月", "対象年月"))
    if not mk:
        return None
    sales = parse_jpy_amount(pick(row, "売上合計", "売上", "売上高"))
    expenses = parse_jpy_amount(pick(row, "経費合計", "経費", "費用合計"))
    profit = parse_jpy_amount(pick(row, "利益", "営業利益", "純利益"))
    margin_raw = pick(row, "利益率", "粗利率")
    margin_rate: float | None = None
    if margin_raw not in (None, ""):
        s = str(margin_raw).strip().replace("%", "")
        try:
            v = float(s)
            margin_rate = v / 100 if v > 1 else v
        except ValueError:
            margin_rate = None
    if profit is None and sales is not None and expenses is not None:
        profit = sales - expenses
    if margin_rate is None and profit is not None and sales not in (None, 0):
        margin_rate = profit / sales if sales else None
    return MonthlySummaryRow(
        month=mk,
        sales=sales,
        expenses=expenses,
        profit=profit,
        margin_rate=margin_rate,
    )


@dataclass
class ReceivableRow:
    sheet_row_index: int
    client: str | None
    title: str | None
    amount: int | None
    due_date: date | None
    payment_date: date | None
    status: str | None
    confirm_check: str | None
    unpaid_flag: Any
    memo: str | None
    last_notice: date | None

    def is_unpaid(self) -> bool:
        return is_unpaid_receivable(self.status, self.payment_date, self.unpaid_flag)


def row_to_receivable(sheet_row_index: int, row: dict[str, Any]) -> ReceivableRow:
    return ReceivableRow(
        sheet_row_index=sheet_row_index,
        client=((str(pick(row, "クライアント", "顧客", "取引先") or "")).strip() or None),
        title=((str(pick(row, "案件名", "請求書番号", "件名") or "")).strip() or None),
        amount=parse_jpy_amount(pick(row, "請求金額", "金額", "請求額")),
        due_date=parse_date(pick(row, "入金予定日", "予定日")),
        payment_date=parse_date(pick(row, "入金日", "実入金日")),
        status=(str(pick(row, "入金ステータス", "ステータス") or "").strip() or None),
        confirm_check=(str(pick(row, "入金確認チェック", "確認") or "").strip() or None),
        unpaid_flag=pick(row, "未入金フラグ", "未入金"),
        memo=(str(pick(row, "メモ", "備考") or "").strip() or None),
        last_notice=parse_date(pick(row, "最終通知日", "督促日")),
    )


@dataclass
class PayableRow:
    sheet_row_index: int
    due_date: date | None
    vendor: str | None
    amount: int | None
    status: str | None
    memo: str | None

    def is_open(self) -> bool:
        if self.status and is_paid_status(self.status):
            return False
        return True


def row_to_payable(sheet_row_index: int, row: dict[str, Any]) -> PayableRow:
    return PayableRow(
        sheet_row_index=sheet_row_index,
        due_date=parse_date(pick(row, "支払予定日", "予定日")),
        vendor=(str(pick(row, "支払先", "取引先", "支払先名") or "").strip() or None),
        amount=parse_jpy_amount(pick(row, "支払金額", "金額")),
        status=(str(pick(row, "支払ステータス", "ステータス") or "").strip() or None),
        memo=((str(pick(row, "メモ", "備考") or "")).strip() or None),
    )
