"""
fortune_content.py - 運勢テキスト生成（日付ベースのシードでランダム）

使用方法:
    from fortune_content import get_fortune_cards, get_date_string
    cards = get_fortune_cards()  # 今日の占い
    cards = get_fortune_cards(datetime(2024, 1, 1))  # 特定日
"""

import random
from datetime import datetime

# ネガティブワード禁止リスト
NEGATIVE_WORDS = [
    "失敗", "悪い", "注意しすぎ", "危険", "落ち込む", "絶望", "挫折",
    "不安", "心配", "困難", "ダメ", "無理", "後悔", "辛い", "苦しい",
]

# カードプール定義
CARD_POOL = [
    {
        "id": "butterfly",
        "title": "縁",
        "symbol": "butterfly",
        "messages": [
            "思わぬ出会いや再会がありそうです。\n心を開いて新しい風を受け入れてみて。\nあなたの魅力が輝く一日になります。",
            "大切な縁が近づいてきています。\n素直な気持ちで人と接してみましょう。\n温かい繋がりが力になります。",
            "変化の中に喜びが潜んでいます。\n直感を信じて一歩踏み出してみて。\n新しい扉が開かれる予感があります。",
        ],
    },
    {
        "id": "star",
        "title": "希望",
        "symbol": "star",
        "messages": [
            "あなたの可能性は無限大に広がっています。\n今日は夢を語ることから始めましょう。\n輝く未来があなたを待っています。",
            "小さな光が道を照らしています。\n焦らず一歩ずつ進んでいきましょう。\n努力が実を結ぶ時が来ています。",
            "心の中の望みを大切にしてください。\n信じる力があなたの翼となります。\n今日という日が特別な始まりです。",
        ],
    },
    {
        "id": "moon",
        "title": "直感",
        "symbol": "moon",
        "messages": [
            "今日は内なる声に耳を傾けてみましょう。\n直感が正しい方向を示しています。\n静かな時間があなたに答えをくれます。",
            "感性が研ぎ澄まされている日です。\n芸術や音楽に触れると良いでしょう。\n心の豊かさが周囲を癒します。",
            "深い洞察力が発揮される一日です。\n物事の本質が見えてきています。\nあなたの知恵が周囲の助けになります。",
        ],
    },
    {
        "id": "sun",
        "title": "活力",
        "symbol": "sun",
        "messages": [
            "エネルギーに満ちた素晴らしい一日です。\n積極的に行動することで道が開けます。\n自信を持って前に進んでください。",
            "今日は特別なパワーが宿っています。\n新しいことにチャレンジする良い機会です。\nあなたの輝きが周囲を明るくします。",
            "成功のエネルギーが流れています。\n目標に向かって力強く歩みましょう。\n努力した分だけ報われる日になります。",
        ],
    },
    {
        "id": "key",
        "title": "機会",
        "symbol": "key",
        "messages": [
            "重要な扉が開こうとしています。\nチャンスを見逃さないよう準備しましょう。\n新しい可能性があなたを待っています。",
            "転換点となる出来事があるかもしれません。\n変化を恐れずに受け入れてみて。\nそれがあなたの成長のきっかけになります。",
            "隠れていたチャンスが現れる日です。\n好奇心を持って周囲を観察してみましょう。\nあなたの行動が未来を変えます。",
        ],
    },
    {
        "id": "hourglass",
        "title": "時",
        "symbol": "hourglass",
        "messages": [
            "積み重ねてきた努力が実る時が来ています。\n焦らず自分のペースを大切にしましょう。\n時間はあなたの味方です。",
            "今この瞬間を大切にする日です。\n小さな幸せに目を向けてみましょう。\n日々の積み重ねが宝になります。",
            "適切なタイミングが訪れようとしています。\n準備は十分整っています。\n自信を持って一歩踏み出しましょう。",
        ],
    },
    {
        "id": "feather",
        "title": "自由",
        "symbol": "feather",
        "messages": [
            "心が軽くなる出来事があるでしょう。\n重いものを手放す勇気を持ってみて。\n自由な発想があなたを輝かせます。",
            "自然の流れに身を委ねてみましょう。\n自分のペースで軽やかに過ごしましょう。\n本来の自分らしさが輝きを放ちます。",
            "創造的なアイデアが湧き出る日です。\n自由な発想で物事を見つめてみて。\nあなたの個性が力になります。",
        ],
    },
    {
        "id": "flame",
        "title": "情熱",
        "symbol": "flame",
        "messages": [
            "情熱の炎が燃え上がっています。\n心が求めることに素直に従いましょう。\n熱い気持ちが道を切り開きます。",
            "創造的なエネルギーが高まっています。\n好きなことに全力で取り組んでみて。\nあなたの熱意が周囲を巻き込みます。",
            "挑戦する意欲が湧いてくる一日です。\n目標に向かって燃えるような情熱を。\nその熱さがあなたの強みになります。",
        ],
    },
    {
        "id": "droplet",
        "title": "癒し",
        "symbol": "droplet",
        "messages": [
            "心と体を癒す時間を作りましょう。\n今日は自分を労ることが大切です。\n優しい気持ちが周囲にも広がります。",
            "感情を素直に表現することが大切です。\n感性豊かな一日になるでしょう。\n心の浄化が新しい力をくれます。",
            "人への思いやりが深まる日です。\n周囲の人を癒す言葉をかけてみて。\nあなたの優しさが戻ってきます。",
        ],
    },
    {
        "id": "heart",
        "title": "愛",
        "symbol": "heart",
        "messages": [
            "大切な人への感謝を伝える日です。\n素直な気持ちが関係を深めます。\n愛されている幸せを感じてください。",
            "自分自身を大切にすることが始まりです。\n心からの愛情があふれ出る日になります。\n周囲との絆がより強くなるでしょう。",
            "思いやりの気持ちが高まっています。\n誰かのために何かをすると喜びになります。\nその愛情があなたにも返ってきます。",
        ],
    },
]


