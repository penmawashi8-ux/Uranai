"""
generate_video.py - MoviePy で占い動画（YouTube Shorts 縦型 1080×1920px）を生成する。

使い方:
    python generate_video.py --sign おひつじ座 --date 2025-01-01
"""

from __future__ import annotations

import argparse
import glob
import os
import random
import sys
import textwrap
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from moviepy import (
    AudioFileClip,
    ColorClip,
    CompositeVideoClip,
    ImageClip,
    TextClip,
    concatenate_videoclips,
    afx,
    vfx,
)

from config import (
    BACKGROUNDS_DIR,
    BGM_DIR,
    FONT_BOLD,
    OUTPUT_DIR,
    VIDEO_FPS,
    VIDEO_HEIGHT,
    VIDEO_WIDTH,
    ZODIAC_LIST,
)
from generate_fortune import get_fortune_for_sign, load_fortunes

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

TOTAL_DURATION = 50  # 合計50秒

SEC_INTRO   = 5
SEC_HOOK    = 5
SEC_SCORE   = 20   # 4項目 × 5秒
SEC_LUCKY   = 8
SEC_MESSAGE = 7
SEC_OUTRO   = 5

FONT_PATH = os.path.join(os.path.dirname(__file__), FONT_BOLD)

W = VIDEO_WIDTH
H = VIDEO_HEIGHT

# ---------------------------------------------------------------------------
# ユーティリティ
# ---------------------------------------------------------------------------

def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """16進数カラーコードを RGB タプルに変換する。

    Args:
        hex_color: "#RRGGBB" 形式の文字列。

    Returns:
        (R, G, B) タプル。
    """
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _wrap_text(text: str, max_chars: int = 20) -> str:
    """日本語テキストを指定文字数で折り返す。

    Args:
        text:      折り返し対象のテキスト。
        max_chars: 1行あたりの最大文字数。

    Returns:
        折り返し後のテキスト。
    """
    lines: list[str] = []
    while len(text) > max_chars:
        lines.append(text[:max_chars])
        text = text[max_chars:]
    if text:
        lines.append(text)
    return "\n".join(lines)


def _get_background_clip(slug: str, duration: float) -> ImageClip:
    """背景画像を読み込んで指定長の ImageClip を返す。

    Args:
        slug:     星座スラッグ。
        duration: クリップの長さ（秒）。

    Returns:
        背景 ImageClip。

    Raises:
        FileNotFoundError: 背景画像が見つからない場合。
    """
    bg_path = os.path.join(BACKGROUNDS_DIR, f"{slug}.png")
    if not os.path.isfile(bg_path):
        raise FileNotFoundError(
            f"背景画像が見つかりません: {bg_path}\n"
            "先に python setup.py を実行してください。"
        )
    return ImageClip(bg_path).with_duration(duration)


def _make_text_clip(
    text: str,
    font_size: int,
    color: str = "white",
    method: str = "caption",
    size: tuple[int | None, int | None] = (W - 100, None),
    duration: float = 3.0,
    text_align: str = "center",
) -> TextClip:
    """テキストクリップを生成する。

    Args:
        text:       表示テキスト。
        font_size:  フォントサイズ（px）。
        color:      文字色。
        method:     'caption'（折り返しあり）または 'label'（折り返しなし）。
        size:       クリップサイズのヒント。
        duration:   クリップ長（秒）。
        text_align: テキスト寄せ（'center', 'left', 'right'）。

    Returns:
        TextClip インスタンス。
    """
    return (
        TextClip(
            font=FONT_PATH,
            text=text,
            font_size=font_size,
            color=color,
            method=method,
            size=size,
            text_align=text_align,
            stroke_color="black",
            stroke_width=2,
        )
        .with_duration(duration)
    )


def _center_clip(clip: TextClip, y_frac: float = 0.5) -> TextClip:
    """クリップを水平中央・指定縦位置に配置する。

    Args:
        clip:   配置するクリップ。
        y_frac: 縦位置（0.0=上端, 1.0=下端, 0.5=中央）。

    Returns:
        位置設定済みのクリップ。
    """
    y = int(H * y_frac - clip.h / 2)
    return clip.with_position(("center", y))


def _load_bgm(duration: float) -> AudioFileClip | None:
    """BGM ファイルをランダムに選択してループ再生用クリップを返す。

    BGM が存在しない場合は None を返す（エラーにしない）。

    Args:
        duration: 必要な合計長（秒）。

    Returns:
        AudioFileClip またはNone。
    """
    mp3_files = sorted(glob.glob(os.path.join(BGM_DIR, "*.mp3")))
    if not mp3_files:
        return None

    bgm_path = random.choice(mp3_files)
    try:
        audio = AudioFileClip(bgm_path)
        # ループ: 必要な長さに合わせて繰り返す
        loops = int(duration / audio.duration) + 2
        from moviepy import concatenate_audioclips  # noqa: PLC0415
        looped = concatenate_audioclips([audio] * loops)
        return looped.with_duration(duration).with_effects([afx.AudioFadeOut(2)])
    except Exception as e:
        print(f"  ⚠️  BGM 読み込み失敗: {e}。無音で続行します")
        return None


