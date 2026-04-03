"""
scheduler.py - APScheduler で占い動画の生成・アップロードを自動実行する。

毎朝 6:00 JST: 全3カードの運勢テキストを一括生成
毎朝 6:30〜  : 3カードを5分おきにアップロード

使い方:
    python scheduler.py          # デーモンとして常駐起動
    python scheduler.py --once   # 今すぐ1回だけ生成＋アップロードを実行
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

from config import CARD_CHOICES, LOGS_DIR, YOUTUBE_MAX_UPLOADS_PER_DAY
from generate_fortune import generate_all_fortunes, get_fortune_for_card
from generate_video import generate_video
from upload_youtube import build_youtube_client, upload_video

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

JST = timezone(timedelta(hours=9))

# ---------------------------------------------------------------------------
# ログ設定
# ---------------------------------------------------------------------------

def _setup_logger(date: str) -> logging.Logger:
    """日付付きログファイルにも出力するロガーを設定する。

    Args:
        date: 日付文字列（YYYY-MM-DD）。

    Returns:
        設定済みの Logger。
    """
    os.makedirs(LOGS_DIR, exist_ok=True)
    log_path = os.path.join(LOGS_DIR, f"{date}.log")

    logger = logging.getLogger("scheduler")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        fmt = logging.Formatter("[%(asctime)s JST] %(levelname)s %(message)s",
                                datefmt="%Y-%m-%d %H:%M:%S")

        fh = logging.FileHandler(log_path, encoding="utf-8")
        fh.setFormatter(fmt)

        ch = logging.StreamHandler()
        ch.setFormatter(fmt)

        logger.addHandler(fh)
        logger.addHandler(ch)

    return logger


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# スケジュールジョブ
# ---------------------------------------------------------------------------

def job_generate_fortunes() -> None:
    """毎朝 6:00 JST: 全3カードの運勢テキストを一括生成する。"""
    date = datetime.now(JST).strftime("%Y-%m-%d")
    logger = _setup_logger(date)
    logger.info("=== 運勢テキスト生成 開始 ===")
    try:
        generate_all_fortunes(date)
        logger.info("=== 運勢テキスト生成 完了 ===")
    except Exception as e:
        logger.error(f"運勢テキスト生成 失敗: {e}", exc_info=True)


def _upload_with_retry(
    youtube,
    card: dict,
    date: str,
    logger: logging.Logger,
    max_retries: int = 3,
    retry_wait: int = 30,
) -> bool:
    """動画生成＋アップロードをリトライ付きで実行する。"""
    for attempt in range(1, max_retries + 1):
        try:
            fortune = get_fortune_for_card(date, card["label"])
            if fortune is None:
                logger.warning(f"カード{card['label']}: 運勢データなし（スキップ）")
                return False

            video_path = generate_video(fortune, card["slug"], date)
            video_id = upload_video(youtube, video_path, fortune, date)
            logger.info(f"カード{card['label']}: アップロード成功 video_id={video_id}")
            return True

        except Exception as e:
            logger.warning(f"カード{card['label']}: 試行 {attempt}/{max_retries} 失敗: {e}")
            if attempt < max_retries:
                logger.info(f"  {retry_wait}秒後にリトライします...")
                time.sleep(retry_wait)

    logger.error(f"カード{card['label']}: すべてのリトライが失敗しました")
    return False


def job_upload_cards() -> None:
    """毎朝 6:30〜 JST: 全3カードを5分おきにアップロードする。"""
    date = datetime.now(JST).strftime("%Y-%m-%d")
    logger = _setup_logger(date)

    logger.info(f"=== アップロード開始: {[c['name'] for c in CARD_CHOICES]} ===")

    try:
        youtube = build_youtube_client()
    except Exception as e:
        logger.error(f"YouTube クライアント構築失敗: {e}", exc_info=True)
        return

    success = 0
    failed  = 0

    for i, card in enumerate(CARD_CHOICES):
        logger.info(f"[{i + 1}/{len(CARD_CHOICES)}] カード{card['label']} 処理開始")
        ok = _upload_with_retry(youtube, card, date, logger)
        if ok:
            success += 1
        else:
            failed += 1

        if i < len(CARD_CHOICES) - 1:
            wait_sec = 5 * 60
            logger.info(f"  次のアップロードまで {wait_sec // 60} 分待機...")
            time.sleep(wait_sec)

    logger.info(
        f"=== アップロード完了 成功:{success} 失敗:{failed} ==="
    )


# ---------------------------------------------------------------------------
# スケジューラ起動
# ---------------------------------------------------------------------------

def run_scheduler() -> None:
    """APScheduler を起動してバックグラウンドでジョブを実行し続ける。"""
    scheduler = BlockingScheduler(timezone=JST)

    # 毎朝 6:00 JST: 運勢テキスト生成
    scheduler.add_job(
        job_generate_fortunes,
        CronTrigger(hour=6, minute=0, timezone=JST),
        id="generate_fortunes",
        name="占いテキスト生成",
        misfire_grace_time=300,
    )

    # 毎朝 6:30 JST: アップロード（3カードを逐次処理、内部で5分待機）
    scheduler.add_job(
        job_upload_cards,
        CronTrigger(hour=6, minute=30, timezone=JST),
        id="upload_cards",
        name="動画アップロード",
        misfire_grace_time=300,
    )

    print("🕕 スケジューラを起動しました")
    print("  - 毎朝 06:00 JST: タロット占いテキスト生成")
    print("  - 毎朝 06:30 JST: 動画生成＆アップロード（3カード）")
    print("  Ctrl+C で停止")

    try:
        scheduler.start()
    except KeyboardInterrupt:
        print("\n⏹️  スケジューラを停止しました")


# ---------------------------------------------------------------------------
# CLI エントリーポイント
# ---------------------------------------------------------------------------

def main() -> None:
    """コマンドライン引数を解析してスケジューラを起動する。"""
    parser = argparse.ArgumentParser(description="占いボット スケジューラ")
    parser.add_argument(
        "--once",
        action="store_true",
        help="今すぐ1回だけ生成＋アップロードを実行（テスト用）",
    )
    args = parser.parse_args()

    if args.once:
        job_generate_fortunes()
        job_upload_cards()
    else:
        run_scheduler()


if __name__ == "__main__":
    main()
