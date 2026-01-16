"""
Cloud Functions用のエントリーポイント
"""
import functions_framework
import logging
import sys

# Cloud Functions(gen2)/Cloud Runでは、先に他のハンドラが設定されているとbasicConfigが効かないことがあるため
# force=True で確実に INFO を標準出力へ流す
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout,
    force=True,
)

from drive_monitor import DriveMonitor  # noqa: E402

# ログ設定
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

        # 期間指定（createdTime基準）: ?mode=created_range&from=2025-12-01&to=2026-02-01
        mode = (request.args.get("mode") if request.args else None) or ""
        if mode == "created_range":
            from_date = request.args.get("from") if request.args else None
            to_date = request.args.get("to") if request.args else None
            if not from_date or not to_date:
                return {"status": "error", "message": "mode=created_range の場合は from/to (YYYY-MM-DD) が必要です"}, 400

            from datetime import datetime, timezone, timedelta
            # JST 00:00 を境界にしたいので、JSTの00:00をUTCに変換して検索
            jst = timezone(timedelta(hours=9))
            start_utc = datetime.fromisoformat(from_date).replace(tzinfo=jst).astimezone(timezone.utc)
            end_utc = datetime.fromisoformat(to_date).replace(tzinfo=jst).astimezone(timezone.utc)

            found, processed = monitor.process_created_range(start_utc=start_utc, end_utc=end_utc)
            response = {
                "status": "success",
                "message": "期間指定のファイル処理が完了しました",
                "mode": mode,
                "found": found,
                "processed": processed,
                "from": from_date,
                "to": to_date,
            }
        else:
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