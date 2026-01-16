"""
全ファイル処理スクリプト
指定フォルダ内の全てのファイルを処理します（処理済みファイルも含む）

使い方:
  python process_all.py              # 全ファイルを処理
  python process_all.py 50           # 先頭2文字が50以上のファイルのみ処理
  python process_all.py --min 50     # 同上
"""
import sys
from drive_monitor import process_all_files_main

if __name__ == "__main__":
    min_prefix = None
    
    # コマンドライン引数を解析
    if len(sys.argv) > 1:
        try:
            # --min オプションを処理
            if sys.argv[1] == "--min" and len(sys.argv) > 2:
                min_prefix = int(sys.argv[2])
            else:
                min_prefix = int(sys.argv[1])
            
            if min_prefix < 0 or min_prefix > 99:
                print("エラー: 数値は0-99の範囲で指定してください")
                sys.exit(1)
                
        except ValueError:
            print(f"エラー: 無効な引数 '{sys.argv[1]}'")
            print(__doc__)
            sys.exit(1)
    
    print("=" * 60)
    if min_prefix is not None:
        print(f"Google Drive 全ファイル処理を開始します（先頭2文字が{min_prefix:02d}以上のファイルのみ）")
    else:
        print("Google Drive 全ファイル処理を開始します")
    print("=" * 60)
    
    result = process_all_files_main(min_prefix=min_prefix)
    
    print("=" * 60)
    print(f"結果: {result}")
    print("=" * 60)

