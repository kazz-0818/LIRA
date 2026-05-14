from __future__ import annotations

from unittest.mock import MagicMock

from app.nl_router import route_question


def test_kongetsu_dou_summary_intent() -> None:
    repo = MagicMock()
    repo.load_receivables.return_value = []
    r = route_question("今月どう？", repo)
    assert r["intent"] == "summary"


def test_kyou_nyukin_receivables_intent() -> None:
    repo = MagicMock()
    repo.load_receivables.return_value = []
    r = route_question("今日入金ある？", repo)
    assert r["intent"] == "receivables"


def test_kongetsu_harau_payables_intent() -> None:
    repo = MagicMock()
    repo.load_receivables.return_value = []
    r = route_question("今月払うものある？", repo)
    assert r["intent"] == "payables"
