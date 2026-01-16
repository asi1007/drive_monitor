# Google Drive 監視・ファイル処理システム

Google Driveに保存された請求書ファイルを自動監視し、ASINと追跡番号をGoogle Sheetsに記録するシステムです。

## 概要

このシステムは以下の機能を提供します：

- Google Driveの指定フォルダを監視
- 新しいファイル（OCS、TW、YP形式）を自動検出
- ファイルからASINと追跡番号を抽出
- Google Sheetsの「invoice」シートに自動記録

## 対応ファイル形式

### 1. OCS形式
- **保存場所**: [統一フォルダ](https://drive.google.com/drive/u/1/folders/1hgAHbzyXZ2mkHen05T3KlWMr152rqO2L)
- **ファイル名**: "OCS"を含む
- **追跡番号**: G2セル
- **ASIN**: G17以降のセル

### 2. TW形式
- **保存場所**: [統一フォルダ](https://drive.google.com/drive/u/1/folders/1hgAHbzyXZ2mkHen05T3KlWMr152rqO2L)
- **ファイル名**: "TW"を含む
- **追跡番号**: A12セル
- **ASIN**: K16以降のセル

### 3. YP形式
- **保存場所**: [統一フォルダ](https://drive.google.com/drive/u/1/folders/1hgAHbzyXZ2mkHen05T3KlWMr152rqO2L)
- **ファイル名**: "YP"を含む
- **ファイル形式**: Excelファイル（.xls, .xlsx）
- **追跡番号**: F12セル
- **ASIN**: J21以降のセル

## セットアップ

### 1. 仮想環境の作成と有効化

```bash
# 仮想環境を作成
python3 -m venv venv

# 仮想環境を有効化
# macOS/Linux:
source venv/bin/activate

# Windows:
# venv\Scripts\activate
```

### 2. 必要なライブラリのインストール

仮想環境を有効化した状態で、依存パッケージをインストール：

```bash
pip install -r requirements.txt
```

### 3. 環境変数の設定

`.env`ファイルを作成し、以下の環境変数を設定してください：

```env
GOOGLE_SHEETS_CREDENTIALS_JSON=service_account.json
GOOGLE_SHEETS_SPREADSHEET_ID=1Dvz3cS9DRGx4woEY0NNypgLPKxLZ55a4j8778YlCFls
```

### 4. Google API認証の設定

1. Google Cloud Consoleでプロジェクトを作成
2. Google Sheets APIとGoogle Drive APIを有効化
3. サービスアカウントを作成し、JSONキーをダウンロード
4. `service_account.json`として保存
5. 対象のGoogle Sheetsにサービスアカウントのメールアドレスを共有設定で追加

## 使用方法

### 単発実行

仮想環境を有効化した状態で実行：

```bash
# 仮想環境を有効化（まだの場合）
source venv/bin/activate

# スクリプト実行
python run_monitor.py
```

### Cloud Functions デプロイ

Google Cloud Functionsにデプロイする手順：

#### 前提条件
- Google Cloud SDKがインストールされていること
- Google Cloudプロジェクトが作成されていること
- 必要なAPIが有効化されていること

#### デプロイ手順

```bash
# 1. Google Cloud にログイン
gcloud auth login

# 2. プロジェクトを設定
gcloud config set project YOUR_PROJECT_ID

# 3. Secret Managerにサービスアカウントキーを保存
gcloud secrets create invoice-service-account \
  --data-file=service_account.json \
  --replication-policy="automatic"

# 4. Cloud Functionsサービスアカウントに権限を付与
gcloud secrets add-iam-policy-binding invoice-service-account \
  --member="serviceAccount:PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# 5. Cloud Build用サービスアカウントに権限を付与
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member=serviceAccount:PROJECT_NUMBER-compute@developer.gserviceaccount.com \
  --role=roles/cloudbuild.builds.builder

# 6. Cloud Functionsにデプロイ（Secret Managerを使用）
gcloud functions deploy process_drive_files \
  --gen2 \
  --runtime python311 \
  --trigger-http \
  --entry-point process_drive_files \
  --source . \
  --region us-central1 \
  --timeout 540s \
  --memory 512MB \
  --set-env-vars GOOGLE_SHEETS_SPREADSHEET_ID=1Dvz3cS9DRGx4woEY0NNypgLPKxLZ55a4j8778YlCFls,GOOGLE_SHEETS_CREDENTIALS_JSON=/secrets/service_account/service_account.json \
  --set-secrets /secrets/service_account/service_account.json=invoice-service-account:latest
```

**注意**: `service_account.json`はSecret Managerで管理されるため、デプロイパッケージに含まれません。

#### Cloud Schedulerで定期実行

```bash
# 1時間ごとに実行するスケジュールを作成（日本時間）
gcloud scheduler jobs create http drive-monitor-job \
  --location=asia-northeast1 \
  --schedule="0 * * * *" \
  --time-zone="Asia/Tokyo" \
  --uri="https://us-central1-YOUR_PROJECT_ID.cloudfunctions.net/process_drive_files" \
  --http-method=GET \
  --oidc-service-account-email=PROJECT_NUMBER-compute@developer.gserviceaccount.com \
  --oidc-token-audience="https://us-central1-YOUR_PROJECT_ID.cloudfunctions.net/process_drive_files"
```

**注意**: 認証が必要なCloud Functionsの場合、`--oidc-service-account-email`と`--oidc-token-audience`を指定してください。

#### Secret Managerを使用するメリット

- **セキュリティ向上**: サービスアカウントキーがコードリポジトリやデプロイパッケージに含まれません
- **管理の簡素化**: キーのローテーションがSecret Manager上で一元管理できます
- **監査**: Secret Managerのアクセスログで誰がいつアクセスしたか追跡できます
- **コード変更不要**: `--set-secrets`オプションでファイルとしてマウントされるため、既存のコードをそのまま使用できます

## ファイル構成

```
├── drive_monitor.py      # メインの監視・処理ロジック
├── main.py              # Cloud Functions用エントリーポイント
├── run_monitor.py       # 単発実行用スクリプト
├── requirements.txt     # 依存関係
├── .env                 # 環境変数設定
├── .gitignore           # Git無視ファイル
├── service_account.json # Google API認証情報
├── venv/                # 仮想環境（.gitignoreで除外）
└── spec/
    ├── drive_monitor.md # 仕様書
    └── n8n.json         # n8nワークフロー設定
```

## 主要機能

### DriveMonitor クラス

- **`__init__()`**: 認証情報とAPIサービスの初期化
- **`check_and_process_once()`**: 一度だけファイルチェックと処理を実行
- **`monitor_continuously()`**: 継続的な監視（開発用）
- **`process_ocs_file()`**: OCS形式ファイルの処理
- **`process_tw_file()`**: TW形式ファイルの処理
- **`process_yp_file()`**: YP形式ファイルの処理
- **`update_sheet()`**: Google Sheetsへのデータ更新

## ログの確認方法

このシステムは実行環境によって異なる方法でログを確認できます。

### ローカル実行時

現在の実装では、ログは**コンソール（標準出力）に出力**されます。

```bash
# 単発実行時はターミナルに直接表示されます
python run_monitor.py

# 全ファイル処理時
python process_all.py
```

**注意**: 現在`drive_monitor.log`ファイルは作成されていません。ファイルに保存したい場合は、下記の「ログをファイルに保存する方法」を参照してください。

### Cloud Functions実行時

GCPのCloud Functionsにデプロイしている場合、Cloud Loggingでログを確認します。

#### 1. gcloudコマンドで確認（推奨）

```bash
# 最新50件のログを表示
gcloud functions logs read process_drive_files --limit 50

# リアルタイムでログを監視（Ctrl+Cで終了）
gcloud functions logs read process_drive_files --limit 50 --follow

# 特定の時間範囲のログを確認
gcloud functions logs read process_drive_files \
  --limit 100 \
  --start-time="2024-01-01T00:00:00Z" \
  --end-time="2024-01-01T23:59:59Z"

# エラーログのみを表示
gcloud functions logs read process_drive_files --limit 50 | grep ERROR
```

#### 2. GCPコンソールで確認

1. [Cloud Functions コンソール](https://console.cloud.google.com/functions/list)にアクセス
2. `process_drive_files`関数を選択
3. 「ログ」タブをクリック
4. または、[Logs Explorer](https://console.cloud.google.com/logs)で詳細なフィルタリングが可能

#### 3. Cloud Schedulerのジョブ実行履歴を確認

```bash
# スケジュールジョブの一覧を表示
gcloud scheduler jobs list

# 特定のジョブの詳細を確認
gcloud scheduler jobs describe drive-monitor-job --location=asia-northeast1
```

#### 4. アプリケーションの標準出力ログを確認

Cloud Functionsで実行されるアプリケーションの詳細なログ（`logger.info()`や`print()`の出力）を確認するには：

**Cloud Loggingで確認（推奨）**

```bash
# 標準出力ログを含む全てのログを表示
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=process-drive-files" \
  --limit=50 \
  --format="table(timestamp,severity,textPayload)" \
  --project=yiwu-automate

# 特定の時間範囲のログを確認（最新の実行を見る）
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=process-drive-files AND timestamp>=\"2025-11-14T23:00:00Z\"" \
  --limit=50 \
  --format="table(timestamp,severity,textPayload)" \
  --project=yiwu-automate

# HTTPリクエストのステータスを確認（処理が成功したか）
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=process-drive-files AND httpRequest.requestUrl=~\".*\"" \
  --limit=20 \
  --format="table(timestamp,httpRequest.status,httpRequest.latency,httpRequest.requestMethod)" \
  --project=yiwu-automate

# エラーのみをフィルタ
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=process-drive-files AND severity>=ERROR" \
  --limit=50 \
  --project=yiwu-automate
```

**Logs Explorerで確認（GUIで詳細確認）**

1. [Logs Explorer](https://console.cloud.google.com/logs)にアクセス
2. 以下のクエリを入力：
   ```
   resource.type="cloud_run_revision"
   resource.labels.service_name="process-drive-files"
   ```
3. 時間範囲を選択して、ログの詳細を確認

**手動で関数を実行してログを確認**

```bash
# 関数を手動で呼び出し
curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  https://us-central1-YOUR_PROJECT_ID.cloudfunctions.net/process_drive_files

# 直後にログを確認
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=process-drive-files" \
  --limit=30 \
  --format="table(timestamp,severity,textPayload)"
```

**ログが見えない場合の対処法**

もしアプリケーションログ（`logger.info()`の出力）が表示されない場合は、`main.py`のロギング設定を確認してください。Cloud Functionsでは、標準出力に出力されたログが自動的にCloud Loggingに記録されます。

`main.py`の設定例：
```python
import logging
import sys

# Cloud Functionsでは標準出力に出力
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout  # 標準出力に出力
)
```

### ログをファイルに保存する方法

ローカル実行時にログをファイルに保存したい場合は、`drive_monitor.py`の21行目を以下のように変更してください：

**変更前:**
```python
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
```

**変更後:**
```python
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('drive_monitor.log'),  # ファイルに出力
        logging.StreamHandler()  # コンソールにも出力
    ]
)
```

変更後は、以下のコマンドでログを確認できます：

```bash
# ログファイルの内容を表示
cat drive_monitor.log

# ログファイルの末尾を表示
tail -f drive_monitor.log

# ログファイルの最新50行を表示
tail -n 50 drive_monitor.log
```

### ログレベルの変更

より詳細なデバッグ情報が必要な場合は、ログレベルを変更できます：

```python
# DEBUGレベルに変更（より詳細な情報）
logging.basicConfig(level=logging.DEBUG, ...)

# WARNINGレベルに変更（警告とエラーのみ）
logging.basicConfig(level=logging.WARNING, ...)
```

## 注意事項

- 処理済みファイルは重複処理を避けるため記録されます
- Google APIの利用制限に注意してください
- サービスアカウントの権限設定を適切に行ってください
- Cloud Functionsのログは90日間保持されます（デフォルト設定）

## トラブルシューティング

### よくある問題

1. **認証エラー**: サービスアカウントのJSONファイルと権限設定を確認
2. **API制限エラー**: リクエスト頻度を調整
3. **ファイルが見つからない**: フォルダIDとファイル名パターンを確認
4. **Cloud Functionsが見つからない**: デプロイされているか確認 (`gcloud functions list`)
5. **ログが表示されない**: 実行履歴がない、または関数名やリージョンが正しいか確認

## ライセンス

このプロジェクトはMITライセンスの下で公開されています。
