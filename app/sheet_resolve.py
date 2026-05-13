from __future__ import annotations

import logging
from typing import Literal

from app.config import Settings

log = logging.getLogger(__name__)

Role = Literal["summary", "receivables", "payables"]

# (部分文字列, 重み) — 日本語はそのまま、英語は小文字化して照合
_KEYWORDS: dict[Role, tuple[tuple[str, int], ...]] = {
    "summary": (
        ("月次サマリー", 120),
        ("月次", 55),
        ("サマリー", 50),
        ("損益", 48),
        ("summary", 42),
        ("monthly", 40),
        ("profit & loss", 45),
        ("p&l", 40),
        ("pl", 32),
        ("profit", 28),
    ),
    "receivables": (
        ("入金予定", 120),
        ("入金", 58),
        ("売掛", 52),
        ("未入金", 50),
        ("未収", 46),
        ("receivable", 44),
        ("accounts receivable", 38),
        ("回収", 40),
    ),
    "payables": (
        ("支払予定", 120),
        ("支払", 58),
        ("買掛", 52),
        ("未払", 48),
        ("payable", 44),
        ("accounts payable", 38),
        ("ap invoice", 25),
    ),
}

_DEFAULT_TAB: dict[Role, str] = {
    "summary": "月次サマリー",
    "receivables": "入金予定",
    "payables": "支払予定",
}


def _score_title(role: Role, title: str) -> int:
    lower = title.lower().strip()
    total = 0
    for kw, pts in _KEYWORDS[role]:
        if kw.isascii():
            if kw.lower() in lower:
                total += pts
        elif kw in title:
            total += pts

    if role == "receivables":
        compact = lower.replace(" ", "")
        if compact in ("ar", "a/r"):
            total += 88
        elif "arlist" in compact or "araging" in compact:
            total += 45
        elif "ar" in compact and "list" in compact:
            total += 40
    elif role == "payables":
        if lower in ("ap", "a/p", "a/p."):
            total += 88

    return total


def _resolve_one(role: Role, configured: str, titles: list[str]) -> tuple[str, str | None]:
    """
    1 ロール分の実タブ名を返す。
    戻り値: (解決後タイトル, ログ用ヒント。完全一致なら None)
    """
    cfg = configured.strip()
    if cfg in titles:
        return cfg, None
    for t in titles:
        if t.strip() == cfg:
            return t, f"{role}: 前後空白の差を吸収し「{t}」を使用"

    if len(cfg) >= 2:
        hits = [t for t in titles if cfg in t]
        if len(hits) == 1:
            return hits[0], f"{role}: 設定「{cfg}」がタブ名に部分一致 →「{hits[0]}」"

    scored: list[tuple[int, int, str]] = []
    for i, t in enumerate(titles):
        scored.append((_score_title(role, t), i, t))
    scored.sort(key=lambda x: (-x[0], x[1]))
    best_sc, _, best_t = scored[0]

    if best_sc > 0:
        return best_t, f"{role}: キーワードで「{best_t}」を自動選択 (score={best_sc})"

    fallback = _DEFAULT_TAB[role]
    if fallback in titles:
        return fallback, f"{role}: キーワード不一致のため既定タブ「{fallback}」を使用"

    return "", None


def resolve_effective_sheet_names(settings: Settings, all_titles: list[str]) -> tuple[str, str, str]:
    """環境変数とブック内タブから、実際に読む 3 タブ名を決める。"""
    if not all_titles:
        raise RuntimeError("スプレッドシートにタブ（シート）が1枚もありません。")

    roles: tuple[tuple[Role, str], ...] = (
        ("summary", settings.sheet_summary),
        ("receivables", settings.sheet_receivables),
        ("payables", settings.sheet_payables),
    )
    resolved: list[str] = []
    for role, cfg in roles:
        name, hint = _resolve_one(role, cfg, all_titles)
        if not name:
            tabs = "、".join(all_titles)
            raise RuntimeError(
                f"シートの自動判定に失敗しました（{role} / 設定「{cfg}」）。"
                f"ブック内のタブ: {tabs}"
            )
        if hint:
            log.info("LIRA %s", hint)
        resolved.append(name)

    if len(set(resolved)) < 3:
        log.warning(
            "LIRA シート解決: 同一タブが複数ロールに割り当てられています → %s",
            resolved,
        )
    return resolved[0], resolved[1], resolved[2]
