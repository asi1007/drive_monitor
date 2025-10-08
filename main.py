"""
Cloud Functions用のエントリーポイント
"""
import functions_framework
from drive_monitor import DriveMonitor
import logging

# ログ設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@functions_framework.http
def process_drive_files(request):
    """
    HTTP Cloud Function エントリーポイント
    Google Drive の新しいファイルをチェックしてASIN/追跡番号を処理
    """
    try:
        logger.info("Cloud Function: Google Drive ファイル処理を開始")

        monitor = DriveMonitor()
        monitor.check_and_process_once()

        response = {
            "status": "success",
            "message": "ファイル処理が完了しました"
        }

        logger.info("Cloud Function: 処理完了")
        return response

    except Exception as e:
        logger.error(f"Cloud Function エラー: {e}")
        return {
            "status": "error",
            "message": f"処理中にエラーが発生しました: {str(e)}"
        }, 500