from __future__ import annotations

from googleapiclient.errors import HttpError


def format_sheets_user_message(exc: BaseException) -> str:
    """LINE 返信用。秘密は含めない。"""
    if isinstance(exc, HttpError):
        status = getattr(exc.resp, "status", None) if exc.resp else None
        if status == 403:
            return (
                "スプレッドシートへのアクセスが拒否されました（403）。\n"
                "サービスアカウントのメール（…@….iam.gserviceaccount.com）を、"
                "シートの「共有」で Editor として追加したか確認してください。"
            )
        if status == 404:
            return (
                "スプレッドシートが見つかりませんでした（404）。\n"
                "SPREADSHEET_ID は URL の /d/ と /edit/ の間の文字列だけにしてください"
                "（?gid= 以降は含めない）。"
            )
        if status == 400:
            return (
                "Sheets API がリクエスト不正と判断しました（400）。\n"
                "シート名（SHEET_SUMMARY / SHEET_RECEIVABLES / SHEET_PAYABLES）の"
                "スペル・全角半角を実シートと一致させてください。"
            )
        return (
            f"Google Sheets API でエラーになりました（HTTP {status}）。\n"
            "Render のログに詳細が出ていることがあります。"
        )

    if isinstance(exc, RuntimeError):
        text = str(exc)
        if "Google 認証が未設定" in text:
            return (
                "Google のサービスアカウント認証が設定されていません。\n"
                "Render では GOOGLE_SERVICE_ACCOUNT_JSON（JSON 全文）、"
                "または GOOGLE_APPLICATION_CREDENTIALS（ファイルパス）を設定してください。"
            )
        if "GOOGLE_SERVICE_ACCOUNT_JSON が有効な JSON" in text:
            return (
                "GOOGLE_SERVICE_ACCOUNT_JSON が正しい JSON として読めませんでした。\n"
                "改行を除いた1行の JSON にするか、ダッシュボードの値を貼り直してください。"
            )

    if isinstance(exc, FileNotFoundError):
        fn = getattr(exc, "filename", None) or "（パス不明）"
        return f"認証用 JSON ファイルが見つかりません: {fn}"

    return (
        "経理シートへの接続でエラーが出ました。\n"
        "認証・SPREADSHEET_ID・シート名（環境変数 SHEET_*）を確認してください。"
    )
