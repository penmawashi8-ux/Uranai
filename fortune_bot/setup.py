"""
setup.py - 初回セットアップスクリプト

実行するだけでフォント・背景画像・フォルダ構成がすべて自動で揃う。
背景生成は ImageMagick 優先、なければ Pillow にフォールバック。
"""

from __future__ import annotations

import os
import sys
import shutil
import random
import subprocess
import platform
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (
    BASE_DIR,
    ASSETS_DIR,
    FONTS_DIR,
    BACKGROUNDS_DIR,
    BGM_DIR,
    OUTPUT_DIR,
    LOGS_DIR,
    CARD_CHOICES,
)

# フォントのダウンロード元
FONT_DOWNLOAD_URL = (
    "https://github.com/googlefonts/noto-cjk/raw/main/Sans/OTF/Japanese/"
    "NotoSansCJKjp-Bold.otf"
)
FONT_DEST_BOLD    = os.path.join(FONTS_DIR, "NotoSansCJK-Bold.ttc")
FONT_DEST_REGULAR = os.path.join(FONTS_DIR, "NotoSansCJK-Regular.ttc")


# ---------------------------------------------------------------------------
# ステップ1: フォルダ作成
# ---------------------------------------------------------------------------

def create_directories() -> None:
    """必要なフォルダをすべて作成する。"""
    for d in [ASSETS_DIR, FONTS_DIR, BACKGROUNDS_DIR, BGM_DIR, OUTPUT_DIR, LOGS_DIR]:
        Path(d).mkdir(parents=True, exist_ok=True)
    print("✅ フォルダ構成を確認・作成しました")


# ---------------------------------------------------------------------------
# ステップ2: フォントのセットアップ
# ---------------------------------------------------------------------------

def _search_font_in_dirs(search_dirs: list[str], candidates: list[str]) -> str | None:
    """指定ディレクトリ群からフォントファイルを再帰検索する。

    Args:
        search_dirs: 検索対象ディレクトリのリスト。
        candidates:  ファイル名の候補リスト。

    Returns:
        見つかったフォントの絶対パス。見つからない場合は None。
    """
    # まずフラットに探す（高速）
    for d in search_dirs:
        for name in candidates:
            path = os.path.join(d, name)
            if os.path.isfile(path):
                return path

    # 再帰検索（サブディレクトリも含む）
    for d in search_dirs:
        if not os.path.isdir(d):
            continue
        for root, _, files in os.walk(d):
            for f in files:
                if f in candidates:
                    return os.path.join(root, f)

    return None


def _find_system_font() -> str | None:
    """システムから Noto Sans CJK のフォントファイルを探す。

    Returns:
        見つかったフォントパス。なければ None。
    """
    system = platform.system()
    candidates = [
        "NotoSansCJK-Bold.ttc",
        "NotoSansCJKjp-Bold.otf",
        "NotoSansCJKjp-Bold.ttf",
        "NotoSansCJK-Bold.otf",
    ]

    if system == "Linux":
        search_dirs = [
            "/usr/share/fonts/opentype/noto/",
            "/usr/share/fonts/noto/",
            "/usr/share/fonts/",
            "/usr/local/share/fonts/",
        ]
    elif system == "Darwin":
        search_dirs = [
            "/System/Library/Fonts/",
            "/Library/Fonts/",
            os.path.expanduser("~/Library/Fonts/"),
        ]
    else:
        search_dirs = []

    return _search_font_in_dirs(search_dirs, candidates)


def _download_font(dest: str) -> None:
    """GitHub から Noto Sans CJK JP Bold をダウンロードする。

    Args:
        dest: 保存先ファイルパス。

    Raises:
        RuntimeError: ダウンロードに失敗した場合。
    """
    try:
        import requests  # noqa: PLC0415
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "requests"], check=True)
        import requests  # noqa: PLC0415

    print(f"  ダウンロード中: {FONT_DOWNLOAD_URL}")
    resp = requests.get(FONT_DOWNLOAD_URL, timeout=60)
    if resp.status_code != 200:
        raise RuntimeError(
            f"フォントのダウンロードに失敗しました (HTTP {resp.status_code})。\n"
            f"手動で以下に配置してください: {dest}"
        )
    with open(dest, "wb") as f:
        f.write(resp.content)
    print(f"  ✅ ダウンロード完了: {dest}")


