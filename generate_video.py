"""
generate_video.py - 占いショート動画 自動生成メインスクリプト

使用方法:
    python generate_video.py           # 今日の動画を生成
    python generate_video.py --test    # テストモード（短縮・デバッグ出力）
    python generate_video.py --date 20240411  # 特定日付で生成
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime

import numpy as np

# ImageMagick バイナリのパスを明示（TextClip が使用する）
os.environ.setdefault("IMAGEMAGICK_BINARY", "/usr/bin/convert")

try:
    from moviepy.editor import (
        ColorClip,
        CompositeVideoClip,
        ImageClip,
        TextClip,
        VideoClip,
        concatenate_videoclips,
    )
    import moviepy.config as mpy_config

    # ImageMagick のパスを MoviePy に設定
    for candidate in ("/usr/bin/convert", "/usr/local/bin/convert"):
        if os.path.exists(candidate):
            mpy_config.change_settings({"IMAGEMAGICK_BINARY": candidate})
            break
except ImportError as e:
    print(f"ERROR: moviepy が見つかりません: {e}", file=sys.stderr)
    sys.exit(1)

from fortune_content import get_fortune_cards, get_date_string
from card_generator import generate_card_back, generate_card_front

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
FPS = 30
CARD_W = 200
CARD_H = 320

# カラーパレット
COLOR_BG_DARK = (15, 10, 40)
COLOR_BG_MID = (35, 12, 70)
COLOR_GOLD = "#C8A84B"
COLOR_WHITE = "white"
COLOR_LIGHT_GOLD = "#F0D060"

# シーン尺（秒）
T_INTRO_END = 3
T_SELECT_END = 8
T_FLIP_END = 20
T_RESULT_END = 35
T_ENDING_END = 40


# ---------------------------------------------------------------------------
# ユーティリティ
# ---------------------------------------------------------------------------


def find_font() -> str | None:
    """利用可能な日本語フォントのパスを返す。"""
    # 1. fc-list で Noto CJK を検索
    try:
        result = subprocess.run(
            ["fc-list", ":lang=ja", "--format=%{file}\\n"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        for line in result.stdout.split("\n"):
            line = line.strip()
            if line and any(kw in line for kw in ("Noto", "noto")) and os.path.exists(line):
                return line
    except Exception:
        pass

    # 2. 既知パスを試す
    fallbacks = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJKjp-Regular.otf",
        "/usr/share/fonts/noto-cjk/NotoSansCJKjp-Regular.otf",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
    ]
    for p in fallbacks:
        if os.path.exists(p):
            return p

    # 3. fc-list で全フォントから日本語対応を検索
    try:
        result = subprocess.run(
            ["fc-list", "--format=%{file}\\n"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        for line in result.stdout.split("\n"):
            line = line.strip()
            if line and os.path.exists(line):
                lower = line.lower()
                if "cjk" in lower or "jp" in lower or "japanese" in lower:
                    return line
    except Exception:
        pass

    return None


def make_text_clip(
    text: str,
    fontsize: int,
    color: str = "white",
    font: str | None = None,
    duration: float = 1.0,
    size: tuple | None = None,
    method: str = "label",
) -> TextClip:
    """TextClip を生成するヘルパー。"""
    kwargs: dict = {
        "txt": text,
        "fontsize": fontsize,
        "color": color,
    }
    if font:
        kwargs["font"] = font
    if size:
        kwargs["size"] = size
        kwargs["method"] = "caption"
    else:
        kwargs["method"] = method

    try:
        clip = TextClip(**kwargs).set_duration(duration)
    except Exception:
        # フォントが使えない場合はシンプルな白テキストで再挑戦
        kwargs.pop("font", None)
        clip = TextClip(**kwargs).set_duration(duration)
    return clip


def create_gradient_bg(
    width: int,
    height: int,
    duration: float,
    color1: tuple,
    color2: tuple,
) -> ImageClip:
    """上から下へグラデーション背景を生成する。"""
    arr = np.zeros((height, width, 3), dtype=np.uint8)
    for y in range(height):
        t = y / (height - 1)
        r = int(color1[0] * (1 - t) + color2[0] * t)
        g = int(color1[1] * (1 - t) + color2[1] * t)
        b = int(color1[2] * (1 - t) + color2[2] * t)
        arr[y, :] = (r, g, b)
    return ImageClip(arr).set_duration(duration)


def squeeze_frame(frame: np.ndarray, scale_x: float) -> np.ndarray:
    """フレームを水平方向にスケーリングし中央に配置する（カードフリップ演出用）。"""
    h, w = frame.shape[:2]
    if scale_x <= 0.01:
        return np.zeros((h, w, 3), dtype=np.uint8)
    new_w = max(1, int(w * scale_x))
    x_src = np.linspace(0, w - 1, new_w).astype(int)
    squeezed = frame[:, x_src, :]
    result = np.zeros((h, w, 3), dtype=np.uint8)
    offset = (w - new_w) // 2
    result[:, offset : offset + new_w] = squeezed
    return result


# ---------------------------------------------------------------------------
# カードフリップアニメーション
# ---------------------------------------------------------------------------


def make_card_flip_clip(
    back_arr: np.ndarray,
    front_arr: np.ndarray,
    duration: float = 2.0,
) -> VideoClip:
    """カードフリップアニメーション VideoClip を生成する。"""
    back = back_arr.copy()
    front = front_arr.copy()

    def make_frame(t: float) -> np.ndarray:
        half = duration / 2
        if t < half:
            scale = max(0.0, 1.0 - t / half)
            return squeeze_frame(back, scale)
        else:
            scale = min(1.0, (t - half) / half)
            return squeeze_frame(front, scale)

    return VideoClip(make_frame, duration=duration)


# ---------------------------------------------------------------------------
# シーン生成
# ---------------------------------------------------------------------------


def make_scene_intro(font: str | None, date: datetime) -> CompositeVideoClip:
    """シーン1: イントロ (0-3秒)"""
    dur = float(T_INTRO_END)
    bg = create_gradient_bg(VIDEO_WIDTH, VIDEO_HEIGHT, dur, COLOR_BG_DARK, COLOR_BG_MID)

    title = make_text_clip(
        "今日のあなたへ",
        fontsize=88,
        color=COLOR_WHITE,
        font=font,
        duration=dur,
        size=(VIDEO_WIDTH - 80, None),
    ).set_position(("center", VIDEO_HEIGHT // 2 - 80))

    date_str = get_date_string(date)
    date_clip = make_text_clip(
        date_str,
        fontsize=54,
        color=COLOR_GOLD,
        font=font,
        duration=dur,
        size=(VIDEO_WIDTH - 80, None),
    ).set_position(("center", VIDEO_HEIGHT // 2 + 30))

    return CompositeVideoClip(
        [bg, title, date_clip], size=(VIDEO_WIDTH, VIDEO_HEIGHT)
    )


def make_scene_select(
    font: str | None,
    back_arr: np.ndarray,
    card_positions: list[tuple[int, int]],
) -> CompositeVideoClip:
    """シーン2: カード選択促し (3-8秒)"""
    dur = float(T_SELECT_END - T_INTRO_END)
    bg = create_gradient_bg(VIDEO_WIDTH, VIDEO_HEIGHT, dur, COLOR_BG_MID, COLOR_BG_DARK)

    prompt = make_text_clip(
        "あなたの直感で\n1枚選んでください",
        fontsize=58,
        color=COLOR_WHITE,
        font=font,
        duration=dur,
        size=(VIDEO_WIDTH - 80, None),
    ).set_position(("center", 680))

    clips: list = [bg, prompt]

    # カード3枚をフェードインで表示
    for i, (px, py) in enumerate(card_positions):
        fade_delay = 0.4 + i * 0.3
        card_clip = (
            ImageClip(back_arr)
            .set_duration(dur)
            .set_position((px, py))
            .crossfadein(0.4)
            .set_start(fade_delay)
        )
        clips.append(card_clip)

    return CompositeVideoClip(clips, size=(VIDEO_WIDTH, VIDEO_HEIGHT))


def make_scene_flip(
    font: str | None,
    back_arr: np.ndarray,
    front_arrs: list[np.ndarray],
    cards: list[dict],
    card_positions: list[tuple[int, int]],
) -> CompositeVideoClip:
    """シーン3: カードフリップ演出 (8-20秒)"""
    dur = float(T_FLIP_END - T_SELECT_END)
    bg = create_gradient_bg(VIDEO_WIDTH, VIDEO_HEIGHT, dur, COLOR_BG_DARK, COLOR_BG_MID)

    clips: list = [bg]

    # 各カードのフリップタイミング（相対時刻）
    flip_starts = [0.0, 3.5, 7.0]  # 8s, 11.5s, 15s (絶対時刻)
    flip_dur = 2.0
    hold_start = 10.0  # フリップ終了後のホールド開始（シーン内相対）

    for i, (px, py) in enumerate(card_positions):
        fs = flip_starts[i]

        # フリップ前：裏面を表示
        if fs > 0:
            pre_back = (
                ImageClip(back_arr)
                .set_duration(fs)
                .set_start(0)
                .set_position((px, py))
            )
            clips.append(pre_back)

        # フリップアニメーション
        flip = (
            make_card_flip_clip(back_arr, front_arrs[i], duration=flip_dur)
            .set_start(fs)
            .set_position((px, py))
        )
        clips.append(flip)

        # フリップ後：表面を表示してカード番号を重ねる
        post_start = fs + flip_dur
        post_dur = dur - post_start
        if post_dur > 0:
            post_front = (
                ImageClip(front_arrs[i])
                .set_duration(post_dur)
                .set_start(post_start)
                .set_position((px, py))
            )
            clips.append(post_front)

            # カードタイトル
            card_title_clip = make_text_clip(
                cards[i]["title"],
                fontsize=36,
                color=COLOR_GOLD,
                font=font,
                duration=post_dur,
                size=(CARD_W, None),
            ).set_start(post_start).set_position((px, py + CARD_H + 5))
            clips.append(card_title_clip)

    # 「カードが語りかけています」テキスト（フリップ後半）
    info_start = flip_starts[2] + flip_dur
    info_dur = dur - info_start
    if info_dur > 0:
        info = make_text_clip(
            "カードのメッセージを\n受け取りましょう",
            fontsize=44,
            color=COLOR_WHITE,
            font=font,
            duration=info_dur,
            size=(VIDEO_WIDTH - 80, None),
        ).set_start(info_start).set_position(("center", 680))
        clips.append(info)

    return CompositeVideoClip(clips, size=(VIDEO_WIDTH, VIDEO_HEIGHT))


def make_scene_results(
    font: str | None,
    front_arrs: list[np.ndarray],
    cards: list[dict],
    card_positions: list[tuple[int, int]],
) -> CompositeVideoClip:
    """シーン4: 運勢結果発表 (20-35秒)"""
    dur = float(T_RESULT_END - T_FLIP_END)
    bg = create_gradient_bg(VIDEO_WIDTH, VIDEO_HEIGHT, dur, COLOR_BG_MID, (25, 8, 55))

    clips: list = [bg]

    # ヘッダー
    header = make_text_clip(
        "今日のあなたへのメッセージ",
        fontsize=52,
        color=COLOR_WHITE,
        font=font,
        duration=dur,
        size=(VIDEO_WIDTH - 60, None),
    ).set_position(("center", 120))
    clips.append(header)

    # カード縦並び表示（小さめのサイズで）
    small_w, small_h = 160, 256
    card_x_start = (VIDEO_WIDTH - small_w) // 2
    card_y_positions = [260, 620, 980]

    rank_labels = {1: "🥇 1位", 2: "🥈 2位", 3: "🥉 3位"}

    for i, card in enumerate(cards):
        # cards はランク順（1位から）
        py = card_y_positions[i]
        px = card_x_start

        # カード画像をリサイズ
        arr = front_arrs[i]
        x_src = np.linspace(0, arr.shape[1] - 1, small_w).astype(int)
        y_src = np.linspace(0, arr.shape[0] - 1, small_h).astype(int)
        small_arr = arr[np.ix_(y_src, x_src)]

        fade_in_delay = i * 0.5
        card_clip = (
            ImageClip(small_arr)
            .set_duration(dur - fade_in_delay)
            .set_start(fade_in_delay)
            .crossfadein(0.3)
            .set_position((px, py))
        )
        clips.append(card_clip)

        # ランクラベル
        rank_color = COLOR_LIGHT_GOLD if card["rank"] == 1 else COLOR_GOLD
        rank_clip = make_text_clip(
            f"第{card['rank']}位  {card['title']}",
            fontsize=40,
            color=rank_color,
            font=font,
            duration=dur - fade_in_delay,
            size=(VIDEO_WIDTH - 60, None),
        ).set_start(fade_in_delay).crossfadein(0.3).set_position(
            ("center", py - 38)
        )
        clips.append(rank_clip)

        # メッセージテキスト
        msg_lines = card["message"].split("\n")
        for j, line in enumerate(msg_lines):
            msg_clip = make_text_clip(
                line,
                fontsize=30,
                color=COLOR_WHITE,
                font=font,
                duration=dur - fade_in_delay,
                size=(VIDEO_WIDTH - 60, None),
            ).set_start(fade_in_delay).crossfadein(0.3).set_position(
                ("center", py + small_h + 5 + j * 34)
            )
            clips.append(msg_clip)

    return CompositeVideoClip(clips, size=(VIDEO_WIDTH, VIDEO_HEIGHT))


def make_scene_ending(font: str | None) -> CompositeVideoClip:
    """シーン5: エンディング (35-40秒)"""
    dur = float(T_ENDING_END - T_RESULT_END)
    bg = create_gradient_bg(VIDEO_WIDTH, VIDEO_HEIGHT, dur, (25, 8, 55), COLOR_BG_DARK)

    msg1 = make_text_clip(
        "明日も良い一日を",
        fontsize=80,
        color=COLOR_WHITE,
        font=font,
        duration=dur,
        size=(VIDEO_WIDTH - 80, None),
    ).set_position(("center", VIDEO_HEIGHT // 2 - 90))

    msg2 = make_text_clip(
        "毎日更新中",
        fontsize=50,
        color=COLOR_GOLD,
        font=font,
        duration=dur,
        size=(VIDEO_WIDTH - 80, None),
    ).set_position(("center", VIDEO_HEIGHT // 2 + 20))

    msg3 = make_text_clip(
        "チャンネル登録をお願いします",
        fontsize=38,
        color=COLOR_WHITE,
        font=font,
        duration=dur,
        size=(VIDEO_WIDTH - 80, None),
    ).set_position(("center", VIDEO_HEIGHT // 2 + 100))

    return CompositeVideoClip(
        [bg, msg1, msg2, msg3], size=(VIDEO_WIDTH, VIDEO_HEIGHT)
    )


# ---------------------------------------------------------------------------
# メイン生成処理
# ---------------------------------------------------------------------------


def generate_video(date: datetime, output_path: str, test_mode: bool = False) -> None:
    """指定日付の動画を生成して output_path に保存する。"""
    print(f"[INFO] 生成日付: {get_date_string(date)}")
    print(f"[INFO] 出力先: {output_path}")

    # フォント検出
    font = find_font()
    if font:
        print(f"[INFO] フォント: {font}")
    else:
        print("[WARN] 日本語フォントが見つかりません。デフォルトフォントを使用します。")

    # 占いコンテンツ生成
    cards = get_fortune_cards(date)
    print("[INFO] カード:")
    for c in cards:
        print(f"  {c['rank']}位: {c['title']} ({c['symbol']})")

    # カード画像生成
    back_arr = generate_card_back(CARD_W, CARD_H)
    front_arrs: list[np.ndarray] = []
    for card in cards:
        front_arr = generate_card_front(card["title"], card["symbol"], card["rank"])
        front_arrs.append(front_arr)

    # カード配置座標（横並び）
    gap = (VIDEO_WIDTH - 3 * CARD_W) // 4
    card_positions = [
        (gap, 1060),
        (gap * 2 + CARD_W, 1060),
        (gap * 3 + CARD_W * 2, 1060),
    ]

    print("[INFO] シーン生成中...")

    if test_mode:
        # テストモード: 簡略版（シーン1のみ）
        scene1 = make_scene_intro(font, date)
        video = scene1.subclip(0, 3)
        print("[INFO] テストモード: シーン1のみ生成")
    else:
        scene1 = make_scene_intro(font, date)
        scene2 = make_scene_select(font, back_arr, card_positions)
        scene3 = make_scene_flip(font, back_arr, front_arrs, cards, card_positions)
        scene4 = make_scene_results(font, front_arrs, cards, card_positions)
        scene5 = make_scene_ending(font)

        print("[INFO] シーン結合中...")
        video = concatenate_videoclips(
            [scene1, scene2, scene3, scene4, scene5],
            method="compose",
        )

    # 出力先ディレクトリを作成
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    print("[INFO] 動画書き出し中（しばらくかかります）...")
    video.write_videofile(
        output_path,
        fps=FPS,
        codec="libx264",
        audio=False,
        logger="bar" if not test_mode else None,
        ffmpeg_params=["-crf", "23", "-preset", "medium"],
    )
    print(f"[OK] 完了: {output_path}")


# ---------------------------------------------------------------------------
# エントリーポイント
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="占いショート動画を生成します")
    parser.add_argument("--test", action="store_true", help="テストモード（簡略生成）")
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="生成日付（YYYYMMDD形式、省略時は今日）",
    )
    args = parser.parse_args()

    if args.date:
        try:
            target_date = datetime.strptime(args.date, "%Y%m%d")
        except ValueError:
            print(f"ERROR: 日付形式が不正です: {args.date} (YYYYMMDD形式で指定)", file=sys.stderr)
            sys.exit(1)
    else:
        target_date = datetime.now()

    date_str = target_date.strftime("%Y%m%d")
    output_path = os.path.join("output", f"fortune_{date_str}.mp4")

    try:
        generate_video(target_date, output_path, test_mode=args.test)
    except Exception as e:
        print(f"ERROR: 動画生成に失敗しました: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
