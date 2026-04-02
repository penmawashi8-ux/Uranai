"""
upload_youtube.py - YouTube Data API v3 で動画を Shorts としてアップロードする。

使い方:
    python upload_youtube.py --auth              # 初回認証
    python upload_youtube.py --sign おひつじ座  # アップロード
    python upload_youtube.py --sign おひつじ座 --private  # 限定公開（テスト用）
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from config import LOGS_DIR, OUTPUT_DIR, ZODIAC_LIST
from generate_fortune import get_fortune_for_sign

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

SCOPES        = ["https://www.googleapis.com/auth/youtube.upload"]
TOKEN_PATH    = os.path.join(os.path.dirname(__file__), "token.json")
CLIENT_SECRETS_PATH = os.path.join(os.path.dirname(__file__), "client_secrets.json")

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 認証
# ---------------------------------------------------------------------------

def _build_client_config() -> dict:
    """環境変数から OAuth クライアント設定を構築する。

    Returns:
        client_secrets.json 相当の辞書。

    Raises:
        ValueError: 必要な環境変数が未設定の場合。
    """
    client_id     = os.getenv("YOUTUBE_CLIENT_ID", "")
    client_secret = os.getenv("YOUTUBE_CLIENT_SECRET", "")

    if not client_id or client_id == "your_client_id":
        raise ValueError(
            "YOUTUBE_CLIENT_ID が設定されていません。\n"
            ".env に YOUTUBE_CLIENT_ID=<your_id> を追加してください。"
        )
    if not client_secret or client_secret == "your_client_secret":
        raise ValueError(
            "YOUTUBE_CLIENT_SECRET が設定されていません。\n"
            ".env に YOUTUBE_CLIENT_SECRET=<your_secret> を追加してください。"
        )

    return {
        "installed": {
            "client_id":     client_id,
            "client_secret": client_secret,
            "auth_uri":      "https://accounts.google.com/o/oauth2/auth",
            "token_uri":     "https://oauth2.googleapis.com/token",
            "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
        }
    }


def get_credentials() -> Credentials:
    """OAuth2 認証情報を取得する。

    token.json が存在すれば読み込み、期限切れなら自動リフレッシュする。
    存在しない場合は認証フローを起動する（ブラウザが開く）。

    Returns:
        有効な Credentials オブジェクト。
    """
    creds: Credentials | None = None

    if os.path.isfile(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.refresh_token:
            creds.refresh(Request())
        else:
            # client_secrets.json があればそちらを優先
            if os.path.isfile(CLIENT_SECRETS_PATH):
                flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_PATH, SCOPES)
            else:
                config = _build_client_config()
                flow = InstalledAppFlow.from_client_config(config, SCOPES)

            creds = flow.run_local_server(port=0)

        # トークンを保存
        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())
        print(f"✅ 認証トークンを保存しました: {TOKEN_PATH}")

    return creds


def build_youtube_client() -> object:
    """YouTube Data API クライアントを構築する。

    Returns:
        YouTube API リソースオブジェクト。
    """
    creds = get_credentials()
    return build("youtube", "v3", credentials=creds)


# ---------------------------------------------------------------------------
# 説明文・タグの生成
# ---------------------------------------------------------------------------

def _build_title(fortune: dict, date: str) -> str:
    """動画タイトルを生成する。

    Args:
        fortune: 運勢データ。
        date:    日付文字列（YYYY-MM-DD）。

    Returns:
        タイトル文字列。
    """
    return (
        f"【{fortune['emoji']}{fortune['sign']}】"
        f"{fortune['hook']}🔮 {date} #shorts"
    )


def _build_description(fortune: dict) -> str:
    """動画説明文を生成する。

    Args:
        fortune: 運勢データ。

    Returns:
        説明文文字列。
    """
    name = fortune["sign"]
    return (
        f"{name}の今日の運勢をお届け！✨\n\n"
        f"📊 総合運：{fortune['overall']}\n"
        f"💕 恋愛運：{fortune['love']}\n"
        f"💼 仕事運：{fortune['work']}\n"
        f"💰 金運：{fortune['money']}\n\n"
        f"🍀 ラッキーカラー：{fortune['lucky_color']}\n"
        f"🎁 ラッキーアイテム：{fortune['lucky_item']}\n\n"
        "━━━━━━━━━━━━━━\n"
        "毎朝7時に12星座の運勢を投稿！\n"
        "🔔 チャンネル登録＆通知ONで運命が変わる✨\n"
        "━━━━━━━━━━━━━━\n\n"
        f"#占い #今日の運勢 #{name} #星座占い #shorts"
    )


def _build_tags(fortune: dict) -> list[str]:
    """タグリストを生成する。

    Args:
        fortune: 運勢データ。

    Returns:
        タグ文字列のリスト。
    """
    return [
        "占い", "今日の運勢", "星座占い", "shorts",
        fortune["sign"], "恋愛運", "金運",
    ]


# ---------------------------------------------------------------------------
# アップロード
# ---------------------------------------------------------------------------

def upload_video(
    youtube,
    video_path: str,
    fortune: dict,
    date: str,
    private: bool = False,
) -> str:
    """動画を YouTube にアップロードする。

    Args:
        youtube:    YouTube API クライアント。
        video_path: アップロードする MP4 ファイルパス。
        fortune:    運勢データ。
        date:       日付文字列（YYYY-MM-DD）。
        private:    True の場合は限定公開。

    Returns:
        アップロードされた動画 ID。

    Raises:
        FileNotFoundError: 動画ファイルが存在しない場合。
    """
    if not os.path.isfile(video_path):
        raise FileNotFoundError(f"動画ファイルが見つかりません: {video_path}")

    title       = _build_title(fortune, date)
    description = _build_description(fortune)
    tags        = _build_tags(fortune)
    privacy     = "private" if private else "public"

    body = {
        "snippet": {
            "title":       title,
            "description": description,
            "tags":        tags,
            "categoryId":  "22",  # People & Blogs
        },
        "status": {
            "privacyStatus": privacy,
        },
    }

    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
    request = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=media,
    )

    print(f"  📤 アップロード中: {title}")
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            pct = int(status.progress() * 100)
            print(f"  進捗: {pct}%", end="\r")

    video_id = response["id"]
    print(f"\n  ✅ アップロード完了: https://youtu.be/{video_id}")

    # ログに記録
    _log_upload(fortune["sign"], video_id, date)

    return video_id


def _log_upload(sign: str, video_id: str, date: str) -> None:
    """アップロード結果をログファイルに記録する。

    Args:
        sign:     星座名。
        video_id: YouTube 動画 ID。
        date:     日付文字列。
    """
    os.makedirs(LOGS_DIR, exist_ok=True)
    log_path = os.path.join(LOGS_DIR, f"{date}.log")
    timestamp = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M:%S JST")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] UPLOAD OK  {sign}  video_id={video_id}\n")


# ---------------------------------------------------------------------------
# CLI エントリーポイント
# ---------------------------------------------------------------------------

def _today_jst() -> str:
    jst = timezone(timedelta(hours=9))
    return datetime.now(jst).strftime("%Y-%m-%d")


def main() -> None:
    """コマンドライン引数を解析してアップロードを実行する。"""
    parser = argparse.ArgumentParser(description="YouTube Shorts アップロード")
    parser.add_argument("--auth",    action="store_true", help="初回 OAuth2 認証フロー")
    parser.add_argument("--sign",    help="星座名（日本語）例: おひつじ座")
    parser.add_argument("--date",    default=_today_jst(), help="日付 YYYY-MM-DD")
    parser.add_argument("--private", action="store_true", help="限定公開（テスト用）")
    args = parser.parse_args()

    if args.auth:
        print("🔑 OAuth2 認証を開始します（ブラウザが開きます）...")
        get_credentials()
        print("✅ 認証完了。token.json に保存されました。")
        return

    if not args.sign:
        parser.error("--sign が必要です（例: --sign おひつじ座）")

    zodiac = next((z for z in ZODIAC_LIST if z["name"] == args.sign), None)
    if zodiac is None:
        names = ", ".join(z["name"] for z in ZODIAC_LIST)
        print(f"❌ 星座名が不正です: {args.sign}\n使用可能: {names}")
        sys.exit(1)

    video_path = os.path.join(OUTPUT_DIR, f"{zodiac['slug']}_{args.date}.mp4")
    fortune    = get_fortune_for_sign(args.date, args.sign)
    if fortune is None:
        print(f"❌ {args.date} の {args.sign} の運勢データが見つかりません。")
        sys.exit(1)

    youtube = build_youtube_client()
    upload_video(youtube, video_path, fortune, args.date, private=args.private)


if __name__ == "__main__":
    main()
