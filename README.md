# LIRA（BRANDVOX 経理 AI MVP）

Google スプレッドシートを正とした会計サマリー・入金／支払スケジュール取得、定型文面生成、**OpenAI による自然文回答**、**LINE Webhook 返信**、**Supabase 監査ログ**（任意）を行う REST API です。バックエンドは **Python 3.12+** / **FastAPI**、データ取得は **Google Sheets API v4（サービスアカウント・読み取り専用スコープ）** です。

## 前提

- Google Cloud プロジェクトで **Google Sheets API** を有効化する。
- **サービスアカウント**を作成し、JSON キーをダウンロードする（リポジトリにコミットしない）。
- 対象スプレッドシートを、サービスアカウントのメール（`...@...iam.gserviceaccount.com`）に **編集者** 以上で共有する。

## 手動で必要な作業（チェックリスト）

コードだけでは動きません。次を人の手で済ませてください。

1. **Google Cloud**  
   - プロジェクトを選び、**Google Sheets API** をオンにする。  
   - **サービスアカウント**を作成し、JSON キーを取得する（Git に入れない）。

2. **スプレッドシート共有**  
   - 経理用シートを、上記 SA のメールアドレスに **編集者** で共有する。  
   - タブ名・ヘッダーは `docs/sheet-structure.md` に合わせるか、`.env` の `SHEET_*` を実シート名に合わせる。

3. **ローカル `.env`**  
   - `cp .env.example .env` または `cp env/local.env.example .env`  
   - `GOOGLE_APPLICATION_CREDENTIALS`（ファイルパス）**または** `GOOGLE_SERVICE_ACCOUNT_JSON`（JSON 全文）のどちらかを必ず設定。  
   - `SPREADSHEET_ID` を URL の `/d/` と `/edit` の間の ID にする。

4. **Render でデプロイする場合**  
   - リポジトリルートの `render.yaml` を Blueprint として読み込むか、手動で Web Service を作成。  
   - Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`（`render.yaml` と同じ）  
   - Environment は `env/render.env.example` を参照。**SA JSON は `GOOGLE_SERVICE_ACCOUNT_JSON`**。  
   - **LINE**: Messaging API の Webhook URL に `https://（あなたのサービスURL）/line/webhook` を設定。  
   - デプロイ後の URL を `PUBLIC_APP_URL` に入れると OpenAPI `/docs` のサーバ URL と一致しやすい。

   **ビルドログに `cargo build` や `rustc` が出る場合** … サービスの **言語／ランタイムが Rust** になっています。LIRA は **Python** です。Render の **Settings → Build & Deploy**（または Environment）で次を直してください。
   - **Runtime / Native Environment**: **Python**（バージョンは 3.12 系で可）
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

5. **Supabase（任意）**  
   - Supabase SQL エディタで `docs/supabase.sql` を実行し `lira_audit_log` を作成。  
   - `.env` に `SUPABASE_URL` と **`SUPABASE_SERVICE_ROLE_KEY`**（挿入用。リポジトリに書かない）を設定。  
   - `/ask` や LINE Webhook 成功時に `source` と `detail`（秘密なし）が追記される。

6. **OpenAI（任意）**  
   - `OPENAI_API_KEY` を設定すると `POST /ask` が `mode: "openai"` で自然文 `answer` を返す。失敗時は従来どおり `mode: "rules"`。

7. **LINE（任意）**  
   - `LINE_CHANNEL_SECRET` と `LINE_CHANNEL_ACCESS_TOKEN` を設定。Webhook を本番 URL に向ける。

## 環境変数テンプレート

| ファイル | 用途 |
|----------|------|
| `.env.example` | 汎用テンプレート |
| `env/local.env.example` | ローカル用（ルートに `.env` としてコピー） |
| `env/render.env.example` | Render 用の変数名の例 |

## 環境変数

