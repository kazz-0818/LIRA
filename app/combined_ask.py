from __future__ import annotations

import logging

from app.ask_service import month_from_question, run_rules_ask
from app.config import get_settings
from app.llm_ask import answer_with_openai
from app.llm_context import build_accounting_context
from app.services import SheetRepository

log = logging.getLogger(__name__)


def _fallback_text(structured: dict) -> str:
    intent = structured.get("intent", "unknown")
    if intent == "greeting":
        return (
            "LIRA 経理部です。こんにちは。\n"
            "「今月の売上」「入金予定」「未入金」「支払い予定」など、知りたいことを送ってください。"
        )
    if intent == "summary":
        d = structured.get("data") or {}
        if not d.get("found"):
            return "今月の月次サマリー行がシート上に見つかりませんでした。"
        return (
            f"（ルール応答）売上: {d.get('sales_jpy')} 円、経費: {d.get('expenses_jpy')} 円、"
            f"利益: {d.get('profit_jpy')} 円です。"
        )
    if intent == "receivables":
        return f"（ルール応答）入金予定は {structured.get('count', 0)} 件です。"
    if intent == "payables":
        return f"（ルール応答）支払予定は {structured.get('count', 0)} 件です。"
    if intent == "unpaid":
        return f"（ルール応答）未入金候補は {structured.get('count', 0)} 件です。"
    if intent in ("payment_received", "overdue_reminder"):
        n = structured.get("count", 0)
        return (
            f"（ルール応答）{intent} 関連データ {n} 件です。" "詳細は /docs の API を参照ください。"
        )
    return "（ルール応答）売上・入金・支払・未入金・月次 などのキーワードで質問してください。"


def answer_for_user(question: str, repo: SheetRepository) -> str:
    """人が読む自然文。OpenAI が使えなければルールベースの短文。"""
    try:
        month = month_from_question(question)
        structured = run_rules_ask(question, repo, month)
        if structured.get("intent") == "greeting":
            return _fallback_text(structured)
        s = get_settings()
        if s.openai_api_key:
            try:
                ctx = build_accounting_context(repo, month)
                return answer_with_openai(question, ctx)
            except Exception:
                log.exception("OpenAI 応答失敗、フォールバックします")
        return _fallback_text(structured)
    except Exception:
        log.exception("LINE / answer_for_user: Sheets または処理エラー")
        return (
            "経理シートへの接続でエラーが出ました（認証・SPREADSHEET_ID・シート名を確認してください）。\n"
            "「売上」「入金」「未入金」など短いキーワードでもう一度お試しください。"
        )
