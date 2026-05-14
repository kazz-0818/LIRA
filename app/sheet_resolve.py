from __future__ import annotations

import logging
from typing import Literal, TypedDict

from app.config import Settings

log = logging.getLogger(__name__)

Role = Literal["summary", "receivables", "payables"]


class SheetResolution(TypedDict):
    resolved_sheets: dict[str, str | None]
    warnings: list[str]


# (部分文字列, 重み) — 日本語はそのまま、英語は小文字化して照合
_KEYWORDS: dict[Role, tuple[tuple[str, int], ...]] = {
    "summary": (
        ("月次サマリー", 120),
        ("事業実績", 125),
        ("事業計画", 115),
        ("実績", 78),
        ("計画", 72),
        ("月次", 55),
        ("サマリー", 50),
        ("損益", 56),
        ("ｐｌ", 42),
        ("売上", 50),
        ("利益", 48),
        ("収支", 46),
        ("管理file", 62),
        ("管理ＦＩＬＥ", 62),
        ("summary", 42),
        ("monthly", 40),
        ("profit & loss", 45),
        ("p&l", 40),
        ("profit", 28),
    ),
    "receivables": (
        ("入金予定", 120),
        ("スポンサー管理", 125),
        ("スポンサー", 85),
        ("事業管理", 80),
        ("入金", 58),
        ("請求", 54),
        ("売掛", 54),
        ("未入金", 52),
        ("未収", 48),
        ("取引先", 50),
        ("売上", 35),
        ("receivable", 44),
        ("accounts receivable", 38),
        ("回収", 42),
    ),
    "payables": (
        ("支払予定", 120),
        ("経費詳細", 125),
        ("経費", 75),
        ("支払", 60),
        ("買掛", 54),
        ("未払", 50),
        ("外注", 52),
        ("仕入", 48),
        ("広告費", 50),
        ("固定費", 46),
        ("payable", 44),
        ("accounts payable", 38),
        ("ap invoice", 25),
    ),
}

# 同点時の優先（先に出るほど高優先）。タイトルに部分一致で比較（小文字化含む）
_ROLE_TAB_PRIORITY: dict[Role, tuple[str, ...]] = {
    "summary": ("事業実績", "事業計画", "管理file", "実績", "計画"),
    "receivables": ("スポンサー", "事業管理", "事業実績", "入金", "請求"),
    "payables": ("経費詳細", "経費", "事業管理", "事業実績", "支払", "外注"),
}

_DEFAULT_TAB: dict[Role, str] = {
    "summary": "月次サマリー",
    "receivables": "入金予定",
    "payables": "支払予定",
}

# スコアが付かないブック向け: タブ名に含まれる順でフォールバック（BRANDVOX 実運用の優先順）
_ORDERED_TAB_HINTS: dict[Role, tuple[str, ...]] = {
    "summary": ("事業実績", "事業計画", "事業管理"),
    "receivables": ("スポンサー管理", "スポンサー", "事業管理", "事業実績"),
    "payables": ("経費詳細", "経費", "事業管理", "事業実績", "支払"),
}


def _pick_by_ordered_hints(
    role: Role,
    titles: list[str],
    used: set[str],
    *,
    allow_reuse: bool,
) -> str | None:
    """タイトル部分一致でロール専用の優先順に割当。"""
    for hint in _ORDERED_TAB_HINTS[role]:
        for t in titles:
            if hint not in t:
                continue
            if not allow_reuse and t in used:
                continue
            return t
    return None


def _norm_title(t: str) -> str:
    return t.lower().strip().replace(" ", "").replace("　", "")


def _priority_rank(role: Role, title: str) -> int:
    """小さいほど高優先（該当しなければ大きい値）。"""
    nt = _norm_title(title)
    for i, hint in enumerate(_ROLE_TAB_PRIORITY[role]):
        h = _norm_title(hint)
        if h and h in nt:
            return i
    return 999


def _score_title(role: Role, title: str) -> int:
    lower = title.lower().strip()
    nt = _norm_title(title)
    total = 0
    for kw, pts in _KEYWORDS[role]:
        if kw.isascii():
            if kw.lower() in lower:
                total += pts
        elif kw in title:
            total += pts
        elif _norm_title(kw) in nt:
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