def setup_fonts() -> None:
    """フォントを assets/fonts/ にセットアップする。

    Bold が存在しない場合にのみ処理を行う。
    Regular は Bold のコピーで代替する。
    """
    if os.path.isfile(FONT_DEST_BOLD):
        print(f"✅ フォント（Bold）はすでに存在します: {FONT_DEST_BOLD}")
    else:
        print("🔍 システムフォントを検索中...")
        found = _find_system_font()
        if found:
            shutil.copy2(found, FONT_DEST_BOLD)
            print(f"✅ フォントをコピーしました: {found} → {FONT_DEST_BOLD}")
        else:
            print("  システムに Noto Sans CJK が見つかりません。ダウンロードします...")
            _download_font(FONT_DEST_BOLD)

    # Regular は Bold の代替として同じファイルをコピー
    if not os.path.isfile(FONT_DEST_REGULAR):
        shutil.copy2(FONT_DEST_BOLD, FONT_DEST_REGULAR)
        print(f"✅ Regular フォントを Bold から複製: {FONT_DEST_REGULAR}")


# ---------------------------------------------------------------------------
# ステップ3: 背景画像の生成
# ---------------------------------------------------------------------------

def _check_imagemagick() -> str | None:
    """ImageMagick の convert コマンドが使えるか確認する。

    Returns:
        使えるコマンド名（"convert" または "magick"）。使えない場合は None。
    """
    for cmd in ["convert", "magick"]:
        try:
            result = subprocess.run(
                [cmd, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                version_line = result.stdout.splitlines()[0] if result.stdout else "(unknown)"
                print(f"✅ ImageMagick 検出: {version_line}")
                return cmd
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return None


def _star_draw_args_imagemagick(
    slug: str,
    color: str,
    white_count: int = 100,
    accent_count: int = 12,
) -> list[str]:
    """ImageMagick 用の星描画引数を生成する（random.seed でリプロダクティブ）。

    Args:
        slug:         カードのスラッグ（シード値に使用）。
        color:        アクセントカラー（16進数文字列）。
        white_count:  白い星の数。
        accent_count: アクセントカラーの星の数。

    Returns:
        ImageMagick コマンドに渡す -fill/-draw 引数のリスト。
    """
    rng = random.Random(slug)
    args: list[str] = []

    # 白い星
    args += ["-fill", "white", "-stroke", "none"]
    for _ in range(white_count):
        x = rng.randint(10, 1070)
        y = rng.randint(10, 1910)
        r = rng.randint(1, 3)
        args += ["-draw", f"circle {x},{y} {x + r},{y}"]

    # アクセントカラーの星
    args += ["-fill", color, "-stroke", "none"]
    for _ in range(accent_count):
        x = rng.randint(10, 1070)
        y = rng.randint(10, 1910)
        args += ["-draw", f"circle {x},{y} {x + 3},{y}"]

    return args


def _generate_bg_imagemagick(cmd: str, card: dict) -> None:
    """ImageMagick で1カード分の背景画像を生成する。

    Args:
        cmd:  ImageMagick コマンド名。
        card: CARD_CHOICES の1要素。

    Raises:
        RuntimeError: コマンドが失敗した場合。
    """
    slug   = card["slug"]
    mid    = card["mid"]
    dark   = card["dark"]
    color  = card["color"]
    output = os.path.join(BACKGROUNDS_DIR, f"{slug}.png")
    tmp    = output + ".tmp.png"

    # グラデーション背景
    r1 = subprocess.run(
        [cmd, "-size", "1920x1080", f"gradient:{mid}-{dark}", "-rotate", "90", tmp],
        capture_output=True, text=True,
    )
    if r1.returncode != 0:
        raise RuntimeError(f"グラデーション生成失敗 ({slug}): {r1.stderr}")

    # 星の描画
    star_args = _star_draw_args_imagemagick(slug, color)
    r2 = subprocess.run(
        [cmd, tmp] + star_args + [tmp],
        capture_output=True, text=True,
    )
    if r2.returncode != 0:
        raise RuntimeError(f"星描画失敗 ({slug}): {r2.stderr}")

    # 下部オーバーレイ（テキスト可読性向上）
    r3 = subprocess.run(
        [
            cmd, tmp,
            "-gravity", "South",
            "(", "-size", "1080x700", "gradient:none-black", ")",
            "-composite",
            output,
        ],
        capture_output=True, text=True,
    )
    if r3.returncode != 0:
        # オーバーレイ失敗時は tmp をそのまま使う
        shutil.move(tmp, output)
        print(f"  ⚠️  オーバーレイ合成に失敗しました（{slug}）。グラデーション背景を使用します")
    else:
        if os.path.isfile(tmp):
            os.remove(tmp)


def _generate_bg_numpy(card: dict) -> None:
    """numpy+zlibでPillowを使わずに背景画像を生成する。

    Args:
        card: CARD_CHOICES の1要素。
    """
    import struct
    import zlib
    import numpy as np

    slug   = card["slug"]
    mid    = card["mid"]
    dark   = card["dark"]
    color  = card["color"]
    output = os.path.join(BACKGROUNDS_DIR, f"{slug}.png")

    W, H = 1080, 1920

    def hex_to_rgb(h: str) -> tuple[int, int, int]:
        h = h.lstrip("#")
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    r1, g1, b1 = hex_to_rgb(mid)
    r2, g2, b2 = hex_to_rgb(dark)
    ar, ag, ab = hex_to_rgb(color)

    # グラデーション背景（numpy）
    t = np.linspace(0, 1, H)[:, None]
    r = (r1 + (r2 - r1) * t).astype(np.uint8)
    g = (g1 + (g2 - g1) * t).astype(np.uint8)
    b = (b1 + (b2 - b1) * t).astype(np.uint8)
    img = np.stack([np.repeat(r, W, axis=1),
                    np.repeat(g, W, axis=1),
                    np.repeat(b, W, axis=1)], axis=2)  # (H, W, 3)

    # 白い星100個
    rng = random.Random(slug)
    for _ in range(100):
        x = rng.randint(5, W - 5)
        y = rng.randint(5, H - 5)
        r_ = rng.randint(1, 3)
        img[max(0,y-r_):y+r_+1, max(0,x-r_):x+r_+1] = [255, 255, 255]

    # アクセントカラーの星12個
    for _ in range(12):
        x = rng.randint(5, W - 5)
        y = rng.randint(5, H - 5)
        img[max(0,y-3):y+4, max(0,x-3):x+4] = [ar, ag, ab]

    # 下部グラデーションオーバーレイ（黒を徐々に重ねる）
    ov_h = 700
    alpha = np.linspace(0, 0.75, ov_h)
    for i, a in enumerate(alpha):
        row = H - ov_h + i
        img[row] = (img[row] * (1 - a)).astype(np.uint8)

    # numpy配列をPNGとして保存（Pillowなし）
    def write_png(path: str, arr: "np.ndarray") -> None:
        h, w = arr.shape[:2]
        raw_rows = b"".join(b"\x00" + arr[y].tobytes() for y in range(h))
        compressed = zlib.compress(raw_rows, 9)

        def chunk(tag: bytes, data: bytes) -> bytes:
            c = struct.pack(">I", len(data)) + tag + data
            return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

        with open(path, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n")
            f.write(chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)))
            f.write(chunk(b"IDAT", compressed))
            f.write(chunk(b"IEND", b""))

    write_png(output, img)


def generate_backgrounds(imagemagick_cmd: str | None) -> None:
    """3カード分の背景画像を生成する。

    ImageMagick が使えればそちらを優先し、なければ numpy で生成する（Pillow 不使用）。

    Args:
        imagemagick_cmd: ImageMagick コマンド名。None の場合は numpy を使う。
    """
    if imagemagick_cmd is None:
        print("⚠️  ImageMagick が見つかりません。numpy で生成します（Pillow 不使用）...")

    for card in CARD_CHOICES:
        slug   = card["slug"]
        output = os.path.join(BACKGROUNDS_DIR, f"{slug}.png")

        if os.path.isfile(output):
            print(f"  ⏭️  スキップ（既存）: {slug}.png")
            continue

        print(f"  生成中: {card['name']} ({slug}.png) ...", end=" ", flush=True)
        if imagemagick_cmd:
            _generate_bg_imagemagick(imagemagick_cmd, card)
        else:
            _generate_bg_numpy(card)
        print("完了")

    print("✅ 背景画像の生成が完了しました")


# ---------------------------------------------------------------------------
# ステップ4: assets/bgm/README.txt
# ---------------------------------------------------------------------------

def create_bgm_readme() -> None:
    """BGM フォルダに README.txt を作成する。"""
    readme = os.path.join(BGM_DIR, "README.txt")
    if os.path.isfile(readme):
        return
    with open(readme, "w", encoding="utf-8") as f:
        f.write(
            "著作権フリーのBGMをここに配置してください。\n"
            "\n"
            "おすすめ:\n"
            "  DOVA-SYNDROME https://dova-s.jp\n"
            "  魔王魂         https://maou.audio\n"
            "\n"
            "ファイル名: bgm1.mp3, bgm2.mp3 ...\n"
        )
    print("✅ assets/bgm/README.txt を作成しました")


# ---------------------------------------------------------------------------
# requirements.txt / .env テンプレート
# ---------------------------------------------------------------------------

def create_requirements() -> None:
    """requirements.txt を作成する（存在しない場合のみ）。"""
    path = os.path.join(BASE_DIR, "requirements.txt")
    if os.path.isfile(path):
        return
    with open(path, "w", encoding="utf-8") as f:
        f.write(
            "google-generativeai\n"
            "moviepy\n"
            "google-api-python-client\n"
            "google-auth-oauthlib\n"
            "python-dotenv\n"
            "apscheduler\n"
            "requests\n"
        )
    print("✅ requirements.txt を作成しました")


def create_env_template() -> None:
    """.env テンプレートを作成する（存在しない場合のみ）。"""
    path = os.path.join(BASE_DIR, ".env")
    if os.path.isfile(path):
        return
    with open(path, "w", encoding="utf-8") as f:
        f.write(
            "GEMINI_API_KEY=your_gemini_api_key_here\n"
            "YOUTUBE_CLIENT_ID=your_client_id\n"
            "YOUTUBE_CLIENT_SECRET=your_client_secret\n"
            "CHANNEL_NAME=あなたのチャンネル名\n"
        )
    print("✅ .env テンプレートを作成しました")


# ---------------------------------------------------------------------------
# メイン
# ---------------------------------------------------------------------------

def main() -> None:
    """セットアップ処理を順番に実行する。"""
    print("=" * 55)
    print("🔮 占い Shorts ボット — セットアップ")
    print("=" * 55)

    print("\n【1/5】フォルダ作成")
    create_directories()

    print("\n【2/5】フォントのセットアップ")
    setup_fonts()

    print("\n【3/5】背景画像の生成")
    im_cmd = _check_imagemagick()
    generate_backgrounds(im_cmd)

    print("\n【4/5】BGM フォルダの準備")
    create_bgm_readme()

    print("\n【5/5】設定ファイルのテンプレート作成")
    create_requirements()
    create_env_template()

    print("\n" + "=" * 55)
    print("✅ セットアップ完了！次のプロンプトを貼ってください")
    print("=" * 55)


if __name__ == "__main__":
    main()
