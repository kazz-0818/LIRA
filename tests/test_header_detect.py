from __future__ import annotations

from app.header_detect import detect_header_row_index


def test_header_detect_finds_row_with_many_column_labels() -> None:
    values = [
        ["タイトル", "", ""],
        ["メモ", "x", "y"],
        ["", "", ""],
        ["取引先", "金額", "入金日", "ステータス", "メモ"],
        ["A社", "1000", "", "未入金", ""],
    ]
    idx, sc = detect_header_row_index(
        values,
        max_scan=20,
        min_score=4,
        fallback_index=0,
    )
    assert idx == 3
    assert sc >= 4


def test_header_row_fixed_fallback_when_high_min_score() -> None:
    values = [["a"], ["b"]]
    idx, _ = detect_header_row_index(values, max_scan=2, min_score=99, fallback_index=0)
    assert idx == 0