def _role_candidates(
    role: Role,
    configured: str,
    titles: list[str],
) -> list[tuple[int, int, int, str]]:
    """各タブの (スコア, tie-break 用優先度, 元インデックス, タイトル) を降順ソート済みで返す。"""
    cfg = (configured or "").strip()
    out: list[tuple[int, int, int, str]] = []
    for i, t in enumerate(titles):
        sc = _score_title(role, t)
        if cfg:
            if t == cfg or t.strip() == cfg:
                sc = max(sc, 10_000)
            elif cfg in t:
                sc = max(sc, 9000)
        pr = _priority_rank(role, t)
        out.append((sc, -pr, i, t))
    out.sort(key=lambda x: (-x[0], -x[1], x[2]))
    return out


def resolve_effective_sheet_names_best_effort(
    settings: Settings,
    all_titles: list[str],
) -> SheetResolution:
    """
    3 ロールを可能な限り解決。失敗ロールは null + warnings。ブックが空なら全 null。
    同一タブの重複割当は許容するが warnings に記録。
    """
    warnings: list[str] = []
    if not all_titles:
        warnings.append("スプレッドシートにタブ（シート）が1枚もありません。")
        return {
            "resolved_sheets": {"summary": None, "receivables": None, "payables": None},
            "warnings": warnings,
        }

    roles: tuple[tuple[Role, str], ...] = (
        ("summary", settings.sheet_summary),
        ("receivables", settings.sheet_receivables),
        ("payables", settings.sheet_payables),
    )

    candidates: dict[Role, list[tuple[int, int, int, str]]] = {}
    for role, cfg in roles:
        candidates[role] = _role_candidates(role, cfg, all_titles)

    assigned: dict[Role, str | None] = {"summary": None, "receivables": None, "payables": None}
    used_first: set[str] = set()

    for role, _cfg in roles:
        cand = candidates[role]
        chosen: str | None = None
        for sc, _pr, _i, name in cand:
            if sc <= 0:
                continue
            if name not in used_first:
                chosen = name
                used_first.add(name)
                break
        if chosen is None and cand and cand[0][0] > 0:
            chosen = cand[0][3]
            warnings.append(
                f"タブ「{chosen}」が複数ロールで再利用されています（{role}）。"
                "必要なら SHEET_* で個別に指定してください。"
            )
        if chosen is None:
            hinted = _pick_by_ordered_hints(role, all_titles, used_first, allow_reuse=False)
            if hinted:
                chosen = hinted
                used_first.add(chosen)
                warnings.append(
                    f"{role}: キーワードスコアが弱いため、BRANDVOX 向け優先ルールで"
                    f"「{chosen}」を選びました。誤りの場合は SHEET_* で明示してください。",
                )
        if chosen is None:
            hinted2 = _pick_by_ordered_hints(role, all_titles, used_first, allow_reuse=True)
            if hinted2:
                chosen = hinted2
                warnings.append(
                    f"{role}: 未使用タブが無かったため「{chosen}」を再利用します"
                    "（他ロールと同一の可能性）。",
                )
        if chosen is None:
            fb = _DEFAULT_TAB[role]
            if fb in all_titles:
                chosen = fb
                warnings.append(
                    f"{role}: キーワード不一致のため既定タブ「{fb}」にフォールバックしました。",
                )
        assigned[role] = chosen
        if chosen is None:
            if role == "summary":
                warnings.append(
                    "月次サマリー相当のタブを特定できませんでした。"
                    "事業実績表・事業計画表などのタブがあるか、"
                    "SHEET_SUMMARY を実タブ名に設定してください。",
                )
            elif role == "receivables":
                warnings.append(
                    "入金・売掛相当のタブを特定できませんでした。"
                    "スポンサー管理FILE や 事業管理FILE の列構造確認、"
                    "または SHEET_RECEIVABLES の指定を検討してください。",
                )
            else:
                warnings.append(
                    "支払・経費相当のタブを特定できませんでした。"
                    "経費詳細 タブの有無、または SHEET_PAYABLES の指定を検討してください。"
                )

    for role, name in assigned.items():
        if name:
            log.info("LIRA sheet resolve %s -> %s", role, name)

    return {"resolved_sheets": assigned, "warnings": warnings}


def score_roles_for_title(title: str) -> dict[str, int]:
    """デバッグ用: タブ名が各ロールにどれだけマッチするか。"""
    return {
        "summary": _score_title("summary", title),
        "receivables": _score_title("receivables", title),
        "payables": _score_title("payables", title),
    }
