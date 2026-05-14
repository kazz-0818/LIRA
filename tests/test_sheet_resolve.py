from __future__ import annotations

from app.config import Settings
from app.sheet_resolve import resolve_effective_sheet_names_best_effort, score_roles_for_title


def _settings(**kw: str) -> Settings:
    d = {
        "spreadsheet_id": "dummy",
        "sheet_summary": "月次サマリー",
        "sheet_receivables": "入金予定",
        "sheet_payables": "支払予定",
    }
    d.update(kw)
    return Settings(**d)


def test_brandvox_summary_tab_scores_highest() -> None:
    t = "事業実績表(26.3-27.8)"
    sc = score_roles_for_title(t)
    assert sc["summary"] > sc["payables"]
    assert sc["summary"] > 0


def test_keihi_shosai_payables() -> None:
    t = "経費詳細"
    sc = score_roles_for_title(t)
    assert sc["payables"] >= sc["summary"]
    assert sc["payables"] > 0


def test_sponsor_file_receivables_candidate() -> None:
    t = "スポンサー管理FILE"
    sc = score_roles_for_title(t)
    assert sc["receivables"] > sc["payables"]


def test_full_brandvox_book_resolves_all_three() -> None:
    titles = [
        "事業計画表(26.3-27.8)",
        "事業実績表(26.3-27.8)",
        "経費詳細",
        "事業管理FILE",
        "スポンサー管理FILE",
    ]
    res = resolve_effective_sheet_names_best_effort(_settings(), titles)
    rs = res["resolved_sheets"]
    assert rs["summary"] == "事業実績表(26.3-27.8)"
    assert rs["receivables"] == "スポンサー管理FILE"
    assert rs["payables"] == "経費詳細"


def test_no_crash_when_only_summary_like_tab() -> None:
    titles = ["事業実績表のみ"]
    res = resolve_effective_sheet_names_best_effort(_settings(), titles)
    rs = res["resolved_sheets"]
    assert rs["summary"] == "事業実績表のみ"
    # 他ロールはヒントまたは同一再利用で埋まるか null のいずれかでも例外にならない
    assert "resolved_sheets" in res


def test_obscure_tabs_do_not_raise() -> None:
    titles = ["Alpha", "Beta"]
    res = resolve_effective_sheet_names_best_effort(_settings(), titles)
    assert res["resolved_sheets"]["summary"] is None or res["resolved_sheets"]["summary"] in titles
