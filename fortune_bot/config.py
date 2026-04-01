"""
config.py - 定数・星座定義
"""

import os

ZODIAC_LIST = [
    {"slug": "aries",        "name": "おひつじ座", "emoji": "♈", "color": "#FF6B6B", "dark": "#1a0020", "mid": "#8B0000"},
    {"slug": "taurus",       "name": "おうし座",   "emoji": "♉", "color": "#51CF66", "dark": "#001a00", "mid": "#1a4d00"},
    {"slug": "gemini",       "name": "ふたご座",   "emoji": "♊", "color": "#FFD43B", "dark": "#1a1a00", "mid": "#4d4d00"},
    {"slug": "cancer",       "name": "かに座",     "emoji": "♋", "color": "#74C0FC", "dark": "#00001a", "mid": "#00004d"},
    {"slug": "leo",          "name": "しし座",     "emoji": "♌", "color": "#FF922B", "dark": "#1a0a00", "mid": "#4d2000"},
    {"slug": "virgo",        "name": "おとめ座",   "emoji": "♍", "color": "#94D82D", "dark": "#0d1a00", "mid": "#204d00"},
    {"slug": "libra",        "name": "てんびん座", "emoji": "♎", "color": "#F783AC", "dark": "#1a0010", "mid": "#4d0030"},
    {"slug": "scorpio",      "name": "さそり座",   "emoji": "♏", "color": "#CC5DE8", "dark": "#0d001a", "mid": "#2d004d"},
    {"slug": "sagittarius",  "name": "いて座",     "emoji": "♐", "color": "#FF6348", "dark": "#1a0500", "mid": "#4d1500"},
    {"slug": "capricorn",    "name": "やぎ座",     "emoji": "♑", "color": "#868E96", "dark": "#0a0a0a", "mid": "#252525"},
    {"slug": "aquarius",     "name": "みずがめ座", "emoji": "♒", "color": "#339AF0", "dark": "#00101a", "mid": "#00304d"},
    {"slug": "pisces",       "name": "うお座",     "emoji": "♓", "color": "#20C997", "dark": "#001a15", "mid": "#004d3d"},
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
GEMINI_SLEEP_SEC = 5

# YouTube API制限
YOUTUBE_MAX_UPLOADS_PER_DAY = 6  # 1日10,000ユニット / 1600ユニット per upload
