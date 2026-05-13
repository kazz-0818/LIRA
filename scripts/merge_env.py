#!/usr/bin/env python3
"""Merge missing keys from .env.example into .env (never overwrites existing keys).

Usage (repo root):
  python scripts/merge_env.py

GCP の JSON を 1 行にしたいとき（Render 用など）:
  jq -c . path/to/sa.json
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
EXAMPLE_PATH = ROOT / ".env.example"
BACKUP_PATH = ROOT / ".env.bak"

ENV_ASSIGN = re.compile(r"^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$")


def _defined_keys(env_text: str) -> set[str]:
    keys: set[str] = set()
    for raw in env_text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = ENV_ASSIGN.match(line)
        if m:
            keys.add(m.group(1))
    return keys


def main() -> int:
    if not EXAMPLE_PATH.is_file():
        print(f"見つかりません: {EXAMPLE_PATH}", file=sys.stderr)
        return 1

    example_lines = EXAMPLE_PATH.read_text(encoding="utf-8").splitlines()
    if ENV_PATH.is_file():
        current = ENV_PATH.read_text(encoding="utf-8")
        shutil.copy2(ENV_PATH, BACKUP_PATH)
    else:
        current = ""

    have = _defined_keys(current)
    additions: list[str] = []
    added_keys: list[str] = []

    for line in example_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        m = ENV_ASSIGN.match(stripped)
        if not m:
            continue
        key = m.group(1)
        if key in have:
            continue
        additions.append(line)
        added_keys.append(key)
        have.add(key)

    if not additions:
        print("追加するキーはありません（.env に .env.example のキーは揃っています）。")
        return 0

    sep = "" if current.endswith("\n") or not current else "\n"
    block = "\n".join(additions)
    new_body = f"{current.rstrip()}{sep}\n# --- merged from .env.example ---\n{block}\n"
    ENV_PATH.write_text(new_body, encoding="utf-8")
    print(f"追加したキー: {', '.join(added_keys)}")
    print(f"バックアップ: {BACKUP_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
