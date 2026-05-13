from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from app.config import get_settings


def answer_with_openai(question: str, context: dict[str, Any]) -> str:
    s = get_settings()
    if not s.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY が未設定です。")

    client = OpenAI(api_key=s.openai_api_key)
    payload = json.dumps(context, ensure_ascii=False, default=str)

    system = (
        "あなたは株式会社BRANDVOXの経理担当AI「LIRA」です。\n"
        "次の JSON は Google スプレッドシートから読み取った事実データです。"
        "JSON にない数値や取引はでっち上げず、「シート上では確認できません」と述べてください。\n"
        "ユーザーの質問に、簡潔な日本語で答えてください。箇条書き可。"
    )
    user = f"質問:\n{question}\n\n参照データ (JSON):\n{payload}"

    resp = client.chat.completions.create(
        model=s.openai_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.3,
        max_tokens=1200,
    )
    choice = resp.choices[0].message.content
    if not choice:
        raise RuntimeError("OpenAI から空の応答でした。")
    return choice.strip()
