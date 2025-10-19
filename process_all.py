"""
全ファイル処理スクリプト
指定フォルダ内の全てのファイルを処理します（処理済みファイルも含む）
"""
from drive_monitor import process_all_files_main

if __name__ == "__main__":
    print("=" * 60)
    print("Google Drive 全ファイル処理を開始します")
    print("=" * 60)
    
    result = process_all_files_main()
    
    print("=" * 60)
    print(f"結果: {result}")
    print("=" * 60)

