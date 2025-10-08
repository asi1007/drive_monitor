#!/usr/bin/env python3
"""
Google Drive ファイル処理の単発実行スクリプト
"""
from drive_monitor import DriveMonitor
import logging

def main():
    """メイン実行関数"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('drive_monitor.log'),
            logging.StreamHandler()
        ]
    )

    logger = logging.getLogger(__name__)

    try:
        logger.info("Google Drive ファイル処理を開始します...")
        monitor = DriveMonitor()

        # 一度だけ実行
        monitor.check_and_process_once()
        logger.info("処理完了")

    except Exception as e:
        logger.error(f"システムエラー: {e}")
        raise

if __name__ == "__main__":
    main()