from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from app.audit_supabase import log_audit
from app.combined_ask import answer_for_user
from app.config import get_settings
from app.services import SheetRepository
from app.sheets_errors import format_sheets_user_message

log = logging.getLogger(__name__)

router = APIRouter(prefix="/line", tags=["line"])


def _verify_signature(channel_secret: str, body: bytes, signature: str | None) -> bool:
    if not signature:
        return False
    mac = hmac.new(channel_secret.encode("utf-8"), body, hashlib.sha256).digest()
    expected = base64.b64encode(mac).decode()
    return hmac.compare_digest(expected, signature)


async def _reply_line(reply_token: str, text: str) -> bool:
    """返信 API を叩く。失敗しても例外は出さない（Webhook 本体は 200 を返すため）。"""
    s = get_settings()
    token = s.line_channel_access_token
    if not token:
        log.warning("LINE_CHANNEL_ACCESS_TOKEN 未設定のため返信できません")
        return False
    payload: dict[str, Any] = {
        "replyToken": reply_token,
        "messages": [{"type": "text", "text": text[:4800]}],
    }
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                "https://api.line.me/v2/bot/message/reply",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=45.0,
            )
        if r.status_code >= 400:
            log.warning("LINE reply API: %s %s", r.status_code, r.text[:500])
            return False
    except Exception:
        log.exception("LINE reply API 通信エラー")
        return False
    return True


async def handle_line_webhook(request: Request) -> dict[str, str]:
    s = get_settings()
    if not s.line_channel_secret:
        raise HTTPException(503, "LINE_CHANNEL_SECRET が未設定です。")

    body = await request.body()
    sig = request.headers.get("X-Line-Signature")
    if not _verify_signature(s.line_channel_secret, body, sig):
        raise HTTPException(400, "Invalid signature")

    if not body.strip():
        return {}

    try:
        data = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as e:
        raise HTTPException(400, "Invalid JSON") from e

    for ev in data.get("events", []):
        if ev.get("type") != "message":
            continue
        msg = ev.get("message") or {}
        if msg.get("type") != "text":
            continue
        q = (msg.get("text") or "").strip()
        reply_token = ev.get("replyToken")
        if not q or not reply_token:
            continue

        def _work(text: str = q) -> str:
            repo = SheetRepository()
            return answer_for_user(text, repo)

        try:
            text_out = await run_in_threadpool(_work)
            await _reply_line(reply_token, text_out)
        except Exception as e:
            log.exception("LINE webhook 処理エラー")
            detail = format_sheets_user_message(e)
            err_reply = (
                f"{detail}\n\n"
                "「売上」「入金」「未入金」など短いキーワードでもう一度お試しください。\n"
                "改善しない場合は時間をおいて再試行してください。"
            )
            try:
                await _reply_line(reply_token, err_reply)
            except Exception:
                log.exception("LINE エラー返信も失敗")
        else:
            try:
                log_audit("line_webhook", {"question_len": len(q)})
            except Exception:
                log.exception("監査ログ（Supabase）の記録に失敗しました（返信は済み）")

    return {}


@router.post("/webhook")
async def line_webhook(request: Request) -> dict[str, str]:
    return await handle_line_webhook(request)
