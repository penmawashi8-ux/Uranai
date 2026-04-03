"""
config.py - 定数・カード定義
"""

import os

# タロットカード3択（星座占いの代わり）
CARD_CHOICES = [
    {"slug": "card_a", "name": "Aのカード", "label": "A", "color": "#CC5DE8", "dark": "#0d001a", "mid": "#2d004d"},
    {"slug": "card_b", "name": "Bのカード", "label": "B", "color": "#74C0FC", "dark": "#00001a", "mid": "#00004d"},
    {"slug": "card_c", "name": "Cのカード", "label": "C", "color": "#FFD43B", "dark": "#1a1a00", "mid": "#4d4d00"},
]

VIDEO_WIDTH  = 1080
VIDEO_HEIGHT = 1920
VIDEO_FPS    = 30
FONT_BOLD    = "assets/fonts/NotoSansCJK-Bold.ttc"
FONT_REGULAR = "assets/fonts/NotoSansCJK-Regular.ttc"

# パス設定
BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR      = os.path.join(BASE_DIR, "assets")
FONTS_DIR       = os.path.join(ASSETS_DIR, "fonts")
BACKGROUNDS_DIR = os.path.join(ASSETS_DIR, "backgrounds")
BGM_DIR         = os.path.join(ASSETS_DIR, "bgm")
OUTPUT_DIR      = os.path.join(BASE_DIR, "output")
LOGS_DIR        = os.path.join(BASE_DIR, "logs")

# Gemini APIレート制限対策
GEMINI_SLEEP_SEC = 8  # 15RPM制限対策（8秒間隔 ≈ 7.5リクエスト/分）

# YouTube API制限
YOUTUBE_MAX_UPLOADS_PER_DAY = 6  # 1日10,000ユニット / 1600ユニット per upload
