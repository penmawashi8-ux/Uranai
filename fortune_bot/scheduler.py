"""
scheduler.py - APScheduler で占い動画の生成・アップロードを自動実行する。

毎朝 6:00 JST: 全星座の運勢テキストを一括生成
毎朝 6:30〜  : 6星座を5分おきにアップロード（奇数日/偶数日で交互）

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

from config import LOGS_DIR, ZODIAC_LIST, YOUTUBE_MAX_UPLOADS_PER_DAY, AUTO_POST_ENABLED
from generate_fortune import generate_all_fortunes, get_fortune_for_sign
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
# 奇数日 / 偶数日で6星座ずつ振り分け
# ---------------------------------------------------------------------------

def _signs_for_today(date: str) -> list[dict]:
    """今日アップロードする6星座を返す（奇数日 / 偶数日で交互）。

    奇数日: ZODIAC_LIST の前半6星座
    偶数日: ZODIAC_LIST の後半6星座

    Args:
        date: 日付文字列（YYYY-MM-DD）。

    Returns:
        ZODIAC_LIST の6要素のサブリスト。
    """
    day = int(date.split("-")[2])
    half = len(ZODIAC_LIST) // 2  # 6
    if day % 2 == 1:
        return ZODIAC_LIST[:half]
    else:
        return ZODIAC_LIST[half:]


# ---------------------------------------------------------------------------
# スケジュールジョブ
# ---------------------------------------------------------------------------

def job_generate_fortunes() -> None:
    """毎朝 6:00 JST: 全星座の運勢テキストを一括生成する。"""
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
    zodiac: dict,
    date: str,
    logger: logging.Logger,
    max_retries: int = 3,
    retry_wait: int = 30,
) -> bool:
    """動画生成＋アップロードをリトライ付きで実行する。

    Args:
        youtube:     YouTube API クライアント。
        zodiac:      ZODIAC_LIST の1要素。
        date:        日付文字列（YYYY-MM-DD）。
        logger:      ロガー。
        max_retries: 最大リトライ回数。
        retry_wait:  リトライ待機秒数。

    Returns:
        成功すれば True、失敗すれば False。
    """
    for attempt in range(1, max_retries + 1):
        try:
            fortune = get_fortune_for_sign(date, zodiac["name"])
            if fortune is None:
                logger.warning(f"{zodiac['name']}: 運勢データなし（スキップ）")
                return False

            # 動画生成
            video_path = generate_video(fortune, zodiac["slug"], date)

            # アップロード
            video_id = upload_video(youtube, video_path, fortune, date)
            logger.info(f"{zodiac['name']}: アップロード成功 video_id={video_id}")
            return True

        except Exception as e:
            logger.warning(f"{zodiac['name']}: 試行 {attempt}/{max_retries} 失敗: {e}")
            if attempt < max_retries:
                logger.info(f"  {retry_wait}秒後にリトライします...")
                time.sleep(retry_wait)

    logger.error(f"{zodiac['name']}: すべてのリトライが失敗しました")
    return False


def job_upload_signs() -> None:
    """毎朝 6:30〜 JST: 今日の6星座を5分おきにアップロードする。

    6星座を逐次処理し、各完了後に5分待機する。
    AUTO_POST_ENABLED が False の場合はスキップする。
    """
    if not AUTO_POST_ENABLED:
        date = datetime.now(JST).strftime("%Y-%m-%d")
        logger = _setup_logger(date)
        logger.info("AUTO_POST_ENABLED=False のため自動投稿をスキップしました")
        return

    date = datetime.now(JST).strftime("%Y-%m-%d")
    logger = _setup_logger(date)
    signs = _signs_for_today(date)

    logger.info(f"=== アップロード開始: {[z['name'] for z in signs]} ===")

    try:
        youtube = build_youtube_client()
    except Exception as e:
        logger.error(f"YouTube クライアント構築失敗: {e}", exc_info=True)
        return

    success = 0
    failed  = 0

    for i, zodiac in enumerate(signs):
        logger.info(f"[{i + 1}/{len(signs)}] {zodiac['name']} 処理開始")
        ok = _upload_with_retry(youtube, zodiac, date, logger)
        if ok:
            success += 1
        else:
            failed += 1

        # 最後の星座以外は5分待機
        if i < len(signs) - 1:
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

    # 毎朝 6:30 JST: アップロード（6星座を逐次処理、内部で5分待機）
    scheduler.add_job(
        job_upload_signs,
        CronTrigger(hour=6, minute=30, timezone=JST),
        id="upload_signs",
        name="動画アップロード",
        misfire_grace_time=300,
    )

    print("🕕 スケジューラを起動しました")
    print("  - 毎朝 06:00 JST: 運勢テキスト生成")
    print("  - 毎朝 06:30 JST: 動画生成＆アップロード（6星座）")
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
        job_upload_signs()
    else:
        run_scheduler()


if __name__ == "__main__":
    main()
