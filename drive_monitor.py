"""
Google Drive監視とファイル処理システム
新しいファイルが保存されたときにASINと追跡番号をGoogle Sheetsに記載
"""
import os
import time
import logging
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from dotenv import load_dotenv
import pandas as pd
import io

# 環境変数を読み込み
load_dotenv()

# ログ設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DriveMonitor:
    """Google Drive監視とファイル処理クラス"""

    def __init__(self):
        # 認証情報
        self.credentials_file = os.environ.get("GOOGLE_SHEETS_CREDENTIALS_JSON", "service_account.json")
        self.spreadsheet_id = os.environ.get("GOOGLE_SHEETS_SPREADSHEET_ID", "1Dvz3cS9DRGx4woEY0NNypgLPKxLZ55a4j8778YlCFls")

        # Google APIのスコープ
        self.scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive.readonly',
        ]

        # フォルダID（URLから抽出）
        self.folder_id = "1hgAHbzyXZ2mkHen05T3KlWMr152rqO2L"  # 統一フォルダ

        # 認証とサービス初期化
        self._init_services()

        # 処理済みファイルを記録するセット
        self.processed_files = set()

    def _init_services(self):
        """Google APIサービスを初期化"""
        try:
            creds = Credentials.from_service_account_file(self.credentials_file, scopes=self.scopes)

            # Google Sheets API
            self.sheets_client = gspread.authorize(creds)
            self.spreadsheet = self.sheets_client.open_by_key(self.spreadsheet_id)

            # Google Drive API
            self.drive_service = build('drive', 'v3', credentials=creds)

            logger.info("Google APIサービスを初期化しました")
        except Exception as e:
            logger.error(f"APIサービス初期化エラー: {e}")
            raise

    def detect_file_type(self, filename):
        """ファイル名からOCS、TW、またはYPを検出"""
        filename_upper = filename.upper()
        if "OCS" in filename_upper:
            return "OCS"
        elif "TW" in filename_upper:
            return "TW"
        elif "YP" in filename_upper:
            return "YP"
        return None

    def get_recent_files(self, folder_id, hours=24):
        """指定されたフォルダから最近のファイルを取得"""
        try:
            # デバッグ: フォルダの存在確認
            try:
                folder_info = self.drive_service.files().get(fileId=folder_id).execute()
                logger.info(f"フォルダ確認: {folder_info.get('name')} (ID: {folder_id})")
            except Exception as folder_error:
                logger.error(f"フォルダアクセスエラー: {folder_error}")
                return []

            # 時間閾値を計算（UTC基準）
            from datetime import timezone
            now_utc = datetime.now(timezone.utc)
            time_threshold = (now_utc - timedelta(hours=hours)).isoformat().replace('+00:00', 'Z')

            logger.info(f"現在時刻 (UTC): {now_utc.isoformat()}")
            logger.info(f"検索対象時間: {time_threshold} 以降 (過去{hours}時間)")

            # 時間フィルタを適用
            query = f"'{folder_id}' in parents and createdTime > '{time_threshold}'"
            logger.info(f"検索クエリ: {query}")

            results = self.drive_service.files().list(
                q=query,
                fields="files(id, name, createdTime, mimeType)",
                orderBy="createdTime desc"
            ).execute()

            files = results.get('files', [])
            logger.info(f"条件に一致するファイル数: {len(files)}")

            return files

        except Exception as e:
            logger.error(f"ファイル取得エラー: {e}")
            return []

    def process_excel_file(self, file_id, filename):
        """Excelファイルをダウンロードしてpandasで処理"""
        try:
            # ファイルをダウンロード
            request = self.drive_service.files().get_media(fileId=file_id)
            file_content = io.BytesIO()
            downloader = MediaIoBaseDownload(file_content, request)

            done = False
            while done is False:
                status, done = downloader.next_chunk()

            file_content.seek(0)

            # pandasでExcelファイルを読み込み（ヘッダーなし）
            df = pd.read_excel(file_content, engine='openpyxl', header=None)
            print(df.head())

            # 追跡番号をG2から取得 (Excel G2 = pandas行1, 列6)
            tracking_number = None
            if len(df) > 1 and len(df.columns) > 6:
                tracking_value = df.iloc[1, 6]  # G2
                if pd.notna(tracking_value):
                    tracking_number = str(tracking_value).strip()

            # ASINをD17以降から取得 (Excel D17 = pandas行16, 列3)
            asin_list = []
            if len(df.columns) > 3:
                for i in range(16, len(df)):  # Excel 17行目以降 = pandas 16以降
                    if i < len(df):
                        asin_value = df.iloc[i, 3]  # D列 = 列3
                        if pd.notna(asin_value) and str(asin_value).strip():
                            asin_list.append(str(asin_value).strip())
                        else:
                            break

            logger.info(f"Excelファイル {filename}: 追跡番号={tracking_number}, ASIN数={len(asin_list)}")
            return tracking_number, asin_list

        except Exception as e:
            logger.error(f"Excel処理エラー {filename}: {e}")
            return None, []

    def process_ocs_file(self, file_id, filename):
        """OCSファイルを処理してASINと追跡番号を取得（Excelファイルのみ対応）"""
        # Excelファイルのみ処理
        if filename.lower().endswith(('.xls', '.xlsx')):
            return self.process_excel_file(file_id, filename)
        else:
            logger.info(f"ファイル {filename} はExcelファイルではありません")
            return None, []

    def process_tw_file(self, file_id, filename):
        """TWファイルを処理してASINと追跡番号を取得（Excelファイルのみ対応）"""
        # Excelファイルのみ処理
        if filename.lower().endswith(('.xls', '.xlsx')):
            return self.process_excel_tw_file(file_id, filename)
        else:
            logger.info(f"ファイル {filename} はExcelファイルではありません")
            return None, []

    def process_excel_tw_file(self, file_id, filename):
        """TWのExcelファイルをダウンロードしてpandasで処理"""
        try:
            # ファイルをダウンロード
            request = self.drive_service.files().get_media(fileId=file_id)
            file_content = io.BytesIO()
            downloader = MediaIoBaseDownload(file_content, request)

            done = False
            while done is False:
                status, done = downloader.next_chunk()

            file_content.seek(0)

            # pandasでExcelファイルを読み込み（ヘッダーなし）
            df = pd.read_excel(file_content, engine='openpyxl', header=None)

            # 追跡番号をA12から取得 (Excel A12 = pandas行11, 列0)
            tracking_number = None
            if len(df) > 11 and len(df.columns) > 0:
                tracking_value = df.iloc[11, 0]  # A12
                if pd.notna(tracking_value):
                    tracking_number = str(tracking_value).strip()

            # ASINをK16以降から取得 (Excel K16 = pandas行15, 列10)
            asin_list = []
            if len(df.columns) > 10:  # K列 = 列10
                for i in range(15, len(df)):  # Excel 16行目以降 = pandas 15以降
                    if i < len(df):
                        asin_value = df.iloc[i, 10]  # K列 = 列10
                        if pd.notna(asin_value) and str(asin_value).strip():
                            asin_list.append(str(asin_value).strip())
                        else:
                            break

            logger.info(f"TWファイル {filename}: 追跡番号={tracking_number}, ASIN数={len(asin_list)}")
            return tracking_number, asin_list

        except Exception as e:
            logger.error(f"TW Excel処理エラー {filename}: {e}")
            return None, []

    def process_yp_file(self, file_id, filename):
        """YPファイルを処理してASINと追跡番号を取得（Excelファイルのみ対応）"""
        # Excelファイルのみ処理
        if filename.lower().endswith(('.xls', '.xlsx')):
            return self.process_excel_yp_file(file_id, filename)
        else:
            logger.info(f"ファイル {filename} はExcelファイルではありません")
            return None, []

    def process_excel_yp_file(self, file_id, filename):
        """YPのExcelファイルをダウンロードしてpandasで処理"""
        try:
            # ファイルをダウンロード
            request = self.drive_service.files().get_media(fileId=file_id)
            file_content = io.BytesIO()
            downloader = MediaIoBaseDownload(file_content, request)

            done = False
            while done is False:
                _, done = downloader.next_chunk()

            file_content.seek(0)

            # pandasでExcelファイルを読み込み（ヘッダーなし）
            df = pd.read_excel(file_content, engine='openpyxl', header=None)

            # 追跡番号をF12から取得 (Excel F12 = pandas行11, 列5)
            tracking_number = None
            if len(df) > 11 and len(df.columns) > 5:
                tracking_value = df.iloc[11, 5]  # F12
                if pd.notna(tracking_value):
                    tracking_number = str(tracking_value).strip()

            # ASINをJ21以降から取得 (Excel J21 = pandas行20, 列9)
            asin_list = []
            if len(df.columns) > 9:  # J列 = 列9
                for i in range(20, len(df)):  # Excel 21行目以降 = pandas 20以降
                    if i < len(df):
                        asin_value = df.iloc[i, 9]  # J列 = 列9
                        if pd.notna(asin_value) and str(asin_value).strip():
                            asin_list.append(str(asin_value).strip())
                        else:
                            break

            logger.info(f"YPファイル {filename}: 追跡番号={tracking_number}, ASIN数={len(asin_list)}")
            return tracking_number, asin_list

        except Exception as e:
            logger.error(f"YP Excel処理エラー {filename}: {e}")
            return None, []

    def write_to_invoice_sheet(self, tracking_number, asin_list, file_type, filename):
        """invoiceシートにASINと追跡番号を記載"""
        try:
            # invoiceシートを取得または作成
            try:
                invoice_sheet = self.spreadsheet.worksheet("invoice")
            except gspread.WorksheetNotFound:
                invoice_sheet = self.spreadsheet.add_worksheet(title="invoice", rows=1000, cols=26)
                # ヘッダーを追加
                invoice_sheet.update('A1:D1', [['ファイル名', 'ファイルタイプ', '追跡番号', 'ASIN']])

            # 現在の最後の行を取得
            all_values = invoice_sheet.get_all_values()
            next_row = len(all_values) + 1

            # 追跡番号を記載
            if tracking_number:
                invoice_sheet.update(f'A{next_row}:C{next_row}', [[filename, file_type, tracking_number]])
                next_row += 1

            # ASINリストを記載
            for asin in asin_list:
                invoice_sheet.update(f'A{next_row}:D{next_row}', [[filename, file_type, tracking_number or '', asin]])
                next_row += 1

            logger.info(f"invoiceシートに {file_type} ファイル {filename} のデータを記載しました")

        except Exception as e:
            logger.error(f"invoiceシート書き込みエラー: {e}")

    def process_file(self, file_info):
        """ファイルを処理"""
        file_id = file_info['id']
        filename = file_info['name']

        # 既に処理済みのファイルはスキップ
        if file_id in self.processed_files:
            return False

        file_type = self.detect_file_type(filename)

        if file_type == "OCS":
            tracking_number, asin_list = self.process_ocs_file(file_id, filename)
        elif file_type == "TW":
            tracking_number, asin_list = self.process_tw_file(file_id, filename)
        elif file_type == "YP":
            tracking_number, asin_list = self.process_yp_file(file_id, filename)
        else:
            logger.info(f"ファイル {filename} はOCS、TW、またはYPファイルではありません")
            return False

        # invoiceシートにデータを記載
        if tracking_number or asin_list:
            self.write_to_invoice_sheet(tracking_number, asin_list, file_type, filename)
            # 処理済みファイルとして記録
            self.processed_files.add(file_id)
            return True

        return False

    def check_and_process_once(self):
        """一度だけファイルをチェックして処理（Cloud Functions用）"""
        logger.info("Google Drive ファイルチェックを開始します...")

        try:
            # OCSフォルダから新しいファイルを取得（過去5分間）
            new_files = self.get_recent_files(self.folder_id, hours=0.084)  # 5分 = 0.084時間

            if not new_files:
                logger.info("新しいファイルは見つかりませんでした")
                return

            # 各ファイルを処理
            processed_count = 0
            for file_info in new_files:
                if self.process_file(file_info):
                    processed_count += 1

            logger.info(f"処理完了: {processed_count}個のファイルを処理しました")

        except Exception as e:
            logger.error(f"ファイル処理エラー: {e}")
            raise

def main():
    """メイン関数（Cloud Functions対応）"""
    try:
        monitor = DriveMonitor()
        monitor.check_and_process_once()
        return "処理完了"
    except Exception as e:
        logger.error(f"システム実行エラー: {e}")
        raise

def cloud_function_entry(_request):
    """Cloud Functions エントリーポイント"""
    return main()

if __name__ == "__main__":
    main()