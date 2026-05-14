"""GET /debug/sheets 用のシート診断ペイロード構築。"""

from __future__ import annotations

import re
from typing import Any

from app.config import Settings
from app.header_detect import detect_header_row_index, score_row_as_header
from app.mapping import rows_to_dicts
from app.sheet_resolve import resolve_effective_sheet_names_best_effort, score_roles_for_title
from app.sheets_client import fetch_range


def _escape_sheet(name: str) -> str:
    return "'" + name.replace("'", "''") + "'"


def _preview_cell(v: Any, *, debug: bool) -> str:
    if v is None:
        return ""
    s = str(v).replace("\n", " ").strip()
    if debug:
        return s[:200] + ("…" if len(s) > 200 else "")
    return s[:48] + ("…" if len(s) > 48 else "")


def _preview_grid(
    values: list[list[Any]],
    *,
    debug: bool,
    max_rows: int = 10,
    max_cols: int = 15,
) -> list[list[str]]:
    out: list[list[str]] = []
    for r in range(min(max_rows, len(values))):
        row = values[r]
        ncols = min(max_cols, len(row) if row else 0)
        line = [
            _preview_cell(row[c] if c < len(row) else None, debug=debug) for c in range(ncols)
        ]
        if not line and r < len(values) and not values[r]:
            line = []
        elif not line and row:
            line = [_preview_cell(row[0], debug=debug)] if row else []
        out.append(line)
    return out


def _inferred_role_from_scores(scores: dict[str, int]) -> str:
    best = max(scores.values()) if scores else 0
    if best <= 0:
        return "unknown"
    tops = [k for k, v in scores.items() if v == best]
    return tops[0] if len(tops) == 1 else "/".join(tops)


def _missing_for_receivable(headers_joined: str) -> list[str]:
    need = ["取引先", "金額", "日付", "入金", "ステータス"]
    return [k for k in need if k not in headers_joined]


def _missing_for_payable(headers_joined: str) -> list[str]:
    need = ["日付", "金額", "支払", "項目", "ステータス"]
    return [k for k in need if k not in headers_joined]


def _missing_for_summary(headers_joined: str) -> list[str]:
    need = ["売上", "経費", "利益", "月", "対象"]
    hits = sum(1 for k in need if k in headers_joined)
    if hits >= 2:
        return []
    return [
        "対象月または売上・経費・利益の列が見当たりません。"
        "（縦持ち／横持ちの別形式の可能性があります）"
    ]


def build_sheets_debug(
    settings: Settings,
    titles: list[str],
    service: Any,
    spreadsheet_id: str,
    *,
    debug: bool = False,
) -> dict[str, Any]:
    resolution = resolve_effective_sheet_names_best_effort(settings, titles)
    rs = resolution["resolved_sheets"]

    tabs_payload: list[dict[str, Any]] = []
    for title in titles:
        a1 = f"{_escape_sheet(title)}!A1:O10"
        try:
            values = fetch_range(service, spreadsheet_id, a1)
        except Exception as e:
            tabs_payload.append(
                {
                    "title": title,
                    "error": f"{type(e).__name__}: {e!s}"[:300],
                    "role_scores": score_roles_for_title(title),
                },
            )
            continue

        fb = settings.header_row - 1
        auto_i, auto_sc = detect_header_row_index(
            values,
            max_scan=20,
            min_score=4,
            fallback_index=fb,
        )
        header_candidates: list[dict[str, Any]] = []
        for i in range(min(20, len(values))):
            row = values[i] if i < len(values) else []
            sc = score_row_as_header(row)
            if sc > 0:
                header_candidates.append({"row_1based": i + 1, "score": sc})

        scores = score_roles_for_title(title)
        inferred = _inferred_role_from_scores(scores)

        headers_joined = ""
        missing_cols: list[str] = []
        if values:
            hi = auto_i if settings.header_row_auto else max(0, min(fb, len(values) - 1))
            hdrs, _dict_rows = rows_to_dicts(values, hi)
            headers_joined = " ".join(str(h) for h in hdrs)
            if title == rs.get("summary"):
                missing_cols.extend(_missing_for_summary(headers_joined))
            if title == rs.get("receivables"):
                missing_cols.extend(_missing_for_receivable(headers_joined))
            if title == rs.get("payables"):
                missing_cols.extend(_missing_for_payable(headers_joined))
            missing_cols = list(dict.fromkeys(missing_cols))[:12]

        tabs_payload.append(
            {
                "title": title,
                "first_rows_preview": _preview_grid(values, debug=debug),
                "header_row_auto_index_0based": auto_i,
                "header_row_auto_score": auto_sc,
                "header_candidates": header_candidates[:8],
                "role_scores": scores,
                "inferred_role_hint": inferred,
                "missing_columns_hint": missing_cols,
            },
        )

    rec_env: dict[str, str | None] = {
        "SHEET_SUMMARY": rs.get("summary"),
        "SHEET_RECEIVABLES": rs.get("receivables"),
        "SHEET_PAYABLES": rs.get("payables"),
    }
    if settings.header_row_auto:
        rec_env["HEADER_ROW_AUTO"] = "true"
        rec_env["HEADER_ROW"] = str(settings.header_row)

    view_sheets = [
        {
            "name": "LIRA_月次サマリー_VIEW（推奨）",
            "purpose": (
                "縦持ちで 対象月・売上合計・経費合計・利益 を並べると安定して読み取れます。"
            ),
            "formula_hint": "=IMPORTRANGE または =QUERY で実績表から必要列だけコピー",
        },
        {
            "name": "LIRA_入金予定_VIEW（推奨）",
            "purpose": (
                "スポンサー管理から 取引先・金額・入金予定日・入金日・ステータス を揃えたビュー"
            ),
        },
        {
            "name": "LIRA_支払予定_VIEW（推奨）",
            "purpose": "経費詳細から 支払予定日・支払先・金額・ステータス を揃えたビュー",
        },
    ]

    return {
        "spreadsheet_id": (
            spreadsheet_id if debug else re.sub(r"(.{4}).+", r"\1***", spreadsheet_id)
        ),
        "debug_mode": debug,
        "tab_titles": titles,
        "tabs": tabs_payload,
        "resolved_sheets": rs,
        "warnings": resolution["warnings"],
        "recommended_environment": rec_env,
        "recommended_lira_view_sheets": view_sheets,
        "operational_hints": [
            "Render: GET /health の git_commit が GitHub main の最新と一致するか確認してください。",
            (
                "環境変数に古い SHEET_* があると、その名前をヒントとして優先します。"
                "不要なら削除か実タブ名に更新してください。"
            ),
            (
                "Supabase / OpenAI はタブ解決とは無関係です。"
                "接続不可時は主に Google 認証・SPREADSHEET_ID・タブ名を確認してください。"
            ),
        ],
    }
