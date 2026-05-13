from __future__ import annotations

import logging
from datetime import date
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from app.ask_service import month_from_question, run_rules_ask
from app.audit_supabase import log_audit
from app.config import get_settings
from app.line_routes import handle_line_webhook
from app.line_routes import router as line_router
from app.llm_ask import answer_with_openai
from app.llm_context import build_accounting_context
from app.parse_util import is_paid_status
from app.services import (
    SheetRepository,
    monthly_report_text,
    overdue_reminder_text,
    payment_received_text,
    serialize_payable,
    serialize_receivable,
)

Audience = Literal["internal", "client"]


def get_repo() -> SheetRepository:
    return SheetRepository()


RepoDep = Annotated[SheetRepository, Depends(get_repo)]


def _fastapi_kwargs() -> dict:
    s = get_settings()
    kwargs: dict = {
        "title": "LIRA",
        "version": "0.1.0",
        "description": "BRANDVOX 経理 AI MVP（Sheets バックエンド）",
    }
    if s.public_app_url:
        kwargs["servers"] = [{"url": s.public_app_url.rstrip("/")}]
    return kwargs


app = FastAPI(**_fastapi_kwargs())
app.include_router(line_router)
# LINE Webhook よくあるパス揺れ（404 防止）
app.add_api_route("/webhook", handle_line_webhook, methods=["POST"], tags=["line"])
app.add_api_route("/webhook/line", handle_line_webhook, methods=["POST"], tags=["line"])

log = logging.getLogger(__name__)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "lira"}


def _month_or_default(month: str | None) -> str:
    if month:
        return month
    return f"{date.today().year:04d}-{date.today().month:02d}"


def _parse_iso(d: str | None) -> date | None:
    if not d:
        return None
    try:
        y, m, day = d.split("-")
        return date(int(y), int(m), int(day))
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail="日付は YYYY-MM-DD 形式で指定してください。",
        ) from e


@app.get("/summary")
def get_summary(
    repo: RepoDep,
    month: str | None = Query(None, description="YYYY-MM（省略時は当月）"),
):
    m = _month_or_default(month)
    s = repo.summary_for_month(m)
    if not s:
        return {
            "month": m,
            "found": False,
            "sales": None,
            "expenses": None,
            "profit": None,
            "margin_rate": None,
        }
    rate = s.margin_rate
    return {
        "month": m,
        "found": True,
        "sales_jpy": s.sales,
        "expenses_jpy": s.expenses,
        "profit_jpy": s.profit,
        "margin_rate": rate,
        "margin_percent": round(rate * 100, 2) if rate is not None else None,
    }


@app.get("/receivables")
def get_receivables(
    repo: RepoDep,
    month: str | None = Query(None, description="入金予定日がこの月に含まれる行に絞る YYYY-MM"),
    due_from: str | None = Query(None),
    due_to: str | None = Query(None),
):
    df = _parse_iso(due_from)
    dt = _parse_iso(due_to)
    rows = repo.load_receivables()
    out = []
    for r in rows:
        if month and r.due_date:
            key = f"{r.due_date.year:04d}-{r.due_date.month:02d}"
            if key != month:
                continue
        elif month and not r.due_date:
            continue
        if df and r.due_date and r.due_date < df:
            continue
        if dt and r.due_date and r.due_date > dt:
            continue
        out.append(serialize_receivable(r))
    return {"items": out, "count": len(out)}


@app.get("/payables")
def get_payables(
    repo: RepoDep,
    month: str | None = Query(None),
    due_from: str | None = Query(None),
    due_to: str | None = Query(None),
    open_only: bool = Query(True, description="未払いのみ"),
):
    df = _parse_iso(due_from)
    dt = _parse_iso(due_to)
    rows = repo.load_payables()
    out = []
    for p in rows:
        if open_only and not p.is_open():
            continue
        if month and p.due_date:
            key = f"{p.due_date.year:04d}-{p.due_date.month:02d}"
            if key != month:
                continue
        elif month and not p.due_date:
            continue
        if df and p.due_date and p.due_date < df:
            continue
        if dt and p.due_date and p.due_date > dt:
            continue
        out.append(serialize_payable(p))
    return {"items": out, "count": len(out)}


@app.get("/unpaid")
def get_unpaid(repo: RepoDep):
    rows = [r for r in repo.load_receivables() if r.is_unpaid()]
    return {"items": [serialize_receivable(r) for r in rows], "count": len(rows)}


@app.get("/integrations/status")
def integrations_status() -> dict[str, bool]:
    s = get_settings()
    return {
        "openai_configured": bool(s.openai_api_key),
        "supabase_configured": bool(
            s.supabase_url and (s.supabase_service_role_key or s.supabase_anon_key)
        ),
        "line_webhook_configured": bool(s.line_channel_secret and s.line_channel_access_token),
        "public_app_url_configured": bool(s.public_app_url),
    }


class MonthlyReportBody(BaseModel):
    month: str | None = Field(None, description="YYYY-MM（省略時は当月）")
    audience: Audience = "internal"


@app.post("/reports/monthly")
def post_monthly_report(body: MonthlyReportBody, repo: RepoDep):
    m = _month_or_default(body.month)
    summary = repo.summary_for_month(m)
    text = monthly_report_text(m, summary, body.audience)
    return {"month": m, "audience": body.audience, "text": text}


class RowSelection(BaseModel):
    sheet_row_indices: list[int] = Field(default_factory=list)
    audience: Audience = "internal"


@app.post("/messages/payment-received")
def post_payment_received(body: RowSelection, repo: RepoDep):
    all_rows = repo.load_receivables()
    if body.sheet_row_indices:
        idx = set(body.sheet_row_indices)
        chosen = [r for r in all_rows if r.sheet_row_index in idx]
        if not chosen:
            raise HTTPException(404, "指定した行番号に一致する入金予定がありません。")
    else:
        chosen = [r for r in all_rows if r.payment_date and is_paid_status(r.status)]
        if not chosen:
            chosen = [r for r in all_rows if r.payment_date]
    text = payment_received_text(chosen, body.audience)
    return {"audience": body.audience, "row_count": len(chosen), "text": text}


@app.post("/messages/overdue-reminder")
def post_overdue_reminder(body: RowSelection, repo: RepoDep):
    all_rows = repo.load_receivables()
    today = date.today()
    if body.sheet_row_indices:
        idx = set(body.sheet_row_indices)
        chosen = [r for r in all_rows if r.sheet_row_index in idx]
        if not chosen:
            raise HTTPException(404, "指定した行番号に一致する入金予定がありません。")
    else:
        chosen = [
            r for r in all_rows if r.is_unpaid() and r.due_date is not None and r.due_date < today
        ]
        if not chosen:
            chosen = [r for r in all_rows if r.is_unpaid()]
    text = overdue_reminder_text(chosen, body.audience)
    return {"audience": body.audience, "row_count": len(chosen), "text": text}


class AskBody(BaseModel):
    question: str = Field(..., min_length=1)


@app.post("/ask")
def post_ask(body: AskBody, repo: RepoDep):
    month = month_from_question(body.question)
    structured = run_rules_ask(body.question, repo, month)
    log_audit(
        "ask",
        {"intent": structured.get("intent"), "month": month},
    )
    s = get_settings()
    if s.openai_api_key:
        try:
            ctx = build_accounting_context(repo, month)
            answer = answer_with_openai(body.question, ctx)
            return {"mode": "openai", "answer": answer, "structured": structured}
        except Exception:
            log.exception("OpenAI /ask が失敗したためルール結果を返します")
    return {"mode": "rules", **structured}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
