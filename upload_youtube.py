"""
upload_youtube.py - YouTube Shorts に動画を自動投稿する

使用方法:
    python upload_youtube.py output/fortune_YYYYMMDD.mp4

環境変数（GitHub Secrets から渡す）:
    YOUTUBE_CLIENT_ID
    YOUTUBE_CLIENT_SECRET
    YOUTUBE_REFRESH_TOKEN
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


def get_youtube_client():
    """環境変数からクレデンシャルを読み込んでYouTube APIクライアントを返す。"""
    client_id     = os.environ.get("YOUTUBE_CLIENT_ID")
    client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET")
    refresh_token = os.environ.get("YOUTUBE_REFRESH_TOKEN")

    if not all([client_id, client_secret, refresh_token]):
        print("ERROR: 環境変数 YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET / YOUTUBE_REFRESH_TOKEN が未設定です",
              file=sys.stderr)
        sys.exit(1)

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        client_id=client_id,
        client_secret=client_secret,
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def upload_video(video_path: str, date: datetime) -> str:
    """動画を YouTube Shorts としてアップロードし、動画IDを返す。"""
    if not os.path.exists(video_path):
        print(f"ERROR: 動画ファイルが見つかりません: {video_path}", file=sys.stderr)
        sys.exit(1)

    month = date.month
    day   = date.day

    title = f"🔮 {month}月{day}日の運勢占い #shorts"
    description = (
        f"{month}月{day}日の運勢をタロットカードで占います。\n\n"
        "3枚のカードがあなたへのメッセージをお届けします。\n"
        "ラッキーカラー・ラッキーアイテムもチェックしてね！\n\n"
        "#占い #運勢 #タロット #shorts #毎日占い"
    )

    youtube = get_youtube_client()

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": ["占い", "運勢", "タロット", "shorts", "毎日占い", "ラッキー"],
            "categoryId": "22",      # People & Blogs
            "defaultLanguage": "ja",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(
        video_path,
        mimetype="video/mp4",
        resumable=True,
        chunksize=4 * 1024 * 1024,  # 4MB チャンク
    )

    print(f"[INFO] アップロード開始: {title}")
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            pct = int(status.progress() * 100)
            print(f"[INFO] アップロード中... {pct}%")

    video_id = response["id"]
    print(f"[OK] アップロード完了: https://www.youtube.com/shorts/{video_id}")
    return video_id


def main() -> None:
    parser = argparse.ArgumentParser(description="YouTube Shorts に動画をアップロードします")
    parser.add_argument("video_path", help="アップロードする動画ファイルパス")
    parser.add_argument("--date", type=str, default=None,
                        help="動画の日付 (YYYYMMDD形式、省略時は今日)")
    args = parser.parse_args()

    if args.date:
        try:
            date = datetime.strptime(args.date, "%Y%m%d")
        except ValueError:
            print(f"ERROR: 日付形式が不正です: {args.date}", file=sys.stderr)
            sys.exit(1)
    else:
        date = datetime.now()

    upload_video(args.video_path, date)


if __name__ == "__main__":
    main()
