"""
generate_fortune.py - Gemini API で12星座の運勢テキストを生成する。

使い方:
    python generate_fortune.py
    python generate_fortune.py --date 2025-01-01
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from google import genai
from google.genai import types as genai_types
from dotenv import load_dotenv

from config import ZODIAC_LIST, OUTPUT_DIR, GEMINI_SLEEP_SEC

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

MODEL_NAME   = "gemini-2.0-flash"
MAX_RETRIES  = 3
RETRY_WAIT   = 10  # リトライ間隔（秒）

JSON_SCHEMA = """{
  "sign": "星座名（日本語）",
  "emoji": "絵文字",
  "overall": "★★★★☆",
  "love": "★★★☆☆",
  "work": "★★★★★",
  "money": "★★★☆☆",
  "lucky_color": "色名",
  "lucky_item": "アイテム名",
  "message": "100文字程度のメッセージ",
  "hook": "15文字以内のキャッチコピー"
}"""

PROMPT_TEMPLATE = """あなたはプロの占い師です。{date}の{sign}の運勢を以下のJSON形式のみで出力してください。
説明文・コードブロック不要。JSONのみ。
バズるSNS向けに「今日だけ」「見た人だけ」などの表現を自然に使ってください。
hookは15文字以内の強いキャッチコピーにしてください。
{json_schema}"""

# ---------------------------------------------------------------------------
# フォールバック用デフォルト値
# ---------------------------------------------------------------------------

def _make_fallback(zodiac: dict, date: str) -> dict:
    """JSON パース失敗時のフォールバックデータを生成する。

    Args:
        zodiac: ZODIAC_LIST の1要素。
        date:   日付文字列（YYYY-MM-DD）。

    Returns:
        運勢データの辞書。
    """
    return {
        "sign":        zodiac["name"],
        "emoji":       zodiac["emoji"],
        "overall":     "★★★☆☆",
        "love":        "★★★☆☆",
        "work":        "★★★☆☆",
        "money":       "★★★☆☆",
        "lucky_color": "ホワイト",
        "lucky_item":  "水晶",
        "message":     f"{date}の{zodiac['name']}は穏やかな一日です。焦らず着実に進みましょう。",
        "hook":        "今日も運気上昇中",
    }


# ---------------------------------------------------------------------------
# Gemini API 呼び出し
# ---------------------------------------------------------------------------

def _call_gemini(client: genai.Client, prompt: str) -> str:
    """Gemini API を呼び出してテキストを返す。

    Args:
        client: google.genai.Client インスタンス。
        prompt: 送信するプロンプト文字列。

    Returns:
        生成されたテキスト。

    Raises:
        Exception: API 呼び出しに失敗した場合。
    """
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
    )
    return response.text


def _parse_fortune_json(text: str, zodiac: dict, date: str) -> dict:
    """Gemini の出力テキストから運勢 JSON を抽出・パースする。

    コードブロック（```json ... ```）があれば除去してからパースする。
    失敗時はフォールバック値を返す。

    Args:
        text:   Gemini の生成テキスト。
        zodiac: ZODIAC_LIST の1要素。
        date:   日付文字列。

    Returns:
        パースした運勢データの辞書。
    """
    # コードブロック除去
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        cleaned = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    # JSON 部分を抜き出す（{ から } まで）
    start = cleaned.find("{")
    end   = cleaned.rfind("}") + 1
    if start != -1 and end > start:
        cleaned = cleaned[start:end]

    try:
        data = json.loads(cleaned)
        # 必須キーが揃っているか検証
        required = ["sign", "emoji", "overall", "love", "work", "money",
                    "lucky_color", "lucky_item", "message", "hook"]
        for key in required:
            if key not in data:
                data[key] = _make_fallback(zodiac, date)[key]
        # hook が長すぎる場合はトリム
        if len(data.get("hook", "")) > 20:
            data["hook"] = data["hook"][:20]
        return data
    except json.JSONDecodeError as e:
        print(f"  ⚠️  JSON パース失敗（{zodiac['name']}）: {e}。フォールバックを使用します")
        return _make_fallback(zodiac, date)


def generate_fortune_for_sign(
    client: genai.Client,
    zodiac: dict,
    date: str,
) -> dict:
    """1星座分の運勢を生成する（最大 MAX_RETRIES 回リトライ）。

    Args:
        client: google.genai.Client インスタンス。
        zodiac: ZODIAC_LIST の1要素。
        date:   日付文字列（YYYY-MM-DD）。

    Returns:
        運勢データの辞書。
    """
    prompt = PROMPT_TEMPLATE.format(
        date=date,
        sign=zodiac["name"],
        json_schema=JSON_SCHEMA,
    )

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            text = _call_gemini(client, prompt)
            fortune = _parse_fortune_json(text, zodiac, date)
            return fortune
        except Exception as e:
            print(f"  ⚠️  [{zodiac['name']}] 試行 {attempt}/{MAX_RETRIES} 失敗: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_WAIT)

    print(f"  ❌  [{zodiac['name']}] すべてのリトライが失敗。フォールバックを使用します")
    fb = _make_fallback(zodiac, date)
    fb["_fallback"] = True
    return fb


# ---------------------------------------------------------------------------
# メイン処理
# ---------------------------------------------------------------------------

def generate_all_fortunes(date: str) -> list[dict]:
    """全12星座の運勢を生成して JSON ファイルに保存する。

    Args:
        date: 日付文字列（YYYY-MM-DD）。

    Returns:
        12星座分の運勢データのリスト。
    """
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key or api_key == "your_gemini_api_key_here":
        raise ValueError(
            "GEMINI_API_KEY が設定されていません。\n"
            ".env に GEMINI_API_KEY=<your_key> を追加してください。"
        )

    client = genai.Client(api_key=api_key)

    fortunes: list[dict] = []

    print(f"🔮 {date} の占いテキストを生成中...")
    fallback_count = 0
    for i, zodiac in enumerate(ZODIAC_LIST):
        print(f"  [{i + 1:02d}/12] {zodiac['name']} ...", end=" ", flush=True)
        fortune = generate_fortune_for_sign(client, zodiac, date)
        if fortune.pop("_fallback", False):
            fallback_count += 1
        fortunes.append(fortune)
        print(f"完了（hook: {fortune['hook'][:15]}）")

        # レート制限対策：最後の星座以外は sleep
        if i < len(ZODIAC_LIST) - 1:
            time.sleep(GEMINI_SLEEP_SEC)

    # JSON ファイルに保存
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, f"fortune_{date}.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(fortunes, f, ensure_ascii=False, indent=2)

    # サマリー
    success_count = len(ZODIAC_LIST) - fallback_count
    print(f"\n{'=' * 40}")
    print(f"✅ API成功: {success_count}/12  ⚠️ フォールバック: {fallback_count}/12")
    print(f"保存完了: {output_path}")
    print(f"{'=' * 40}")

    if fallback_count == len(ZODIAC_LIST):
        print("❌ 全星座がAPIエラーのためフォールバックを使用しました。GEMINI_API_KEYとモデル名を確認してください。")
        sys.exit(1)

    return fortunes


def load_fortunes(date: str) -> list[dict]:
    """保存済みの運勢 JSON を読み込む。

    Args:
        date: 日付文字列（YYYY-MM-DD）。

    Returns:
        運勢データのリスト。

    Raises:
        FileNotFoundError: ファイルが存在しない場合。
    """
    path = os.path.join(OUTPUT_DIR, f"fortune_{date}.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def get_fortune_for_sign(date: str, sign_name: str) -> dict | None:
    """指定星座の運勢データを取得する。

    Args:
        date:      日付文字列（YYYY-MM-DD）。
        sign_name: 星座名（日本語）。

    Returns:
        運勢データの辞書。見つからない場合は None。
    """
    try:
        fortunes = load_fortunes(date)
        return next((f for f in fortunes if f["sign"] == sign_name), None)
    except FileNotFoundError:
        return None


# ---------------------------------------------------------------------------
# CLI エントリーポイント
# ---------------------------------------------------------------------------

def _today_jst() -> str:
    """JST の今日の日付を YYYY-MM-DD 形式で返す。"""
    jst = timezone(timedelta(hours=9))
    return datetime.now(jst).strftime("%Y-%m-%d")


def main() -> None:
    """コマンドライン引数を解析して実行する。"""
    parser = argparse.ArgumentParser(description="占いテキスト生成（Gemini API）")
    parser.add_argument("--date", default=_today_jst(), help="日付 YYYY-MM-DD（省略時: 今日）")
    args = parser.parse_args()

    generate_all_fortunes(args.date)


if __name__ == "__main__":
    main()
