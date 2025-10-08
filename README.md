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

# 3. Cloud Functionsにデプロイ
gcloud functions deploy process_drive_files \
  --runtime python311 \
  --trigger-http \
  --allow-unauthenticated \
  --entry-point process_drive_files \
  --source . \
  --timeout 540s \
  --memory 512MB \
  --set-env-vars GOOGLE_SHEETS_SPREADSHEET_ID=1Dvz3cS9DRGx4woEY0NNypgLPKxLZ55a4j8778YlCFls

# 4. サービスアカウントキーを追加（GCPコンソールから設定）
# または Secret Manager を使用してキーを管理
```

#### Cloud Schedulerで定期実行

```bash
# 5分ごとに実行するスケジュールを作成
gcloud scheduler jobs create http drive-monitor-job \
  --schedule="*/5 * * * *" \
  --uri="https://REGION-PROJECT_ID.cloudfunctions.net/process_drive_files" \
  --http-method=GET \
  --location=asia-northeast1
```

#### 環境変数の設定

デプロイ時に環境変数を設定する場合：

```bash
gcloud functions deploy process_drive_files \
  --set-env-vars GOOGLE_SHEETS_SPREADSHEET_ID=YOUR_SPREADSHEET_ID,GOOGLE_SHEETS_CREDENTIALS_JSON=service_account.json
```

または、Google Cloud コンソールから「環境変数」セクションで設定できます。

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

## ログ

処理ログは`drive_monitor.log`ファイルに記録されます。

## 注意事項

- 処理済みファイルは重複処理を避けるため記録されます
- Google APIの利用制限に注意してください
- サービスアカウントの権限設定を適切に行ってください

## トラブルシューティング

### よくある問題

1. **認証エラー**: サービスアカウントのJSONファイルと権限設定を確認
2. **API制限エラー**: リクエスト頻度を調整
3. **ファイルが見つからない**: フォルダIDとファイル名パターンを確認

### ログの確認

```bash
tail -f drive_monitor.log
```

## ライセンス

このプロジェクトはMITライセンスの下で公開されています。
