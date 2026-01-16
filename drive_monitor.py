"""
Google Drive監視とファイル処理システム
新しいファイルが保存されたときにASINと追跡番号をGoogle Sheetsに記載
"""
import os
import time
import logging
import sys
from datetime import datetime, timedelta
from typing import Optional, Tuple, List, Set
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
# Cloud Functions(gen2)/Cloud Runでは、先に他のハンドラが設定されているとbasicConfigが効かないことがあるため
# force=True で確実に INFO を標準出力へ流す
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout,
    force=True,
)
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
        self.folder_id = "1h6f0-C9S_5Qx70WeVFUcwQ24xoWWDD-O"  # 対象フォルダ

        # 認証とサービス初期化
        self._init_services()

        # 処理済みファイルを記録するセット
        self.processed_files = set()

    @staticmethod
    def _to_rfc3339(dt: datetime) -> str:
        """UTCのdatetimeをDrive APIクエリ用RFC3339へ."""
        # Drive API query expects RFC3339 like 2026-01-16T07:18:11.020266Z
        s = dt.isoformat()
        return s.replace("+00:00", "Z")

    def _list_files(self, query: str, order_by: str) -> List[dict]:
        """Drive files.list をページネーション込みで取得"""
        files: List[dict] = []
        page_token: Optional[str] = None
        while True:
            results = self.drive_service.files().list(
                q=query,
                fields="nextPageToken,files(id, name, createdTime, modifiedTime, mimeType, webViewLink, parents)",
                orderBy=order_by,
                pageToken=page_token,
                pageSize=1000,
            ).execute()
            files.extend(results.get("files", []))
            page_token = results.get("nextPageToken")
            if not page_token:
                break
        return files

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

    def get_folder_name(self, folder_id):
        """フォルダIDからフォルダ名を取得"""
        try:
            folder_info = self.drive_service.files().get(fileId=folder_id, fields="name").execute()
            return folder_info.get('name', '不明')
        except Exception as e:
            logger.warning(f"フォルダ名取得エラー: {e}")
            return '不明'

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
                folder_name = folder_info.get('name', '不明')
                folder_link = f"https://drive.google.com/drive/folders/{folder_id}"
                logger.info("=" * 60)
                logger.info(f"検索対象フォルダ: {folder_name}")
                logger.info(f"   フォルダID: {folder_id}")
                logger.info(f"   フォルダURL: {folder_link}")
                logger.info("=" * 60)
            except Exception as folder_error:
                logger.error(f"フォルダアクセスエラー: {folder_error}")
                return []

            # 時間閾値を計算（UTC基準）
            from datetime import timezone
            now_utc = datetime.now(timezone.utc)
            time_threshold = (now_utc - timedelta(hours=hours)).isoformat().replace('+00:00', 'Z')

            logger.info(f"現在時刻 (UTC): {now_utc.isoformat()}")
            logger.info(f"検索対象時間: {time_threshold} 以降 (過去{hours}時間)")

            # 時間フィルタを適用（modifiedTimeで検索）
            query = f"'{folder_id}' in parents and modifiedTime > '{time_threshold}'"
            logger.info(f"検索クエリ: {query}")

            files = self._list_files(query=query, order_by="modifiedTime desc")
            logger.info(f"条件に一致するファイル数: {len(files)}")
            
            # 各ファイルの情報をログ出力
            if files:
                logger.info("検出されたファイル一覧:")
                for idx, file_info in enumerate(files, 1):
                    filename = file_info.get('name', '不明')
                    file_id = file_info.get('id', '')
                    web_link = file_info.get('webViewLink', '')
                    parents = file_info.get('parents', [])
                    folder_name = self.get_folder_name(parents[0]) if parents else '不明'
                    folder_path = f"/{folder_name}/{filename}"
                    
                    # webViewLinkがない場合はファイルIDから生成
                    if not web_link and file_id:
                        web_link = f"https://drive.google.com/file/d/{file_id}/view"
                    
                    logger.info(f"  [{idx}] {filename}")
                    logger.info(f"      パス: {folder_path}")
                    logger.info(f"      URL: {web_link}")

            return files

        except Exception as e:
            logger.error(f"ファイル取得エラー: {e}")
            return []

    def get_files_by_created_range(self, folder_id: str, start_utc: datetime, end_utc: datetime) -> List[dict]:
        """createdTime で期間指定してファイルを取得（UTC境界）"""
        try:
            # フォルダの存在確認
            try:
                folder_info = self.drive_service.files().get(fileId=folder_id).execute()
                folder_name = folder_info.get("name", "不明")
                folder_link = f"https://drive.google.com/drive/folders/{folder_id}"
                logger.info("=" * 60)
                logger.info(f"検索対象フォルダ（期間指定）: {folder_name}")
                logger.info(f"   フォルダID: {folder_id}")
                logger.info(f"   フォルダURL: {folder_link}")
                logger.info("=" * 60)
            except Exception as folder_error:
                logger.error(f"フォルダアクセスエラー: {folder_error}")
                return []

            start_rfc3339 = self._to_rfc3339(start_utc)
            end_rfc3339 = self._to_rfc3339(end_utc)
            logger.info(f"検索対象期間(createdTime): {start_rfc3339} 以上, {end_rfc3339} 未満")

            query = (
                f"'{folder_id}' in parents "
                f"and createdTime >= '{start_rfc3339}' "
                f"and createdTime < '{end_rfc3339}'"
            )
            logger.info(f"検索クエリ: {query}")

            files = self._list_files(query=query, order_by="createdTime asc")
            logger.info(f"条件に一致するファイル数: {len(files)}")
            return files
        except Exception as e:
            logger.error(f"期間指定ファイル取得エラー: {e}")
            return []

    def get_all_files(self, folder_id):
        """指定されたフォルダから全てのファイルを取得（時間制限なし）"""
        try:
            # デバッグ: フォルダの存在確認
            try:
                folder_info = self.drive_service.files().get(fileId=folder_id).execute()
                folder_name = folder_info.get('name', '不明')
                folder_link = f"https://drive.google.com/drive/folders/{folder_id}"
                logger.info("=" * 60)
                logger.info(f"検索対象フォルダ（全ファイル）: {folder_name}")
                logger.info(f"   フォルダID: {folder_id}")
                logger.info(f"   フォルダURL: {folder_link}")
                logger.info("=" * 60)
            except Exception as folder_error:
                logger.error(f"フォルダアクセスエラー: {folder_error}")
                return []

            # 時間フィルタなしで全ファイルを取得
            query = f"'{folder_id}' in parents"
            logger.info(f"検索クエリ（全ファイル）: {query}")

            files = self._list_files(query=query, order_by="createdTime desc")
            logger.info(f"フォルダ内の全ファイル数: {len(files)}")
            
            # 各ファイルの情報をログ出力
            if files:
                logger.info("全ファイル一覧:")
                for idx, file_info in enumerate(files, 1):
                    filename = file_info.get('name', '不明')
                    file_id = file_info.get('id', '')
                    web_link = file_info.get('webViewLink', '')
                    parents = file_info.get('parents', [])
                    folder_name = self.get_folder_name(parents[0]) if parents else '不明'
                    folder_path = f"/{folder_name}/{filename}"
                    
                    # webViewLinkがない場合はファイルIDから生成
                    if not web_link and file_id:
                        web_link = f"https://drive.google.com/file/d/{file_id}/view"
                    
                    logger.info(f"  [{idx}] {filename}")
                    logger.info(f"      パス: {folder_path}")
                    logger.info(f"      URL: {web_link}")

            return files

        except Exception as e:
            logger.error(f"全ファイル取得エラー: {e}")
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
            return tracking_number, asin_list, None  # OCS/TWは箱数なし

        except Exception as e:
            logger.error(f"Excel処理エラー {filename}: {e}")
            return None, [], None

    def process_ocs_file(self, file_id, filename):
        """OCSファイルを処理してASINと追跡番号を取得（Excelファイルのみ対応）"""
        # Excelファイルのみ処理
        if filename.lower().endswith(('.xls', '.xlsx')):
            return self.process_excel_file(file_id, filename)
        else:
            logger.info(f"ファイル {filename} はExcelファイルではありません")
            return None, [], None

    def process_tw_file(self, file_id, filename):
        """TWファイルを処理してASINと追跡番号を取得（Excelファイルのみ対応）"""
        # Excelファイルのみ処理
        if filename.lower().endswith(('.xls', '.xlsx')):
            return self.process_excel_tw_file(file_id, filename)
        else:
            logger.info(f"ファイル {filename} はExcelファイルではありません")
            return None, [], None

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
            return tracking_number, asin_list, None  # TWは箱数なし

        except Exception as e:
            logger.error(f"TW Excel処理エラー {filename}: {e}")
            return None, [], None

    def process_yp_file(self, file_id, filename):
        """YPファイルを処理してASINと追跡番号、箱数を取得（Excelファイルのみ対応）"""
        # Excelファイルのみ処理
        if filename.lower().endswith(('.xls', '.xlsx')):
            return self.process_excel_yp_file(file_id, filename)
        else:
            logger.info(f"ファイル {filename} はExcelファイルではありません")
            return None, [], None

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

            # 箱数をG8から取得 (Excel G8 = pandas行7, 列6)
            box_count = None
            if len(df) > 7 and len(df.columns) > 6:
                box_value = df.iloc[7, 6]  # G8
                if pd.notna(box_value):
                    box_count = str(box_value).strip()

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

            logger.info(f"YPファイル {filename}: 追跡番号={tracking_number}, 箱数={box_count}, ASIN数={len(asin_list)}")
            return tracking_number, asin_list, box_count

        except Exception as e:
            logger.error(f"YP Excel処理エラー {filename}: {e}")
            return None, [], None

    def _get_existing_file_ids_in_invoice_sheet(self) -> Set[str]:
        """invoiceシートに既に書かれているファイルIDを取得（重複防止）"""
        try:
            invoice_sheet = self.spreadsheet.worksheet("invoice")
        except gspread.WorksheetNotFound:
            return set()

        values = invoice_sheet.get_all_values()
        if len(values) < 2:
            return set()

        # 7列目(G)にファイルIDを格納する想定（ヘッダー含め）
        existing: Set[str] = set()
        for row in values[1:]:
            if len(row) >= 7 and row[6].strip():
                existing.add(row[6].strip())
        return existing

    def write_to_invoice_sheet(self, file_id: str, tracking_number, asin_list, file_type, filename, created_time, box_count=None):
        """invoiceシートにASINと追跡番号、箱数を記載"""
        try:
            # invoiceシートを取得または作成
            try:
                invoice_sheet = self.spreadsheet.worksheet("invoice")
            except gspread.WorksheetNotFound:
                invoice_sheet = self.spreadsheet.add_worksheet(title="invoice", rows=1000, cols=26)
                # ヘッダーを追加
                invoice_sheet.update('A1:G1', [['ファイル名', 'ファイルタイプ', '作成日時', '追跡番号', 'ASIN', '箱数', 'ファイルID']])

            # 既存ファイルIDがあればスキップ（重複防止）
            existing_file_ids = self._get_existing_file_ids_in_invoice_sheet()
            if file_id in existing_file_ids:
                logger.info(f"スキップ: invoiceシートに既に存在するファイルID ({file_id})")
                return

            # 現在の最後の行を取得
            all_values = invoice_sheet.get_all_values()
            next_row = len(all_values) + 1

            # 追跡番号を記載
            if tracking_number:
                invoice_sheet.update(f'A{next_row}:G{next_row}', [[filename, file_type, created_time, tracking_number, '', box_count or '', file_id]])
                next_row += 1

            # ASINリストを記載
            for asin in asin_list:
                invoice_sheet.update(f'A{next_row}:G{next_row}', [[filename, file_type, created_time, tracking_number or '', asin, box_count or '', file_id]])
                next_row += 1

            logger.info(f"invoiceシートに {file_type} ファイル {filename} のデータを記載しました")

        except Exception as e:
            logger.error(f"invoiceシート書き込みエラー: {e}")

    def process_file(self, file_info, skip_processed_check=False):
        """ファイルを処理"""
        file_id = file_info['id']
        filename = file_info['name']
        created_time_utc = file_info.get('createdTime', '')  # 作成日時を取得（UTC）
        web_view_link = file_info.get('webViewLink', '')  # WebリンクURL
        parents = file_info.get('parents', [])  # 親フォルダID
        
        # フォルダパス風の表示を作成
        folder_path = f"/{self.get_folder_name(parents[0]) if parents else '不明'}/{filename}"
        
        # webViewLinkがない場合はファイルIDから生成
        if not web_view_link and file_id:
            web_view_link = f"https://drive.google.com/file/d/{file_id}/view"
        
        # ファイル情報をログに出力
        logger.info("=" * 60)
        logger.info(f"ファイル処理開始: {filename}")
        logger.info(f"パス: {folder_path}")
        logger.info(f"URL: {web_view_link}")
        logger.info(f"ファイルID: {file_id}")
        logger.info("=" * 60)
        
        # UTC時刻を日本時間に変換
        created_time_jst = ''
        if created_time_utc:
            try:
                from datetime import timezone
                # ISO 8601形式の文字列をdatetimeオブジェクトに変換
                dt_utc = datetime.fromisoformat(created_time_utc.replace('Z', '+00:00'))
                # 日本時間（UTC+9）に変換
                jst = timezone(timedelta(hours=9))
                dt_jst = dt_utc.astimezone(jst)
                # 読みやすい形式でフォーマット
                created_time_jst = dt_jst.strftime('%Y-%m-%d %H:%M:%S')
            except Exception as e:
                logger.warning(f"日時変換エラー: {e}")
                created_time_jst = created_time_utc

        # 既に処理済みのファイルはスキップ（skip_processed_check=Trueの場合は無視）
        if not skip_processed_check and file_id in self.processed_files:
            logger.info(f"スキップ: 処理済みファイル")
            return False

        file_type = self.detect_file_type(filename)

        if file_type == "OCS":
            tracking_number, asin_list, box_count = self.process_ocs_file(file_id, filename)
        elif file_type == "TW":
            tracking_number, asin_list, box_count = self.process_tw_file(file_id, filename)
        elif file_type == "YP":
            tracking_number, asin_list, box_count = self.process_yp_file(file_id, filename)
        else:
            logger.info(f"ファイル {filename} はOCS、TW、またはYPファイルではありません")
            return False

        # invoiceシートにデータを記載
        if tracking_number or asin_list:
            self.write_to_invoice_sheet(file_id, tracking_number, asin_list, file_type, filename, created_time_jst, box_count)
            # 処理済みファイルとして記録
            self.processed_files.add(file_id)
            return True

        return False

    def check_and_process_once(self):
        """一度だけファイルをチェックして処理（Cloud Functions用）"""
        logger.info("Google Drive ファイルチェックを開始します...")

        try:
            # フォルダから新しいファイルを取得（過去1時間）
            new_files = self.get_recent_files(self.folder_id, hours=1)

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

    def process_created_range(self, start_utc: datetime, end_utc: datetime) -> Tuple[int, int]:
        """createdTime期間でファイルを取得して処理（重複はシート上のファイルIDで排除）

        Returns:
            (found_count, processed_count)
        """
        files = self.get_files_by_created_range(self.folder_id, start_utc=start_utc, end_utc=end_utc)
        found_count = len(files)
        processed_count = 0
        for file_info in files:
            # 期間指定は「全件対象」の意図が多いので、processed_files（メモリ上）チェックはスキップしつつ
            # シート上のfile_idで重複を防ぐ
            if self.process_file(file_info, skip_processed_check=True):
                processed_count += 1
        logger.info(f"期間指定処理完了: 検出={found_count}, 処理={processed_count}")
        return found_count, processed_count

    def process_all_files(self, min_prefix=None):
        """フォルダ内の全てのファイルを処理（手動実行用）
        
        Args:
            min_prefix: ファイル名の先頭2文字が数字の場合、この値以上のファイルのみ処理
                       例: min_prefix=50 の場合、50, 51, 52... で始まるファイルのみ処理
        """
        if min_prefix is not None:
            logger.info(f"Google Drive 全ファイル処理を開始します（先頭2文字が{min_prefix:02d}以上のファイルのみ）...")
        else:
            logger.info("Google Drive 全ファイル処理を開始します...")

        try:
            # フォルダから全ファイルを取得（時間制限なし）
            all_files = self.get_all_files(self.folder_id)

            if not all_files:
                logger.info("フォルダ内にファイルが見つかりませんでした")
                return

            # 各ファイルを処理（処理済みチェックをスキップ）
            processed_count = 0
            skipped_count = 0
            for file_info in all_files:
                filename = file_info.get('name', '')
                
                # min_prefixが指定されている場合、ファイル名の先頭2文字をチェック
                if min_prefix is not None:
                    # ファイル名の先頭2文字を取得
                    prefix = filename[:2]
                    # 数字かどうか確認
                    if prefix.isdigit():
                        prefix_num = int(prefix)
                        if prefix_num < min_prefix:
                            logger.info(f"スキップ: {filename} (先頭2文字: {prefix_num} < {min_prefix})")
                            skipped_count += 1
                            continue
                    else:
                        logger.info(f"スキップ: {filename} (先頭2文字が数字ではない)")
                        skipped_count += 1
                        continue
                
                if self.process_file(file_info, skip_processed_check=True):
                    processed_count += 1

            logger.info(f"全ファイル処理完了: {processed_count}個のファイルを処理しました")
            if skipped_count > 0:
                logger.info(f"スキップしたファイル数: {skipped_count}個")

        except Exception as e:
            logger.error(f"全ファイル処理エラー: {e}")
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

def process_all_files_main(min_prefix=None):
    """全ファイル処理用のメイン関数（手動実行用）
    
    Args:
        min_prefix: ファイル名の先頭2文字が数字の場合、この値以上のファイルのみ処理
    """
    try:
        monitor = DriveMonitor()
        monitor.process_all_files(min_prefix=min_prefix)
        return "全ファイル処理完了"
    except Exception as e:
        logger.error(f"全ファイル処理実行エラー: {e}")
        raise

def cloud_function_entry(_request):
    """Cloud Functions エントリーポイント"""
    return main()

if __name__ == "__main__":
    main()