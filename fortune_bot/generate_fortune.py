"""
generate_fortune.py - Gemini API でタロットカード3択の運勢テキストを生成する。

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
from dotenv import load_dotenv

from config import CARD_CHOICES, OUTPUT_DIR, GEMINI_SLEEP_SEC

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

MODEL_NAME        = "gemini-2.0-flash"
MAX_RETRIES       = 2
RETRY_WAIT        = 15   # 通常リトライ間隔（秒）
RATE_LIMIT_WAIT   = 65   # 429 レート制限時の待機（秒）

TAROT_CARDS = [
    "愚者", "魔術師", "女教皇", "女帝", "皇帝", "教皇", "恋人", "戦車",
    "力", "隠者", "運命の輪", "正義", "吊られた男", "死神", "節制",
    "悪魔", "塔", "星", "月", "太陽", "審判", "世界",
]

JSON_SCHEMA = """{
  "card_label": "カードの選択肢（例: A）",
  "card": "タロットカード名（例: 太陽）",
  "card_orientation": "正位置 または 逆位置",
  "overall": "★★★★☆",
  "love": "★★★☆☆",
  "work": "★★★★★",
  "money": "★★★☆☆",
  "lucky_color": "色名",
  "lucky_item": "アイテム名",
  "message": "100文字程度のメッセージ（引いたカードの解釈を含む）",
  "hook": "15文字以内のキャッチコピー"
}"""

PROMPT_TEMPLATE = """あなたはプロのタロット占い師です。{date}に「カード{label}」を選んだ人の運勢を占います。
タロットの大アルカナ（{cards}）から1枚カードを引き、正位置か逆位置かを決めてください。
以下のJSON形式のみで出力してください。説明文・コードブロック不要。JSONのみ。
バズるSNS向けに「今日だけ」「見た人だけ」などの表現を自然に使ってください。
hookは15文字以内の強いキャッチコピーにしてください。
{json_schema}"""

# ---------------------------------------------------------------------------
# フォールバック用デフォルト値
# ---------------------------------------------------------------------------

_FALLBACK_CARDS = {
    "A": ("太陽", "正位置"),
    "B": ("月",   "正位置"),
    "C": ("星",   "正位置"),
}

def _make_fallback(card: dict, date: str) -> dict:
    """JSON パース失敗時のフォールバックデータを生成する。"""
    tarot_card, orient = _FALLBACK_CARDS.get(card["label"], ("星", "正位置"))
    return {
        "card_label":       card["label"],
        "card":             tarot_card,
        "card_orientation": orient,
        "overall":          "★★★☆☆",
        "love":             "★★★☆☆",
        "work":             "★★★☆☆",
        "money":            "★★★☆☆",
        "lucky_color":      "ホワイト",
        "lucky_item":       "水晶",
        "message":          f"「{tarot_card}」のカードがあなたに届いています。今日は内なる声に耳を傾けて。",
        "hook":             f"{tarot_card}のカードが導く",
    }


# ---------------------------------------------------------------------------
# Gemini API 呼び出し
# ---------------------------------------------------------------------------

def _call_gemini(client: genai.Client, prompt: str) -> str:
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
    )
    return response.text


def _parse_fortune_json(text: str, card: dict, date: str) -> dict:
    """Gemini の出力テキストから運勢 JSON を抽出・パースする。"""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        cleaned = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    start = cleaned.find("{")
    end   = cleaned.rfind("}") + 1
    if start != -1 and end > start:
        cleaned = cleaned[start:end]

    try:
        data = json.loads(cleaned)
        required = ["card_label", "card", "card_orientation", "overall", "love", "work", "money",
                    "lucky_color", "lucky_item", "message", "hook"]
        for key in required:
            if key not in data:
                data[key] = _make_fallback(card, date)[key]
        if len(data.get("hook", "")) > 20:
            data["hook"] = data["hook"][:20]
        return data
    except json.JSONDecodeError as e:
        print(f"  ⚠️  JSON パース失敗（カード{card['label']}）: {e}。フォールバックを使用します")
        return _make_fallback(card, date)


def generate_fortune_for_card(
    client: genai.Client,
    card: dict,
    date: str,
) -> dict:
    """1カード分の運勢を生成する（最大 MAX_RETRIES 回リトライ）。"""
    prompt = PROMPT_TEMPLATE.format(
        date=date,
        label=card["label"],
        cards="・".join(TAROT_CARDS),
        json_schema=JSON_SCHEMA,
    )

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            text = _call_gemini(client, prompt)
            return _parse_fortune_json(text, card, date)
        except Exception as e:
            err_str = str(e)
            is_rate_limit = "429" in err_str or "RESOURCE_EXHAUSTED" in err_str
            wait = RATE_LIMIT_WAIT if is_rate_limit else RETRY_WAIT
            print(f"  ⚠️  [カード{card['label']}] 試行 {attempt}/{MAX_RETRIES} 失敗: {e}")
            if attempt < MAX_RETRIES:
                print(f"  ⏳ {wait}秒待機{'（レート制限）' if is_rate_limit else ''}中...")
                time.sleep(wait)

    print(f"  ❌  [カード{card['label']}] すべてのリトライが失敗。フォールバックを使用します")
    fb = _make_fallback(card, date)
    fb["_fallback"] = True
    return fb


# ---------------------------------------------------------------------------
# メイン処理
# ---------------------------------------------------------------------------

def generate_all_fortunes(date: str) -> list[dict]:
    """全3カードの運勢を生成して JSON ファイルに保存する。"""
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key or api_key == "your_gemini_api_key_here":
        raise ValueError(
            "GEMINI_API_KEY が設定されていません。\n"
            ".env に GEMINI_API_KEY=<your_key> を追加してください。"
        )

    client = genai.Client(api_key=api_key)
    fortunes: list[dict] = []

    print(f"🔮 {date} のタロット占いテキストを生成中...")
    fallback_count = 0
    for i, card in enumerate(CARD_CHOICES):
        print(f"  [{i + 1:02d}/03] カード{card['label']} ...", end=" ", flush=True)
        fortune = generate_fortune_for_card(client, card, date)
        if fortune.get("_fallback"):
            fallback_count += 1
        else:
            fortune.pop("_fallback", None)
        fortunes.append(fortune)
        print(f"完了（hook: {fortune['hook'][:15]}）")

        if i < len(CARD_CHOICES) - 1:
            time.sleep(GEMINI_SLEEP_SEC)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, f"fortune_{date}.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(fortunes, f, ensure_ascii=False, indent=2)

    success_count = len(CARD_CHOICES) - fallback_count
    print(f"\n{'=' * 40}")
    print(f"✅ API成功: {success_count}/3  ⚠️ フォールバック: {fallback_count}/3")
    print(f"保存完了: {output_path}")
    print(f"{'=' * 40}")

    if fallback_count == len(CARD_CHOICES):
        print("⚠️  全カードがAPIエラーのためフォールバックを使用しました。GEMINI_API_KEYとモデル名を確認してください。")
        print("⚠️  フォールバックデータで動画生成を続行します。")
        sys.exit(2)

    return fortunes


def load_fortunes(date: str) -> list[dict]:
    """保存済みの運勢 JSON を読み込む。"""
    path = os.path.join(OUTPUT_DIR, f"fortune_{date}.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def get_fortune_for_card(date: str, card_label: str) -> dict | None:
    """指定カードの運勢データを取得する。"""
    try:
        fortunes = load_fortunes(date)
        return next((f for f in fortunes if f["card_label"] == card_label), None)
    except FileNotFoundError:
        return None


# ---------------------------------------------------------------------------
# CLI エントリーポイント
# ---------------------------------------------------------------------------

def _today_jst() -> str:
    jst = timezone(timedelta(hours=9))
    return datetime.now(jst).strftime("%Y-%m-%d")


def main() -> None:
    parser = argparse.ArgumentParser(description="タロット占いテキスト生成（Gemini API）")
    parser.add_argument("--date", default=_today_jst(), help="日付 YYYY-MM-DD（省略時: 今日）")
    args = parser.parse_args()
    generate_all_fortunes(args.date)


if __name__ == "__main__":
    main()