# ---------------------------------------------------------------------------
# 各セクションのクリップ生成
# ---------------------------------------------------------------------------

def _make_intro(fortune: dict, bg: ImageClip, color: str) -> CompositeVideoClip:
    """イントロ（5秒）: 星座名＋絵文字をフェードイン表示。

    Args:
        fortune: 運勢データ。
        bg:      背景クリップ。
        color:   アクセントカラー。

    Returns:
        CompositeVideoClip。
    """
    d = float(SEC_INTRO)
    emoji_clip = _make_text_clip(fortune["emoji"], 160, color, duration=d)
    name_clip  = _make_text_clip(fortune["sign"], 90, "white", duration=d)

    emoji_pos = _center_clip(emoji_clip, 0.38)
    name_pos  = _center_clip(name_clip,  0.55)

    return CompositeVideoClip([
        bg.with_duration(d),
        emoji_pos.with_effects([vfx.FadeIn(1.0)]),
        name_pos.with_effects([vfx.FadeIn(1.5)]),
    ]).with_duration(d)


def _make_hook(fortune: dict, bg: ImageClip, color: str) -> CompositeVideoClip:
    """フック（5秒）: hook 文言を大きく表示。

    Args:
        fortune: 運勢データ。
        bg:      背景クリップ。
        color:   アクセントカラー。

    Returns:
        CompositeVideoClip。
    """
    d = float(SEC_HOOK)
    hook_clip = _make_text_clip(fortune["hook"], 80, color, duration=d)
    hook_pos  = _center_clip(hook_clip, 0.5)

    return CompositeVideoClip([
        bg.with_duration(d),
        hook_pos.with_effects([vfx.FadeIn(0.5)]),
    ]).with_duration(d)


def _make_score_section(fortune: dict, bg: ImageClip, color: str) -> CompositeVideoClip:
    """運勢スコア（20秒）: 総合・恋愛・仕事・金運を5秒ずつフェードイン。

    Args:
        fortune: 運勢データ。
        bg:      背景クリップ。
        color:   アクセントカラー。

    Returns:
        CompositeVideoClip。
    """
    d = float(SEC_SCORE)
    items = [
        ("📊 総合運", fortune["overall"]),
        ("💕 恋愛運", fortune["love"]),
        ("💼 仕事運", fortune["work"]),
        ("💰 金運",   fortune["money"]),
    ]

    clips: list = [bg.with_duration(d)]

    for i, (label, stars) in enumerate(items):
        t_start = i * 5.0

        label_clip = _make_text_clip(label, 55, "white", method="label", duration=d - t_start)
        star_clip  = _make_text_clip(stars, 65, color,   method="label", duration=d - t_start)

        y_base = 0.25 + i * 0.175
        clips.append(
            _center_clip(label_clip, y_base)
            .with_start(t_start)
            .with_effects([vfx.FadeIn(0.8)])
        )
        clips.append(
            _center_clip(star_clip, y_base + 0.07)
            .with_start(t_start)
            .with_effects([vfx.FadeIn(0.8)])
        )

    return CompositeVideoClip(clips).with_duration(d)


def _make_lucky(fortune: dict, bg: ImageClip, color: str) -> CompositeVideoClip:
    """ラッキー情報（8秒）: ラッキーカラー＋ラッキーアイテムを表示。

    Args:
        fortune: 運勢データ。
        bg:      背景クリップ。
        color:   アクセントカラー。

    Returns:
        CompositeVideoClip。
    """
    d = float(SEC_LUCKY)
    color_clip = _make_text_clip(
        f"🍀 ラッキーカラー\n{fortune['lucky_color']}", 65, color, duration=d
    )
    item_clip  = _make_text_clip(
        f"🎁 ラッキーアイテム\n{fortune['lucky_item']}", 65, "white", duration=d
    )

    color_pos = _center_clip(color_clip, 0.38)
    item_pos  = _center_clip(item_clip,  0.60)

    return CompositeVideoClip([
        bg.with_duration(d),
        color_pos.with_effects([vfx.FadeIn(0.8)]),
        item_pos.with_effects([vfx.FadeIn(1.2)]),
    ]).with_duration(d)


