from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

_MONTH_RE = re.compile(r"^(\d{4})[-/](\d{1,2})$")


def parse_jpy_amount(raw: Any) -> int | None:
    if raw is None:
        return None
    if isinstance(raw, int | float):
        return int(Decimal(str(raw)).quantize(Decimal("1")))
    s = str(raw).strip()
    if not s:
        return None
    s = s.replace("¥", "").replace(",", "").replace("，", "").replace("円", "").strip()
    try:
        return int(Decimal(s).quantize(Decimal("1")))
    except (InvalidOperation, ValueError):
        return None


def parse_date(raw: Any) -> date | None:
    if raw is None:
        return None
    if isinstance(raw, date) and not isinstance(raw, datetime):
        return raw
    s = str(raw).strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(s[:10], fmt).date()
        except ValueError:
            continue
    try:
        n = float(s)
        if 30000 < n < 60000:
            epoch = date(1899, 12, 30)
            return date.fromordinal(epoch.toordinal() + int(n))
    except ValueError:
        pass
    return None


def parse_month_key(raw: Any) -> str | None:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    m = _MONTH_RE.match(s)
    if m:
        y, mo = int(m.group(1)), int(m.group(2))
        return f"{y:04d}-{mo:02d}"
    try:
        d = parse_date(s)
        if d:
            return f"{d.year:04d}-{d.month:02d}"
    except Exception:
        pass
    return None


def parse_bool_flag(raw: Any) -> bool | None:
    if raw is None:
        return None
    if isinstance(raw, bool):
        return raw
    s = str(raw).strip().lower()
    if s in ("true", "1", "yes", "y", "はい"):
        return True
    if s in ("false", "0", "no", "n", "いいえ"):
        return False
    return None


def truthy_unpaid_flag(raw: Any) -> bool:
    b = parse_bool_flag(raw)
    if b is True:
        return True
    if isinstance(raw, str) and raw.strip().upper() == "TRUE":
        return True
    return False


def is_paid_status(status: str | None) -> bool:
    if not status:
        return False
    s = status.strip()
    return s in ("入金済", "支払済", "済", "完了", "paid", "Paid")


def is_unpaid_receivable(
    status: str | None,
    payment_date: date | None,
    unpaid_flag: Any,
) -> bool:
    if truthy_unpaid_flag(unpaid_flag):
        return True
    if payment_date is not None:
        return False
    if status and is_paid_status(status):
        return False
    return True