| 変数 | 必須 | 説明 |
|------|------|------|
| `GOOGLE_APPLICATION_CREDENTIALS` | ローカルでは**推奨** | サービスアカウント JSON の**絶対パス**（`GOOGLE_SERVICE_ACCOUNT_JSON` 未使用時は実質必須） |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Render 等では**推奨** | JSON 全文を 1 変数に格納。設定時はファイルパス不要 |
| `SPREADSHEET_ID` | はい | スプレッドシート URL の `/d/` と `/edit` の間の ID |
| `PUBLIC_APP_URL` | いいえ | 本番 URL（OpenAPI `/docs` の servers。LINE Webhook のベースにも使用） |
| `SUPABASE_URL` | いいえ | 監査ログ用 |
| `SUPABASE_SERVICE_ROLE_KEY` | いいえ | サーバーからの `lira_audit_log` 挿入に推奨（`anon` の代わり） |
| `SUPABASE_ANON_KEY` | いいえ | `service_role` が無い場合のみ（RLS で insert 要設定） |
| `SUPABASE_AUDIT_TABLE` | いいえ | 既定 `lira_audit_log` |
| `OPENAI_API_KEY` | いいえ | 設定時 `/ask` と LINE が自然文優先 |
| `OPENAI_MODEL` | いいえ | 既定 `gpt-4o-mini` |
| `LINE_CHANNEL_SECRET` | いいえ | LINE Webhook 署名検証 |
| `LINE_CHANNEL_ACCESS_TOKEN` | いいえ | 返信 API 用 |
| `SHEET_SUMMARY` | いいえ | 月次サマリーシート名（既定: `月次サマリー`） |
| `SHEET_RECEIVABLES` | いいえ | 入金予定シート名（既定: `入金予定`） |
| `SHEET_PAYABLES` | いいえ | 支払予定シート名（既定: `支払予定`） |
| `HEADER_ROW` | いいえ | ヘッダー行（1 始まり、既定: `1`） |
| `DATA_START_ROW` | いいえ | 将来拡張用（現在は `HEADER_ROW` 直下をデータとみなす） |
| `MAX_DATA_ROWS` | いいえ | 取得末尾行（既定: `5000`） |

`.env.example` をコピーして `.env` を作成してください。

```bash
cp .env.example .env
# .env を編集
```

**テンプレにキーが増えたとき**（pull 後など）、既存の値はそのままに **足りないキーだけ追記**するには:

```bash
python scripts/merge_env.py
```

（実行前に `.env` を `.env.bak` にバックアップします。）

**GCP の JSON を 1 行にしたいとき**（Render の Environment に貼りやすくする）:

```bash
jq -c . /path/to/service-account.json
```

**direnv** を使う場合は `.envrc` に `dotenv` と書けば、ディレクトリに入ったとき自動で `.env` を読み込めます（別途 direnv のインストールが必要）。

## セットアップ

```bash
cd /path/to/LIRA
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 起動

```bash
export GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/to/sa.json
export SPREADSHEET_ID=your_spreadsheet_id
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

ブラウザで `http://127.0.0.1:8000/docs`（OpenAPI UI）を開けます。

## API 概要

| メソッド | パス | 説明 |
|----------|------|------|
| GET | `/health` | 生存確認 |
| GET | `/summary?month=YYYY-MM` | 当月の売上・経費・利益・利益率（`月次サマリー` 行） |
| GET | `/receivables` | 入金予定一覧（`month` / `due_from` / `due_to` で絞り込み可） |
| GET | `/payables` | 支払予定一覧（`open_only` 既定 true） |
| GET | `/unpaid` | 未入金候補 |
| POST | `/reports/monthly` | 月次レポート文（`audience`: `internal` / `client`） |
| POST | `/messages/payment-received` | 入金確認文（任意で `sheet_row_indices`） |
| POST | `/messages/overdue-reminder` | 督促文（任意で `sheet_row_indices`） |
| GET | `/integrations/status` | OpenAI / Supabase / LINE が設定済みか（値は返さない） |
| POST | `/line/webhook` | LINE Messaging API（署名検証後、テキストに返信） |
| POST | `/ask` | OpenAI があれば自然文 `answer` + `structured`、なければ従来のルール結果のみ |

シートの列名・構成は `docs/sheet-structure.md` を参照してください。

## Lint（任意）

```bash
pip install ruff==0.8.6
ruff check app
ruff format app
```

## ターゲットシート（設計用 ID）

開発時の想定例: `https://docs.google.com/spreadsheets/d/1DGEgDH0205d9pjV-ujvk28nmzH34Djh1JtIPELNW4jg/edit`  
実運用では自社の `SPREADSHEET_ID` に差し替えてください。