def _validate_message(msg: str) -> bool:
    """ネガティブワードが含まれていないか確認する。"""
    for word in NEGATIVE_WORDS:
        if word in msg:
            return False
    return True


def get_fortune_cards(date: datetime | None = None) -> list[dict]:
    """
    日付ベースのシードで3枚のカードを選択して返す。

    Returns:
        [
            {"title": str, "symbol": str, "rank": int, "message": str},
            ...
        ]  ランク順（1が最良）でソートされている
    """
    if date is None:
        date = datetime.now()

    seed = int(date.strftime("%Y%m%d"))
    rng = random.Random(seed)

    # 3枚選択
    selected = rng.sample(CARD_POOL, 3)

    # メッセージ選択（シードに基づく）
    cards = []
    for i, tpl in enumerate(selected):
        msg_idx = (seed + i * 31) % len(tpl["messages"])
        msg = tpl["messages"][msg_idx]
        assert _validate_message(msg), f"Negative word in message: {msg}"
        cards.append(
            {
                "title": tpl["title"],
                "symbol": tpl["symbol"],
                "rank": 0,  # 後で設定
                "message": msg,
            }
        )

    # ランク割り当て（シードに基づく順列）
    ranks = rng.sample([1, 2, 3], 3)
    for i, card in enumerate(cards):
        card["rank"] = ranks[i]

    # ランク順にソート
    cards.sort(key=lambda c: c["rank"])
    return cards


def get_date_string(date: datetime | None = None) -> str:
    """日本語の日付文字列を返す（例: 4月11日）。"""
    if date is None:
        date = datetime.now()
    return f"{date.month}月{date.day}日"


if __name__ == "__main__":
    today = datetime.now()
    print(f"=== {get_date_string(today)} の占い ===")
    for card in get_fortune_cards(today):
        print(f"\n【{card['rank']}位】{card['title']} ({card['symbol']})")
        print(card["message"])
