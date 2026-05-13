from __future__ import annotations

from datetime import date
from typing import Any

from app.services import SheetRepository, serialize_payable, serialize_receivable


def build_accounting_context(repo: SheetRepository, month: str) -> dict[str, Any]:
    """OpenAI に渡す事実ベースの JSON（トークン節約のため件数上限あり）。"""
    today = date.today()
    summary = repo.summary_for_month(month)
    summ_dict: dict[str, Any] | None = None
    if summary:
        summ_dict = {
            "month": summary.month,
            "sales_jpy": summary.sales,
            "expenses_jpy": summary.expenses,
            "profit_jpy": summary.profit,
            "margin_rate": summary.margin_rate,
        }

    rec_all = repo.load_receivables()
    unpaid = [serialize_receivable(r) for r in rec_all if r.is_unpaid()][:40]
    due_today = [serialize_receivable(r) for r in rec_all if r.due_date == today][:25]
    overdue = [
        serialize_receivable(r)
        for r in rec_all
        if r.is_unpaid() and r.due_date is not None and r.due_date < today
    ][:25]

    pay_all = repo.load_payables()
    pay_open = [serialize_payable(p) for p in pay_all if p.is_open()][:40]
    pay_due_today = [serialize_payable(p) for p in pay_all if p.is_open() and p.due_date == today][
        :25
    ]

    return {
        "as_of": today.isoformat(),
        "target_month": month,
        "monthly_summary_row": summ_dict,
        "unpaid_receivables": unpaid,
        "receivables_due_today": due_today,
        "overdue_unpaid_receivables": overdue,
        "open_payables": pay_open,
        "payables_due_today": pay_due_today,
    }
