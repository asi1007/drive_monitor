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

### 1. 必要なライブラリのインストール

```bash
pip install -r requirements.txt
```

### 2. 環境変数の設定

`.env`ファイルを作成し、以下の環境変数を設定してください：

```env
GOOGLE_SHEETS_CREDENTIALS_JSON=service_account.json
GOOGLE_SHEETS_SPREADSHEET_ID=1Dvz3cS9DRGx4woEY0NNypgLPKxLZ55a4j8778YlCFls
```

### 3. Google API認証の設定

1. Google Cloud Consoleでプロジェクトを作成
2. Google Sheets APIとGoogle Drive APIを有効化
3. サービスアカウントを作成し、JSONキーをダウンロード
4. `service_account.json`として保存
5. 対象のGoogle Sheetsにサービスアカウントのメールアドレスを共有設定で追加

## 使用方法

### 単発実行

```bash
python run_monitor.py
```

### Cloud Functions デプロイ

```bash
# Cloud Functions用のエントリーポイント
# main.py を使用してデプロイ
```

## ファイル構成

```
├── drive_monitor.py      # メインの監視・処理ロジック
├── main.py              # Cloud Functions用エントリーポイント
├── run_monitor.py       # 単発実行用スクリプト
├── requirements.txt     # 依存関係
├── .env                 # 環境変数設定
├── service_account.json # Google API認証情報
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
