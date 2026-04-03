"""
main.py - タロット占い動画ボットのメインエントリーポイント。

使い方:
    python main.py --test --card A          # 動作確認（アップロードなし）
    python main.py --all                    # 今日の3カードを本番実行
    python main.py --card A                 # カードAのみ
    python main.py --card A --date 2025-01-01  # 指定日で実行
"""

from __future__ import annotations

import argparse
import os
import sys
import traceback
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv

from config import CARD_CHOICES
from generate_fortune import generate_all_fortunes, get_fortune_for_card, load_fortunes
from generate_video import generate_video
from upload_youtube import build_youtube_client, upload_video

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

JST = timezone(timedelta(hours=9))


def _today_jst() -> str:
    return datetime.now(JST).strftime("%Y-%m-%d")


def _ensure_fortunes(date: str) -> None:
    try:
        load_fortunes(date)
        print(f"✅ 運勢データ読み込み済み: output/fortune_{date}.json")
    except FileNotFoundError:
        print("📄 運勢データがありません。生成します...")
        generate_all_fortunes(date)


def process_card(
    card: dict,
    date: str,
    test_mode: bool,
    youtube=None,
) -> bool:
    """1カード分の処理（運勢取得 → 動画生成 → アップロード）を行う。"""
    label = card["label"]

    fortune = get_fortune_for_card(date, label)
    if fortune is None:
        print(f"❌ カード{label}: 運勢データが見つかりません（スキップ）")
        return False

    try:
        video_path = generate_video(fortune, card["slug"], date)
    except Exception as e:
        print(f"❌ カード{label}: 動画生成失敗: {e}")
        traceback.print_exc()
        return False

    if test_mode:
        print(f"🧪 テストモード: アップロードをスキップ ({video_path})")
        return True

    try:
        upload_video(youtube, video_path, fortune, date)
    except Exception as e:
        print(f"❌ カード{label}: アップロード失敗: {e}")
        traceback.print_exc()
        return False

    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="タロット占い動画ボット",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python main.py --test --card A          動作確認（アップロードなし）
  python main.py --all                    今日の3カードを本番実行
  python main.py --card A                 カードAのみ本番実行
  python main.py --card A --date 2025-01-01  指定日で実行
        """,
    )
    parser.add_argument("--all",  action="store_true", help="全3カードを処理")
    parser.add_argument("--card", help="特定のカードのみ処理（例: A）")
    parser.add_argument("--test", action="store_true", help="動画生成まで（アップロードしない）")
    parser.add_argument("--date", default=_today_jst(), help="日付 YYYY-MM-DD（デフォルト: 今日）")
    args = parser.parse_args()

    if not args.all and not args.card:
        parser.print_help()
        sys.exit(1)

    date = args.date
    print(f"📅 処理日: {date}")
    print(f"🧪 テストモード: {'ON' if args.test else 'OFF'}")

    if args.card:
        card = next((c for c in CARD_CHOICES if c["label"] == args.card.upper()), None)
        if card is None:
            labels = ", ".join(c["label"] for c in CARD_CHOICES)
            print(f"❌ カードラベルが不正です: {args.card}\n使用可能: {labels}")
            sys.exit(1)
        targets = [card]
    else:
        targets = list(CARD_CHOICES)
        labels_str = ", ".join(c["name"] for c in targets)
        print(f"🎯 本日の対象: {labels_str}")

    _ensure_fortunes(date)

    youtube = None
    if not args.test:
        print("🔑 YouTube API 認証中...")
        try:
            youtube = build_youtube_client()
        except Exception as e:
            print(f"❌ YouTube 認証失敗: {e}")
            traceback.print_exc()
            print("💡 先に python upload_youtube.py --auth を実行してください")
            sys.exit(1)

    success = 0
    failed  = 0
    for i, card in enumerate(targets):
        print(f"\n[{i + 1}/{len(targets)}] カード{card['label']} を処理中...")
        ok = process_card(card, date, args.test, youtube)
        if ok:
            success += 1
        else:
            failed += 1

    print(f"\n{'=' * 40}")
    print(f"✅ 完了  成功: {success}  失敗: {failed}")
    print(f"{'=' * 40}")

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
