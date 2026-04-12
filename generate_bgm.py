"""
generate_bgm.py - numpy のみで占い向けBGMを合成する

外部ファイル・ライブラリ不要。
日付シードで5パターンからランダムに選択し、毎日異なるBGMを生成する。

パターン:
  1. 神秘  - Aマイナーペンタトニック、ベルトーン多め、幽玄
  2. 幻想  - Cメジャーペンタトニック、明るく温かみのある
  3. 静寂  - Dマイナー、ゆっくり深呼吸するような穏やか
  4. 力強  - Eマイナー、力強いアルペジオでドラマチック
  5. 温か  - Gメジャー、明るくほっとする
"""

from __future__ import annotations

import random
import numpy as np
from datetime import datetime

SAMPLE_RATE = 44100


# ──────────────────────────────────────────────
# 低レベル合成ユーティリティ
# ──────────────────────────────────────────────

def _sine(freq: float, t: np.ndarray, amp: float = 1.0) -> np.ndarray:
    return np.sin(2 * np.pi * freq * t) * amp


def _make_tone(
    freq: float,
    duration: float,
    amplitude: float = 0.3,
    harmonics: list[tuple[float, float]] | None = None,
    attack_ratio: float = 0.08,
    release_ratio: float = 0.35,
) -> np.ndarray:
    """倍音付きサイン波トーンをADSRエンベロープで生成する。"""
    n = int(SAMPLE_RATE * duration)
    if n <= 0:
        return np.zeros(1)
    t = np.linspace(0, duration, n, endpoint=False)

    wave = _sine(freq, t, 0.6)
    if harmonics:
        for ratio, amp in harmonics:
            wave += _sine(freq * ratio, t, amp)

    attack  = int(SAMPLE_RATE * min(attack_ratio, duration * 0.15))
    release = int(SAMPLE_RATE * min(release_ratio, duration * 0.4))
    env = np.ones(n)
    if attack > 0:
        env[:attack] = np.linspace(0, 1, attack)
    if release > 0 and n > release:
        env[-release:] = np.linspace(0.8, 0, release)

    return wave * env * amplitude


def _add_at(buf: np.ndarray, start_sec: float, wave: np.ndarray) -> None:
    """buf の start_sec 秒位置に wave を加算する。"""
    start = int(start_sec * SAMPLE_RATE)
    end   = min(start + len(wave), len(buf))
    length = end - start
    if length > 0:
        buf[start:end] += wave[:length]


def _drone(buf: np.ndarray, freq: float, amp: float = 0.15,
           vibrato_hz: float = 0.4, vibrato_depth: float = 0.004) -> None:
    """持続低音ドローンを buf に加算する。"""
    n = len(buf)
    t = np.linspace(0, n / SAMPLE_RATE, n, endpoint=False)
    vibrato = 1 + vibrato_depth * np.sin(2 * np.pi * vibrato_hz * t)
    d = (_sine(freq, t, 0.6) + _sine(freq * 2, t, 0.25) + _sine(freq * 3, t, 0.08)) * vibrato * amp
    buf += d


def _simple_reverb(audio: np.ndarray, delay_sec: float = 0.22,
                   gain: float = 0.26) -> np.ndarray:
    """2段階ディレイによる簡易リバーブ。"""
    result = audio.copy()
    d1 = int(delay_sec * SAMPLE_RATE)
    d2 = int(delay_sec * 1.8 * SAMPLE_RATE)
    if d1 < len(audio):
        result[d1:] += audio[: len(audio) - d1] * gain
    if d2 < len(audio):
        result[d2:] += audio[: len(audio) - d2] * gain * 0.35
    return result


def _arpeggio(buf: np.ndarray, note_freqs: list[float], note_dur: float,
              start_sec: float, amplitude: float,
              harmonics: list[tuple[float, float]],
              total_duration: float) -> None:
    """アルペジオパターンを buf に書き込む。"""
    t_pos = start_sec
    idx = 0
    while t_pos < total_duration - 1.0:
        freq = note_freqs[idx % len(note_freqs)]
        dur = min(note_dur + 0.05, total_duration - t_pos - 0.2)
        if dur <= 0.05:
            break
        wave = _make_tone(freq, dur, amplitude=amplitude, harmonics=harmonics)
        _add_at(buf, t_pos, wave)
        t_pos += note_dur
        idx += 1