def _make_message(fortune: dict, bg: ImageClip) -> CompositeVideoClip:
    """メッセージ（7秒）: 今日のメッセージをゆっくり表示。

    Args:
        fortune: 運勢データ。
        bg:      背景クリップ。

    Returns:
        CompositeVideoClip。
    """
    d = float(SEC_MESSAGE)
    msg = _wrap_text(fortune["message"], 20)
    msg_clip  = _make_text_clip(msg, 52, "white", duration=d)
    msg_pos   = _center_clip(msg_clip, 0.5)

    return CompositeVideoClip([
        bg.with_duration(d),
        msg_pos.with_effects([vfx.FadeIn(1.0)]),
    ]).with_duration(d)


def _make_outro(bg: ImageClip, color: str) -> CompositeVideoClip:
    """アウトロ（5秒）: フォロー促進テキストを表示。

    Args:
        bg:    背景クリップ。
        color: アクセントカラー。

    Returns:
        CompositeVideoClip。
    """
    d = float(SEC_OUTRO)
    text = "🔔 フォローして\n毎日チェック！"
    follow_clip = _make_text_clip(text, 80, color, duration=d)
    follow_pos  = _center_clip(follow_clip, 0.5)

    return CompositeVideoClip([
        bg.with_duration(d),
        follow_pos.with_effects([vfx.FadeIn(0.5)]),
    ]).with_duration(d)


# ---------------------------------------------------------------------------
# 動画生成メイン
# ---------------------------------------------------------------------------

def generate_video(fortune: dict, slug: str, date: str) -> str:
    """1星座分の動画を生成して output/ に保存する。

    Args:
        fortune: 運勢データの辞書。
        slug:    星座スラッグ（ファイル名用）。
        date:    日付文字列（YYYY-MM-DD）。

    Returns:
        出力 MP4 ファイルのパス。
    """
    sign_name = fortune["sign"]
    print(f"🎬 {sign_name}の動画を生成中...")

    # アクセントカラー取得
    zodiac_info = next(z for z in ZODIAC_LIST if z["slug"] == slug)
    color = zodiac_info["color"]

    # 背景を各セクション用に用意（全編同じ画像）
    def bg(d: float) -> ImageClip:
        return _get_background_clip(slug, d)

    # 各セクション生成
    print("  📦 イントロ生成...")
    intro   = _make_intro(fortune, bg(SEC_INTRO), color)
    print("  📦 フック生成...")
    hook    = _make_hook(fortune, bg(SEC_HOOK), color)
    print("  📦 スコア生成...")
    score   = _make_score_section(fortune, bg(SEC_SCORE), color)
    print("  📦 ラッキー情報生成...")
    lucky   = _make_lucky(fortune, bg(SEC_LUCKY), color)
    print("  📦 メッセージ生成...")
    message = _make_message(fortune, bg(SEC_MESSAGE))
    print("  📦 アウトロ生成...")
    outro   = _make_outro(bg(SEC_OUTRO), color)

    # 結合
    print("  🔗 クリップを結合中...")
    video = concatenate_videoclips([intro, hook, score, lucky, message, outro])

    # BGM 追加
    bgm = _load_bgm(video.duration)
    if bgm:
        print("  🎵 BGM を追加中...")
        video = video.with_audio(bgm)
    else:
        print("  🔇 BGM なしで続行します")

    # 出力
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, f"{slug}_{date}.mp4")
    print(f"  💾 書き出し中: {output_path}")
    video.write_videofile(
        output_path,
        fps=VIDEO_FPS,
        codec="libx264",
        audio_codec="aac",
        logger="bar",
    )

    print(f"✅ 完了: {output_path}")
    return output_path


# ---------------------------------------------------------------------------
# CLI エントリーポイント
# ---------------------------------------------------------------------------

def _today_jst() -> str:
    """JST の今日の日付を YYYY-MM-DD 形式で返す。"""
    jst = timezone(timedelta(hours=9))
    return datetime.now(jst).strftime("%Y-%m-%d")


def main() -> None:
    """コマンドライン引数を解析して動画を生成する。"""
    parser = argparse.ArgumentParser(description="占い動画生成（MoviePy）")
    parser.add_argument("--sign", required=True, help="星座名（日本語）例: おひつじ座")
    parser.add_argument("--date", default=_today_jst(), help="日付 YYYY-MM-DD（省略時: 今日）")
    args = parser.parse_args()

    # 星座情報を取得
    zodiac = next((z for z in ZODIAC_LIST if z["name"] == args.sign), None)
    if zodiac is None:
        names = ", ".join(z["name"] for z in ZODIAC_LIST)
        print(f"❌ 星座名が不正です: {args.sign}\n使用可能: {names}")
        sys.exit(1)

    # 運勢データ取得
    fortune = get_fortune_for_sign(args.date, args.sign)
    if fortune is None:
        print(
            f"❌ {args.date} の {args.sign} の運勢データが見つかりません。\n"
            f"先に python generate_fortune.py --date {args.date} を実行してください。"
        )
        sys.exit(1)

    generate_video(fortune, zodiac["slug"], args.date)


if __name__ == "__main__":
    main()
