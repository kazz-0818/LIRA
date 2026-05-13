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

log = logging.getLogger(__name__)

router = APIRouter(prefix="/line", tags=["line"])


def _verify_signature(channel_secret: str, body: bytes, signature: str | None) -> bool:
    if not signature:
        return False
    mac = hmac.new(channel_secret.encode("utf-8"), body, hashlib.sha256).digest()
    expected = base64.b64encode(mac).decode()
    return hmac.compare_digest(expected, signature)


async def _reply_line(reply_token: str, text: str) -> None:
    s = get_settings()
    token = s.line_channel_access_token
    if not token:
        raise HTTPException(503, "LINE_CHANNEL_ACCESS_TOKEN が未設定です。")
    payload: dict[str, Any] = {
        "replyToken": reply_token,
        "messages": [{"type": "text", "text": text[:4800]}],
    }
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


@router.post("/webhook")
async def line_webhook(request: Request) -> dict[str, str]:
    s = get_settings()
    if not s.line_channel_secret:
        raise HTTPException(503, "LINE_CHANNEL_SECRET が未設定です。")

    body = await request.body()
    sig = request.headers.get("X-Line-Signature")
    if not _verify_signature(s.line_channel_secret, body, sig):
        raise HTTPException(400, "Invalid signature")

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
            log_audit("line_webhook", {"question_len": len(q)})
        except Exception:
            log.exception("LINE webhook 処理エラー")
            try:
                await _reply_line(
                    reply_token,
                    "LIRA でエラーが発生しました。しばらくしてからもう一度お試しください。",
                )
            except Exception:
                log.exception("LINE エラー返信も失敗")

    return {}