def _pad_chords(buf: np.ndarray, chord_seq: list[list[float]],
                chord_dur: float, amplitude: float,
                total_duration: float) -> None:
    """パッドコードを一定間隔で buf に書き込む。"""
    ct, ci = 0.0, 0
    while ct < total_duration - 2.0:
        chord = chord_seq[ci % len(chord_seq)]
        remaining = min(chord_dur, total_duration - ct - 0.5)
        for freq in chord:
            wave = _make_tone(freq, remaining, amplitude=amplitude,
                              harmonics=[(2.0, 0.12), (3.0, 0.04)])
            _add_at(buf, ct, wave)
        ct += chord_dur
        ci += 1


def _bells(buf: np.ndarray, times: list[float], freqs: list[float],
           amplitude: float = 0.10, total_duration: float = 40.0) -> None:
    """ベルトーンを指定時刻に配置する。"""
    BELL_H = [(2.0, 0.30), (4.0, 0.10), (0.5, 0.04)]
    for bt, freq in zip(times, freqs):
        if bt >= total_duration:
            continue
        wave = _make_tone(freq, 1.5, amplitude=amplitude, harmonics=BELL_H,
                          attack_ratio=0.02, release_ratio=0.6)
        _add_at(buf, bt, wave)


def _finalize(mono: np.ndarray, fade_in: float = 2.0,
              fade_out: float = 3.5, target_amp: float = 0.72) -> np.ndarray:
    """リバーブ・フェード・ノーマライズ・ステレオ化を行う。"""
    mono = _simple_reverb(mono)
    fi = min(int(fade_in  * SAMPLE_RATE), len(mono))
    fo = min(int(fade_out * SAMPLE_RATE), len(mono))
    mono[:fi] *= np.linspace(0, 1, fi)
    if fo > 0:
        mono[-fo:] *= np.linspace(1, 0, fo)
    peak = np.max(np.abs(mono))
    if peak > 0:
        mono = mono / peak * target_amp
    # ステレオ（3ms 位相差でひろがり感）
    d = int(0.003 * SAMPLE_RATE)
    right = np.zeros_like(mono)
    right[d:] = mono[:-d]
    return np.column_stack([mono, right]).astype(np.float32)


# ──────────────────────────────────────────────
# BGM パターン 5 種
# ──────────────────────────────────────────────

def _bgm_shinpi(duration: float) -> np.ndarray:
    """パターン1: 神秘 — Aマイナーペンタトニック、ベルトーン多め、幽玄。"""
    total = int(SAMPLE_RATE * duration)
    mono  = np.zeros(total)

    _drone(mono, 110.00, amp=0.18)  # A2

    arp_notes = [220.00, 261.63, 329.63, 440.00, 523.25,  # A3 C4 E4 A4 C5
                 659.26, 523.25, 440.00, 329.63, 261.63]  # E5 C5 A4 E4 C4
    _arpeggio(mono, arp_notes, note_dur=0.70, start_sec=0.5,
              amplitude=0.14, harmonics=[(2.0, 0.18), (3.0, 0.07), (0.5, 0.04)],
              total_duration=duration)

    chords = [
        [220.00, 329.63, 440.00],   # Am
        [196.00, 293.66, 392.00],   # G
        [261.63, 392.00, 523.25],   # C
        [220.00, 261.63, 329.63, 440.00],  # Am7
    ]
    _pad_chords(mono, chords, chord_dur=4.0, amplitude=0.055, total_duration=duration)

    bell_t = [3.0, 8.0, 14.0, 20.0, 27.0, 35.0]
    bell_f = [659.26, 523.25, 783.99, 659.26, 440.00, 783.99]
    _bells(mono, bell_t, bell_f, amplitude=0.10, total_duration=duration)

    return _finalize(mono)


