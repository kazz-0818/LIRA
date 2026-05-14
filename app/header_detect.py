"""ヘッダー行の自動検出（1〜20行目を走査）。"""

from __future__ import annotations

from typing import Any

# 列名・ヘッダらしさのスコア用トークン（部分一致）
_HEADER_TOKENS: tuple[str, ...] = (
    "売上",
    "経費",
    "利益",
    "日付",
    "項目",
    "金額",
    "支払",
    "入金",
    "ステータス",
    "予定",
    "クライアント",
    "取引先",
    "メモ",
    "備考",
    "対象月",
    "請求",
    "未入金",
    "スポンサー",
    "内容",
    "状況",
    "合計",
    "粗利",
    "純利益",
    "収支",
    "実績",
    "計画",
)


def _cell_text(c: Any) -> str:
    return str(c).strip() if c is not None else ""


def score_row_as_header(row: list[Any]) -> int:
    """行がヘッダらしいほど高スコア。"""
    if not row:
        return 0
    texts = [_cell_text(c) for c in row[:40]]
    joined = " ".join(t for t in texts if t)
    if not joined:
        return 0
    score = 0
    for tok in _HEADER_TOKENS:
        if tok in joined:
            score += 2
    # 複数の非空セルがあるとヘッダらしい
    nonempty = sum(1 for t in texts if t)
    if nonempty >= 3:
        score += 2
    if nonempty >= 5:
        score += 1
    return score


def detect_header_row_index(
    values: list[list[Any]],
    *,
    max_scan: int = 20,
    min_score: int = 4,
    fallback_index: int = 0,
) -> tuple[int, int]:
    """
    0-based のヘッダー行インデックスとスコアを返す。
    最高スコアが min_score 未満なら fallback_index を使う。
    """
    if not values:
        return 0, 0
    best_i = max(0, min(fallback_index, len(values) - 1))
    best_sc = -1
    limit = min(max_scan, len(values))
    for i in range(limit):
        row = values[i] if i < len(values) else []
        sc = score_row_as_header(row)
        if sc > best_sc:
            best_sc = sc
            best_i = i
    if best_sc < min_score:
        return max(0, min(fallback_index, len(values) - 1)), best_sc
    return best_i, best_sc
