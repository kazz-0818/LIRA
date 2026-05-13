from __future__ import annotations

import json
import os
from typing import Any

from google.oauth2 import service_account
from googleapiclient.discovery import build

from app.config import get_settings

SCOPES = ("https://www.googleapis.com/auth/spreadsheets.readonly",)


def build_sheets_service():
    s = get_settings()
    if s.google_service_account_json and s.google_service_account_json.strip():
        try:
            info = json.loads(s.google_service_account_json)
        except json.JSONDecodeError as e:
            raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON が有効な JSON ではありません。") from e
        creds = service_account.Credentials.from_service_account_info(
            info,
            scopes=SCOPES,
        )
        return build("sheets", "v4", credentials=creds, cache_discovery=False)

    cred_path = s.google_application_credentials or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not cred_path or not os.path.isfile(cred_path):
        raise RuntimeError(
            "Google 認証が未設定です。次のいずれかを設定してください: "
            "(1) GOOGLE_SERVICE_ACCOUNT_JSON にサービスアカウント JSON 全文 "
            "(2) GOOGLE_APPLICATION_CREDENTIALS に JSON ファイルの絶対パス"
        )
    creds = service_account.Credentials.from_service_account_file(
        cred_path,
        scopes=SCOPES,
    )
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def fetch_range(service, spreadsheet_id: str, a1_range: str) -> list[list[Any]]:
    result = (
        service.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=a1_range).execute()
    )
    return result.get("values", [])


def list_sheet_titles(service, spreadsheet_id: str) -> list[str]:
    """ブック内タブ名（表示名）を、左から順に返す。"""
    meta = (
        service.spreadsheets()
        .get(spreadsheetId=spreadsheet_id, fields="sheets.properties.title")
        .execute()
    )
    out: list[str] = []
    for sh in meta.get("sheets", []):
        props = sh.get("properties") or {}
        title = props.get("title")
        if title is not None:
            out.append(str(title))
    return out