def _bgm_genso(duration: float) -> np.ndarray:
    """パターン2: 幻想 — Cメジャーペンタトニック、明るく温かみのある。"""
    total = int(SAMPLE_RATE * duration)
    mono  = np.zeros(total)

    _drone(mono, 130.81, amp=0.14, vibrato_hz=0.3)  # C3

    # C メジャーペンタトニック: C D E G A
    arp_notes = [261.63, 293.66, 329.63, 392.00, 440.00,  # C4 D4 E4 G4 A4
                 523.25, 440.00, 392.00, 329.63, 261.63]
    _arpeggio(mono, arp_notes, note_dur=0.65, start_sec=0.8,
              amplitude=0.13, harmonics=[(2.0, 0.20), (3.0, 0.06)],
              total_duration=duration)

    chords = [
        [261.63, 329.63, 392.00],   # C
        [293.66, 369.99, 440.00],   # Dm
        [329.63, 392.00, 493.88],   # Em
        [261.63, 329.63, 523.25],   # C hi
    ]
    _pad_chords(mono, chords, chord_dur=4.5, amplitude=0.050, total_duration=duration)

    bell_t = [2.0, 6.0, 12.0, 20.0, 28.0, 36.0]
    bell_f = [523.25, 659.26, 523.25, 783.99, 659.26, 523.25]
    _bells(mono, bell_t, bell_f, amplitude=0.09, total_duration=duration)

    return _finalize(mono)


def _bgm_seijaku(duration: float) -> np.ndarray:
    """パターン3: 静寂 — Dマイナー、ゆっくり深呼吸するような穏やか。"""
    total = int(SAMPLE_RATE * duration)
    mono  = np.zeros(total)

    _drone(mono, 146.83, amp=0.16, vibrato_hz=0.25, vibrato_depth=0.003)  # D3

    # Dナチュラルマイナー: D E F G A Bb C
    arp_notes = [293.66, 349.23, 369.99, 440.00, 466.16,  # D4 F4 Fs4 A4 Bb4
                 587.33, 466.16, 440.00, 349.23, 293.66]
    _arpeggio(mono, arp_notes, note_dur=0.90, start_sec=1.0,
              amplitude=0.12, harmonics=[(2.0, 0.15), (3.0, 0.05), (0.5, 0.06)],
              total_duration=duration)

    chords = [
        [293.66, 349.23, 440.00],   # Dm
        [261.63, 329.63, 392.00],   # C
        [174.61, 261.63, 349.23],   # F
        [293.66, 369.99, 466.16],   # Dm7
    ]
    _pad_chords(mono, chords, chord_dur=5.0, amplitude=0.060, total_duration=duration)

    bell_t = [4.0, 10.0, 18.0, 25.0, 33.0]
    bell_f = [587.33, 440.00, 698.46, 587.33, 440.00]
    _bells(mono, bell_t, bell_f, amplitude=0.08, total_duration=duration)

    return _finalize(mono, fade_in=3.0, fade_out=4.0)


def _bgm_tsuyosa(duration: float) -> np.ndarray:
    """パターン4: 力強 — Eマイナー、力強いアルペジオでドラマチック。"""
    total = int(SAMPLE_RATE * duration)
    mono  = np.zeros(total)

    _drone(mono, 164.81, amp=0.20, vibrato_hz=0.5, vibrato_depth=0.005)  # E3

    # Eマイナーペンタトニック: E G A B D
    arp_notes = [164.81, 196.00, 220.00, 246.94, 293.66,  # E3 G3 A3 B3 D4
                 329.63, 392.00, 440.00, 493.88, 587.33,  # E4 G4 A4 B4 D5
                 587.33, 493.88, 440.00, 392.00, 329.63]
    _arpeggio(mono, arp_notes, note_dur=0.55, start_sec=0.3,
              amplitude=0.15, harmonics=[(2.0, 0.22), (3.0, 0.08), (4.0, 0.03)],
              total_duration=duration)

    chords = [
        [164.81, 246.94, 329.63],   # Em
        [196.00, 293.66, 392.00],   # G
        [146.83, 220.00, 293.66],   # Dsus2
        [164.81, 220.00, 329.63, 440.00],  # Em9
    ]
    _pad_chords(mono, chords, chord_dur=4.0, amplitude=0.060, total_duration=duration)

    bell_t = [3.0, 8.0, 12.0, 20.0, 30.0, 35.0]
    bell_f = [659.26, 783.99, 659.26, 987.77, 783.99, 659.26]
    _bells(mono, bell_t, bell_f, amplitude=0.11, total_duration=duration)

    return _finalize(mono, target_amp=0.75)


