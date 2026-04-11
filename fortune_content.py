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
            "今日は嬉しい出会いがありそうです。\n積極的に話しかけてみましょう。\nあなたの笑顔が縁を呼びます。",
            "大切な人との時間を作りましょう。\n素直な言葉が関係を深めます。\n人との繋がりが今日の力になります。",
            "久しぶりの人から連絡があるかも。\n気になる人に自分から声をかけて。\n新しい縁が広がる一日です。",
        ],
    },
    {
        "id": "star",
        "title": "希望",
        "symbol": "star",
        "messages": [
            "今日は自分の夢を声に出してみて。\nやりたいことに一歩踏み出せます。\n良い変化が近づいています。",
            "コツコツ続けてきたことが形になります。\n自分のペースで進んで大丈夫です。\n努力は必ず報われます。",
            "今日は思い切った決断ができる日。\n迷っていることがあれば動いてみて。\n新しい道が開ける予感がします。",
        ],
    },
    {
        "id": "moon",
        "title": "直感",
        "symbol": "moon",
        "messages": [
            "今日はピンときたことを大切にして。\n直感が正しい答えを教えてくれます。\n静かな時間が判断力を高めます。",
            "今日は感性が冴えている日です。\n好きな音楽や映画を楽しんで。\nリラックスすることで力が出ます。",
            "なんとなく感じることを信じて。\n考えすぎより感じることが大事です。\nあなたの判断は正確です。",
        ],
    },
    {
        "id": "sun",
        "title": "活力",
        "symbol": "sun",
        "messages": [
            "今日はエネルギーに溢れています。\n行動すればするほど良い結果が出ます。\n自信を持って動きましょう。",
            "新しいことを始めるのに最高の日です。\n気になっていたことに挑戦してみて。\nあなたの元気が周りを明るくします。",
            "目標に向かって動ける一日です。\n小さなことから始めればOKです。\n頑張った分だけ結果に出ます。",
        ],
    },
    {
        "id": "key",
        "title": "機会",
        "symbol": "key",
        "messages": [
            "今日は大事なチャンスが来る日です。\n見逃さないようにアンテナを張って。\n行動することで道が開けます。",
            "今まで気づかなかったことに気づく日。\n視野を広げると良いことが見えます。\nあなたの選択が未来を変えます。",
            "思いがけない話が来るかもしれません。\n最初は小さく見えても大事な機会です。\nまず話を聞いてみましょう。",
        ],
    },
    {
        "id": "hourglass",
        "title": "時",
        "symbol": "hourglass",
        "messages": [
            "続けてきた努力が実りはじめています。\n急がなくて大丈夫、タイミングは来ます。\n今日この瞬間を大切にして。",
            "今日は今やるべきことに集中して。\n一つずつ片付けると気持ちが楽になります。\n積み重ねが自信になっています。",
            "タイミングが整ってきています。\n準備は十分できているはずです。\n一歩踏み出す日が今日です。",
        ],
    },
    {
        "id": "feather",
        "title": "自由",
        "symbol": "feather",
        "messages": [
            "今日は気持ちが軽くなる出来事があります。\nこだわりを手放すと楽になれます。\n自分らしくいることが一番です。",
            "型にはまらないアイデアが出る日です。\n自分の個性を活かして行動してみて。\nあなたらしさが強みになります。",
            "今日はやりたいことを優先していいです。\n自分の気持ちに正直に動きましょう。\nそれが一番良い結果に繋がります。",
        ],
    },
    {
        "id": "flame",
        "title": "情熱",
        "symbol": "flame",
        "messages": [
            "好きなことに全力を出せる日です。\n情熱を持って取り組むことが大事です。\nその熱量が周りに伝わります。",
            "今日は創造力が高まっています。\n作りたいもの、やりたいことに集中して。\n思っている以上に良いものができます。",
            "迷っているなら挑戦する方を選んで。\n本気でやれば必ず結果が出ます。\n情熱があなたの最大の武器です。",
        ],
    },
    {
        "id": "droplet",
        "title": "癒し",
        "symbol": "droplet",
        "messages": [
            "今日はゆっくり自分を休ませましょう。\n自分のペースを守ることが大切な日です。\n優しい気持ちが周りにも伝わります。",
            "今日は感情を素直に出していいです。\n話せる人に気持ちを話してみて。\n誰かに話すだけで楽になれます。",
            "身近な人を気にかけてみましょう。\nちょっとした言葉が誰かを助けます。\nその優しさはあなたにも返ってきます。",
        ],
    },
    {
        "id": "heart",
        "title": "愛",
        "symbol": "heart",
        "messages": [
            "大切な人に感謝を伝える良い日です。\n素直な一言が関係をより深めます。\n愛情を受け取ることも大切にして。",
            "今日は自分自身を大切にしましょう。\n好きなものを食べたり休んだりして。\n自分への優しさが周りへの優しさになります。",
            "誰かのために何かをすると喜びになります。\nちょっとした親切が嬉しい結果を生みます。\nその温かさが必ずあなたに戻ります。",
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
