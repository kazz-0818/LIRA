from __future__ import annotations

from datetime import date
from typing import Any

from app.nl_router import extract_month, route_question
from app.services import SheetRepository, serialize_payable, serialize_receivable


def month_from_question(question: str) -> str:
    return extract_month(question) or f"{date.today().year:04d}-{date.today().month:02d}"


def run_rules_ask(question: str, repo: SheetRepository, month: str) -> dict[str, Any]:
    """キーワードルーティング + スプレッドシート由来の構造化データ（従来の /ask 相当）。"""
    route = route_question(question, repo)
    intent = route["intent"]

    if intent == "greeting":
        return {"intent": "greeting"}

    if intent == "summary":
        s = repo.summary_for_month(month)
        return {
            "intent": intent,
            "month": month,
            "data": {
                "found": s is not None,
                "sales_jpy": s.sales if s else None,
                "expenses_jpy": s.expenses if s else None,
                "profit_jpy": s.profit if s else None,
            },
        }
    if intent == "receivables":
        rows = repo.load_receivables()
        sample = [serialize_receivable(r) for r in rows[:5]]
        return {"intent": intent, "count": len(rows), "sample": sample}
    if intent == "payables":
        rows = repo.load_payables()
        sample = [serialize_payable(p) for p in rows[:5]]
        return {"intent": intent, "count": len(rows), "sample": sample}
    if intent == "unpaid":
        rows = [r for r in repo.load_receivables() if r.is_unpaid()]
        sample = [serialize_receivable(r) for r in rows[:5]]
        return {"intent": intent, "count": len(rows), "sample": sample}
    if intent == "payment_received":
        rows = [r for r in repo.load_receivables() if r.payment_date]
        return {"intent": intent, "count": len(rows)}
    if intent == "overdue_reminder":
        rows = [r for r in repo.load_receivables() if r.is_unpaid()]
        return {"intent": intent, "count": len(rows)}

    return {"intent": "unknown", "route": route}