def _bgm_atataka(duration: float) -> np.ndarray:
    """パターン5: 温か — Gメジャー、明るくほっとする。"""
    total = int(SAMPLE_RATE * duration)
    mono  = np.zeros(total)

    _drone(mono, 195.99, amp=0.13, vibrato_hz=0.35, vibrato_depth=0.003)  # G3

    # Gメジャーペンタトニック: G A B D E
    arp_notes = [196.00, 220.00, 246.94, 293.66, 329.63,  # G3 A3 B3 D4 E4
                 392.00, 440.00, 493.88, 587.33, 659.26,  # G4 A4 B4 D5 E5
                 659.26, 587.33, 493.88, 440.00, 392.00]
    _arpeggio(mono, arp_notes, note_dur=0.60, start_sec=0.6,
              amplitude=0.12, harmonics=[(2.0, 0.20), (3.0, 0.06), (0.5, 0.03)],
              total_duration=duration)

    chords = [
        [196.00, 246.94, 293.66],   # G
        [220.00, 277.18, 329.63],   # Am
        [246.94, 293.66, 369.99],   # Bm
        [261.63, 329.63, 392.00],   # C
        [196.00, 246.94, 392.00],   # G hi
    ]
    _pad_chords(mono, chords, chord_dur=4.0, amplitude=0.048, total_duration=duration)

    bell_t = [2.5, 7.0, 13.0, 20.0, 28.0, 35.0]
    bell_f = [587.33, 659.26, 783.99, 587.33, 783.99, 987.77]
    _bells(mono, bell_t, bell_f, amplitude=0.09, total_duration=duration)

    return _finalize(mono, fade_in=1.5)


# ──────────────────────────────────────────────
# パブリックAPI
# ──────────────────────────────────────────────

_PATTERNS = [
    ("神秘",  _bgm_shinpi),
    ("幻想",  _bgm_genso),
    ("静寂",  _bgm_seijaku),
    ("力強",  _bgm_tsuyosa),
    ("温か",  _bgm_atataka),
]


def make_bgm(duration: float = 40.0,
             date: "datetime | None" = None) -> tuple[np.ndarray, str]:
    """
    日付から5パターンを完全ローテーション方式で選択して生成する。

    5日ごとにシャッフル順が変わる完全ローテーションにより
    連続して同じBGMが流れない設計。

    Returns:
        (stereo_array, pattern_name)
        stereo_array: shape=(N,2), dtype=float32
    """
    if date is None:
        date = datetime.now()

    n_pat = len(_PATTERNS)
    doy   = date.timetuple().tm_yday - 1   # 0-indexed
    group = doy // n_pat
    pos   = doy % n_pat
    rng   = random.Random(date.year * 1000 + group)
    order = list(range(n_pat))
    rng.shuffle(order)
    name, func = _PATTERNS[order[pos]]
    print(f"[INFO] BGMパターン: {name}")
    return func(duration), name


if __name__ == "__main__":
    # 動作確認: WAVファイルに書き出す
    import struct, zlib, io

    def write_wav(path: str, data: np.ndarray, sr: int = SAMPLE_RATE) -> None:
        """最小限のWAVライター（stdlib のみ）。"""
        mono16 = (data[:, 0] * 32767).astype(np.int16)
        pcm = mono16.tobytes()
        with open(path, "wb") as f:
            data_len = len(pcm)
            f.write(b"RIFF")
            f.write(struct.pack("<I", 36 + data_len))
            f.write(b"WAVEfmt ")
            f.write(struct.pack("<IHHIIHH", 16, 1, 1, sr, sr * 2, 2, 16))
            f.write(b"data")
            f.write(struct.pack("<I", data_len))
            f.write(pcm)

    arr, name = make_bgm(10.0)
    write_wav("/tmp/bgm_test.wav", arr)
    print(f"[OK] /tmp/bgm_test.wav に書き出しました（パターン: {name}）")
