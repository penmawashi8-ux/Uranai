"""
card_generator.py - カード画像生成（PIL不使用、numpy+標準ライブラリのみ）

ImageMagick も numpy+zlib も使えるが、ここでは numpy で直接ピクセルを操作して
PNG ファイルを書き出す方式を採用する。
"""

from __future__ import annotations

import math
import struct
import zlib
import os

import numpy as np


# ---------------------------------------------------------------------------
# PNG 書き出しユーティリティ
# ---------------------------------------------------------------------------


def _make_png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    c = chunk_type + data
    return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)


def write_png(path: str, arr: np.ndarray) -> None:
    """H×W×3 の uint8 numpy 配列を PNG ファイルに保存する（PIL 不使用）。"""
    h, w = arr.shape[:2]
    raw = b"".join(b"\x00" + row.tobytes() for row in arr.astype(np.uint8))
    with open(path, "wb") as f:
        f.write(
            b"\x89PNG\r\n\x1a\n"
            + _make_png_chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + _make_png_chunk(b"IDAT", zlib.compress(raw, 9))
            + _make_png_chunk(b"IEND", b"")
        )


# ---------------------------------------------------------------------------
# 色ユーティリティ
# ---------------------------------------------------------------------------


def _hex(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _clamp(v: int) -> int:
    return max(0, min(255, v))


# ---------------------------------------------------------------------------
# 基本描画プリミティブ
# ---------------------------------------------------------------------------


def _set(arr: np.ndarray, x: int, y: int, color: tuple | np.ndarray) -> None:
    h, w = arr.shape[:2]
    if 0 <= x < w and 0 <= y < h:
        arr[y, x] = np.array(color, dtype=np.uint8)


def draw_rect_border(
    arr: np.ndarray,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    color: tuple,
    thickness: int = 2,
) -> None:
    c = np.array(color, dtype=np.uint8)
    h, w = arr.shape[:2]
    for t in range(thickness):
        y_top = y1 + t
        y_bot = y2 - t
        x_left = x1 + t
        x_right = x2 - t
        if 0 <= y_top < h:
            arr[y_top, max(0, x1) : min(w, x2 + 1)] = c
        if 0 <= y_bot < h:
            arr[y_bot, max(0, x1) : min(w, x2 + 1)] = c
        if 0 <= x_left < w:
            arr[max(0, y1) : min(h, y2 + 1), x_left] = c
        if 0 <= x_right < w:
            arr[max(0, y1) : min(h, y2 + 1), x_right] = c


def fill_polygon(arr: np.ndarray, points: list[tuple], color: tuple) -> None:
    """スキャンライン法でポリゴンを塗りつぶす。"""
    if not points:
        return
    c = np.array(color, dtype=np.uint8)
    h, w = arr.shape[:2]
    n = len(points)
    min_y = max(0, int(min(p[1] for p in points)))
    max_y = min(h - 1, int(max(p[1] for p in points)))

    for y in range(min_y, max_y + 1):
        xs: list[float] = []
        for i in range(n):
            x1, y1 = points[i]
            x2, y2 = points[(i + 1) % n]
            if (y1 <= y < y2) or (y2 <= y < y1):
                if y2 != y1:
                    xs.append(x1 + (y - y1) * (x2 - x1) / (y2 - y1))
        xs.sort()
        for j in range(0, len(xs) - 1, 2):
            x_s = max(0, int(xs[j]))
            x_e = min(w - 1, int(xs[j + 1]))
            if x_s <= x_e:
                arr[y, x_s : x_e + 1] = c


def draw_star(
    arr: np.ndarray,
    cx: float,
    cy: float,
    outer_r: float,
    color: tuple,
    inner_r: float | None = None,
) -> None:
    if inner_r is None:
        inner_r = outer_r / 2.5
    pts = []
    for i in range(10):
        angle = math.pi * i / 5 - math.pi / 2
        r = outer_r if i % 2 == 0 else inner_r
        pts.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    fill_polygon(arr, pts, color)


def draw_circle_filled(
    arr: np.ndarray, cx: float, cy: float, r: float, color: tuple
) -> None:
    c = np.array(color, dtype=np.uint8)
    h, w = arr.shape[:2]
    y_min = max(0, int(cy - r))
    y_max = min(h - 1, int(cy + r))
    x_min = max(0, int(cx - r))
    x_max = min(w - 1, int(cx + r))
    Y, X = np.ogrid[y_min : y_max + 1, x_min : x_max + 1]
    mask = (X - cx) ** 2 + (Y - cy) ** 2 <= r ** 2
    arr[y_min : y_max + 1, x_min : x_max + 1][mask] = c


def draw_circle_outline(
    arr: np.ndarray, cx: float, cy: float, r: float, color: tuple, thickness: int = 3
) -> None:
    h, w = arr.shape[:2]
    c = np.array(color, dtype=np.uint8)
    for t in range(thickness):
        ri = r - t
        if ri <= 0:
            continue
        steps = max(360, int(2 * math.pi * ri * 2))
        for step in range(steps):
            angle = 2 * math.pi * step / steps
            x = int(cx + ri * math.cos(angle))
            y = int(cy + ri * math.sin(angle))
            if 0 <= x < w and 0 <= y < h:
                arr[y, x] = c


# ---------------------------------------------------------------------------
# シンボル描画
# ---------------------------------------------------------------------------


def _draw_symbol(arr: np.ndarray, cx: int, cy: int, symbol: str, color: tuple) -> None:
    h, w = arr.shape[:2]
    c = np.array(color, dtype=np.uint8)

    if symbol == "star":
        draw_star(arr, cx, cy, 42, color)

    elif symbol == "moon":
        outer_r = 34
        # 外円 - 内円（クレッセント）
        for y in range(max(0, cy - outer_r), min(h, cy + outer_r + 1)):
            for x in range(max(0, cx - outer_r), min(w, cx + outer_r + 1)):
                in_outer = (x - cx) ** 2 + (y - cy) ** 2 <= outer_r ** 2
                ox, oy = cx + int(outer_r * 0.35), cy
                in_inner = (x - ox) ** 2 + (y - oy) ** 2 <= int(outer_r * 0.78) ** 2
                if in_outer and not in_inner:
                    arr[y, x] = c

    elif symbol == "sun":
        draw_circle_filled(arr, cx, cy, 22, color)
        for deg in range(0, 360, 30):
            angle = math.radians(deg)
            for r in range(28, 43):
                px = int(cx + r * math.cos(angle))
                py = int(cy + r * math.sin(angle))
                if 0 <= px < w and 0 <= py < h:
                    arr[py, px] = c
                px2 = int(cx + r * math.cos(angle + 0.08))
                py2 = int(cy + r * math.sin(angle + 0.08))
                if 0 <= px2 < w and 0 <= py2 < h:
                    arr[py2, px2] = c

    elif symbol == "butterfly":
        draw_circle_filled(arr, cx - 20, cy - 6, 17, color)
        draw_circle_filled(arr, cx + 20, cy - 6, 17, color)
        wing2 = (_clamp(color[0] - 30), _clamp(color[1] - 20), _clamp(color[2]))
        draw_circle_filled(arr, cx - 14, cy + 14, 12, wing2)
        draw_circle_filled(arr, cx + 14, cy + 14, 12, wing2)
        # 体
        for y in range(cy - 22, cy + 22):
            for x in range(cx - 2, cx + 3):
                if 0 <= x < w and 0 <= y < h:
                    arr[y, x] = np.array((50, 30, 20), dtype=np.uint8)

    elif symbol == "key":
        draw_circle_outline(arr, cx, cy - 14, 17, color, thickness=5)
        for y in range(cy + 3, cy + 38):
            for x in range(cx - 3, cx + 4):
                if 0 <= x < w and 0 <= y < h:
                    arr[y, x] = c
        for ty_base in (cy + 18, cy + 27):
            for x in range(cx + 3, cx + 13):
                for ty in range(ty_base, ty_base + 5):
                    if 0 <= x < w and 0 <= ty < h:
                        arr[ty, x] = c

    elif symbol == "hourglass":
        gold_dark = (
            _clamp(color[0] - 30),
            _clamp(color[1] - 20),
            _clamp(color[2]),
        )
        fill_polygon(arr, [(cx - 24, cy - 32), (cx + 24, cy - 32), (cx, cy)], color)
        fill_polygon(arr, [(cx, cy), (cx - 24, cy + 32), (cx + 24, cy + 32)], gold_dark)
        for x in range(cx - 24, cx + 25):
            for t in range(3):
                for yy in (cy - 32 + t, cy + 32 - t):
                    if 0 <= x < w and 0 <= yy < h:
                        arr[yy, x] = c

    elif symbol == "feather":
        for i in range(65):
            t = i / 64.0
            px = int(cx - 14 + 20 * t)
            py = int(cy - 30 + 58 * t)
            for dx in range(-1, 2):
                if 0 <= px + dx < w and 0 <= py < h:
                    arr[py, px + dx] = c
            barb = int(14 * math.sin(math.pi * t))
            for b in range(1, barb + 1):
                for bx, by in ((px - b, py - b // 2), (px + b, py - b // 2)):
                    if 0 <= bx < w and 0 <= by < h:
                        arr[by, bx] = c

    elif symbol == "flame":
        for y_off in range(-36, 22):
            y = cy + y_off
            if y < 0 or y >= h:
                continue
            t = (y_off + 36) / 58.0  # 0 = top, 1 = bottom
            if t < 0.25:
                w_half = int(4 * t / 0.25)
            elif t < 0.55:
                w_half = int(4 + 14 * (t - 0.25) / 0.3)
            else:
                w_half = int(18 - 10 * (t - 0.55) / 0.45)
            for x in range(cx - w_half, cx + w_half + 1):
                if 0 <= x < w:
                    if t < 0.35:
                        px_color = (255, _clamp(int(230 - 60 * t / 0.35)), 40)
                    elif t < 0.65:
                        px_color = (255, _clamp(int(130 - 80 * (t - 0.35) / 0.3)), 0)
                    else:
                        px_color = (_clamp(int(255 - 55 * (t - 0.65) / 0.35)), 50, 0)
                    arr[y, x] = np.array(px_color, dtype=np.uint8)

    elif symbol == "droplet":
        draw_circle_filled(arr, cx, cy + 10, 21, color)
        fill_polygon(
            arr,
            [(cx, cy - 34), (cx - 9, cy - 4), (cx + 9, cy - 4)],
            color,
        )

    elif symbol == "heart":
        # 上部2つの円 + 下部V字三角形
        draw_circle_filled(arr, cx - 13, cy - 6, 16, color)
        draw_circle_filled(arr, cx + 13, cy - 6, 16, color)
        fill_polygon(
            arr,
            [(cx - 28, cy - 4), (cx + 28, cy - 4), (cx, cy + 24)],
            color,
        )

    else:
        draw_star(arr, cx, cy, 42, color)


# ---------------------------------------------------------------------------
# カード生成
# ---------------------------------------------------------------------------


def generate_card_back(width: int = 200, height: int = 320) -> np.ndarray:
    """カード裏面の numpy 配列（H×W×3）を生成する。"""
    bg = _hex("#1A1040")
    arr = np.full((height, width, 3), bg, dtype=np.uint8)

    gold = _hex("#C8A84B")
    purple = _hex("#5A3080")

    cx, cy = width // 2, height // 2

    # 背景の幾何学模様（菱形グリッド）
    for dy in range(-4, 5):
        for dx in range(-3, 4):
            gx = cx + dx * 44
            gy = cy + dy * 44
            size = 14
            for i in range(-size, size + 1):
                for xi, yi in ((i, size - abs(i)), (i, -(size - abs(i)))):
                    px, py = gx + xi, gy + yi
                    if 14 <= px < width - 14 and 14 <= py < height - 14:
                        arr[py, px] = np.array(purple, dtype=np.uint8)

    # 外枠
    draw_rect_border(arr, 4, 4, width - 5, height - 5, gold, 2)
    draw_rect_border(arr, 9, 9, width - 10, height - 10, gold, 1)

    # 星の装飾
    draw_star(arr, cx, cy, 18, gold)
    for sx, sy, sr in [
        (cx, cy - 76, 10),
        (cx, cy + 76, 10),
        (cx - 55, cy, 8),
        (cx + 55, cy, 8),
        (cx - 44, cy - 55, 6),
        (cx + 44, cy - 55, 6),
        (cx - 44, cy + 55, 6),
        (cx + 44, cy + 55, 6),
    ]:
        draw_star(arr, sx, sy, sr, gold)

    return arr


def generate_card_front(
    title: str,
    symbol: str,
    rank: int,
    width: int = 200,
    height: int = 320,
) -> np.ndarray:
    """カード表面の numpy 配列（H×W×3）を生成する。"""
    bg = _hex("#F5E6C8")
    arr = np.full((height, width, 3), bg, dtype=np.uint8)

    gold = _hex("#C8A84B")

    # ランク1は金色ウォッシュ背景
    if rank == 1:
        wash = _hex("#FEF3DC")
        arr[12:height - 12, 12:width - 12] = np.array(wash, dtype=np.uint8)

    # ダブルボーダー
    draw_rect_border(arr, 4, 4, width - 5, height - 5, gold, 3)
    draw_rect_border(arr, 10, 10, width - 11, height - 11, gold, 1)

    # ランク1の場合は輝くゴールドボーダーを追加
    if rank == 1:
        bright_gold = _hex("#F0D060")
        draw_rect_border(arr, 13, 13, width - 14, height - 14, bright_gold, 2)

    # シンボル描画（上下中央より少し上）
    _draw_symbol(arr, width // 2, height // 2 - 22, symbol, gold)

    return arr


# ---------------------------------------------------------------------------
# テスト用 CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import os

    os.makedirs("output", exist_ok=True)

    back = generate_card_back()
    write_png("output/test_card_back.png", back)
    print("Saved output/test_card_back.png")

    for sym in ["star", "moon", "sun", "butterfly", "key", "hourglass",
                "feather", "flame", "droplet", "heart"]:
        front = generate_card_front(sym, sym, 1)
        write_png(f"output/test_card_{sym}.png", front)
    print("Saved output/test_card_*.png")
