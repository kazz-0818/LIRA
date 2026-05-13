from __future__ import annotations

import re
from datetime import date
from typing import Any

from app.services import SheetRepository

_MONTH_RE = re.compile(r"(20\d{2})[-年/](\d{1,2})")


def extract_month(question: str) -> str | None:
    m = _MONTH_RE.search(question)
    if not m:
        return None
    y, mo = int(m.group(1)), int(m.group(2))
    return f"{y:04d}-{mo:02d}"


def route_question(question: str, repo: SheetRepository) -> dict[str, Any]:
    q = question.strip()
    month = extract_month(q) or f"{date.today().year:04d}-{date.today().month:02d}"

    if any(k in q for k in ("督促", "遅延", "延滞", "未入金", "overdue")):
        rows = [r for r in repo.load_receivables() if r.is_unpaid()]
        return {"intent": "overdue_reminder", "month": month, "unpaid_count": len(rows)}

    if any(k in q for k in ("入金確認", "入金済", "支払いました", "振込済")):
        rows = [r for r in repo.load_receivables() if r.payment_date]
        return {"intent": "payment_received", "rows_with_payment_date": len(rows)}

    if any(k in q for k in ("未払い", "未入金一覧", "未収")):
        rows = [r for r in repo.load_receivables() if r.is_unpaid()]
        return {"intent": "unpaid", "count": len(rows)}

    if any(k in q for k in ("支払", "買掛", "payable")):
        return {"intent": "payables", "count": len(repo.load_payables())}

    if any(k in q for k in ("入金予定", "売掛", "レシーバブル", "receivable")):
        return {"intent": "receivables", "count": len(repo.load_receivables())}

    if any(
        k in q
        for k in (
            "月次",
            "レポート",
            "サマリー",
            "売上",
            "経費",
            "利益",
            "summary",
        )
    ):
        s = repo.summary_for_month(month)
        return {
            "intent": "summary",
            "month": month,
            "found": s is not None,
        }

    return {
        "intent": "unknown",
        "hint": "売上・入金・支払・未入金・月次 などのキーワードで試してください。",
    }
