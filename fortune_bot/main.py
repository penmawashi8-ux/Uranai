"""
main.py - 占い動画ボットのメインエントリーポイント。

使い方:
    python main.py --test --sign おひつじ座          # 動作確認（アップロードなし）
    python main.py --all                              # 今日の6星座を本番実行
    python main.py --sign おひつじ座                 # 特定星座のみ
    python main.py --sign おひつじ座 --date 2025-01-01  # 指定日で実行
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv

from config import ZODIAC_LIST
from generate_fortune import generate_all_fortunes, get_fortune_for_sign, load_fortunes
from generate_video import generate_video
from upload_youtube import build_youtube_client, upload_video

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

JST = timezone(timedelta(hours=9))


# ---------------------------------------------------------------------------
# ユーティリティ
# ---------------------------------------------------------------------------

def _today_jst() -> str:
    """JST の今日の日付を YYYY-MM-DD 形式で返す。"""
    return datetime.now(JST).strftime("%Y-%m-%d")


def _signs_for_today(date: str) -> list[dict]:
    """今日処理する6星座を返す（奇数日/偶数日で交互）。

    Args:
        date: 日付文字列（YYYY-MM-DD）。

    Returns:
        ZODIAC_LIST の6要素のサブリスト。
    """
    day = int(date.split("-")[2])
    half = len(ZODIAC_LIST) // 2
    return ZODIAC_LIST[:half] if day % 2 == 1 else ZODIAC_LIST[half:]


def _ensure_fortunes(date: str) -> None:
    """運勢データがなければ生成する。

    Args:
        date: 日付文字列（YYYY-MM-DD）。
    """
    try:
        load_fortunes(date)
        print(f"✅ 運勢データ読み込み済み: output/fortune_{date}.json")
    except FileNotFoundError:
        print(f"📄 運勢データがありません。生成します...")
        generate_all_fortunes(date)


# ---------------------------------------------------------------------------
# 処理関数
# ---------------------------------------------------------------------------

def process_sign(
    zodiac: dict,
    date: str,
    test_mode: bool,
    youtube=None,
) -> bool:
    """1星座分の処理（運勢取得 → 動画生成 → アップロード）を行う。

    Args:
        zodiac:    ZODIAC_LIST の1要素。
        date:      日付文字列（YYYY-MM-DD）。
        test_mode: True の場合はアップロードしない。
        youtube:   YouTube API クライアント（test_mode=False 時に必要）。

    Returns:
        成功した場合 True、失敗した場合 False。
    """
    sign_name = zodiac["name"]

    # 運勢データ取得
    fortune = get_fortune_for_sign(date, sign_name)
    if fortune is None:
        print(f"❌ {sign_name}: 運勢データが見つかりません（スキップ）")
        return False

    # 動画生成
    try:
        video_path = generate_video(fortune, zodiac["slug"], date)
    except Exception as e:
        print(f"❌ {sign_name}: 動画生成失敗: {e}")
        return False

    if test_mode:
        print(f"🧪 テストモード: アップロードをスキップ ({video_path})")
        return True

    # アップロード
    try:
        upload_video(youtube, video_path, fortune, date)
    except Exception as e:
        print(f"❌ {sign_name}: アップロード失敗: {e}")
        return False

    return True


# ---------------------------------------------------------------------------
# CLI エントリーポイント
# ---------------------------------------------------------------------------

def main() -> None:
    """コマンドライン引数を解析してメイン処理を実行する。"""
    parser = argparse.ArgumentParser(
        description="占い動画ボット",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python main.py --test --sign おひつじ座          動作確認（アップロードなし）
  python main.py --all                              今日の6星座を本番実行
  python main.py --sign おひつじ座                 特定星座のみ本番実行
  python main.py --sign おひつじ座 --date 2025-01-01  指定日で実行
        """,
    )
    parser.add_argument("--all",  action="store_true", help="今日の6星座を処理（奇数/偶数日で自動振り分け）")
    parser.add_argument("--sign", help="特定の星座のみ処理（例: おひつじ座）")
    parser.add_argument("--test", action="store_true", help="動画生成まで（アップロードしない）")
    parser.add_argument("--date", default=_today_jst(), help="日付 YYYY-MM-DD（デフォルト: 今日）")
    args = parser.parse_args()

    if not args.all and not args.sign:
        parser.print_help()
        sys.exit(1)

    date = args.date
    print(f"📅 処理日: {date}")
    print(f"🧪 テストモード: {'ON' if args.test else 'OFF'}")

    # 処理対象の星座を決定
    if args.sign:
        zodiac = next((z for z in ZODIAC_LIST if z["name"] == args.sign), None)
        if zodiac is None:
            names = ", ".join(z["name"] for z in ZODIAC_LIST)
            print(f"❌ 星座名が不正です: {args.sign}\n使用可能: {names}")
            sys.exit(1)
        targets = [zodiac]
    else:  # --all
        targets = _signs_for_today(date)
        names_str = ", ".join(z["name"] for z in targets)
        print(f"🎯 本日の対象: {names_str}")

    # 運勢データの準備
    _ensure_fortunes(date)

    # YouTube クライアントの準備（テストモードでなければ）
    youtube = None
    if not args.test:
        print("🔑 YouTube API 認証中...")
        try:
            youtube = build_youtube_client()
        except Exception as e:
            print(f"❌ YouTube 認証失敗: {e}")
            print("💡 先に python upload_youtube.py --auth を実行してください")
            sys.exit(1)

    # 各星座を処理
    success = 0
    failed  = 0
    for i, zodiac in enumerate(targets):
        print(f"\n[{i + 1}/{len(targets)}] {zodiac['name']} を処理中...")
        ok = process_sign(zodiac, date, args.test, youtube)
        if ok:
            success += 1
        else:
            failed += 1

    # サマリー
    print(f"\n{'=' * 40}")
    print(f"✅ 完了  成功: {success}  失敗: {failed}")
    print(f"{'=' * 40}")

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
