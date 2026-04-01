# 🔮 占い動画ボット（YouTube Shorts 自動投稿）

毎日12星座の占い動画を自動生成・投稿するシステムです。  
**すべて無料枠のみ使用**（Gemini API / YouTube Data API v3 / MoviePy）。

---

## システム概要

```
Gemini API → 占いテキスト生成
     ↓
MoviePy    → 縦型動画生成（1080×1920px / 50秒）
     ↓
YouTube API → Shorts として投稿
```

YouTube の無料枠制限（1日6本）のため、**12星座を奇数日・偶数日で6星座ずつ交互に投稿**します。

---

## セットアップ手順

### 1. パッケージのインストール

```bash
cd fortune_bot
pip install -r requirements.txt
```

### 2. 素材の自動生成

```bash
python setup.py
```

フォント（Noto Sans CJK）と背景画像（12星座分）が自動で揃います。

### 3. Gemini API キーの取得

1. [Google AI Studio](https://aistudio.google.com) にアクセス
2. 「Get API key」→「Create API key」をクリック
3. 取得したキーを `.env` に設定:

```
GEMINI_API_KEY=AIza...your_key_here
```

### 4. YouTube API の設定

1. [Google Cloud Console](https://console.cloud.google.com) にアクセス
2. 新しいプロジェクトを作成（または既存を選択）
3. 「APIとサービス」→「ライブラリ」→「YouTube Data API v3」を有効化
4. 「認証情報」→「OAuth 2.0 クライアント ID」を作成
   - アプリの種類: **デスクトップアプリ**
5. クライアントIDとシークレットを `.env` に設定:

```
YOUTUBE_CLIENT_ID=123456789-xxx.apps.googleusercontent.com
YOUTUBE_CLIENT_SECRET=GOCSPX-xxx
```

### 5. 初回 OAuth2 認証

```bash
python upload_youtube.py --auth
```

ブラウザが開くので Google アカウントでログインし、チャンネルへのアクセスを許可します。  
認証情報は `token.json` に保存され、以降は自動リフレッシュされます。

### 6. BGMの準備

`assets/bgm/` に著作権フリーの MP3 を配置してください（任意）。

| サイト | URL |
|--------|-----|
| DOVA-SYNDROME | https://dova-s.jp |
| 魔王魂 | https://maou.audio |

ファイル名は `bgm1.mp3`, `bgm2.mp3` ... としてください。  
BGM がない場合は無音で動画が生成されます。

---

## 実行コマンド一覧

```bash
# テスト（動画生成まで、アップロードなし）
python main.py --test --sign おひつじ座

# 特定の星座のみ本番実行
python main.py --sign おひつじ座

# 今日の6星座を本番実行（奇数/偶数日で自動振り分け）
python main.py --all

# 指定日で実行
python main.py --all --date 2025-01-01

# 運勢テキストだけ生成（動画なし）
python generate_fortune.py --date 2025-01-01

# 動画だけ生成
python generate_video.py --sign おひつじ座 --date 2025-01-01

# 動画だけアップロード（生成済みの場合）
python upload_youtube.py --sign おひつじ座

# 限定公開でアップロード（テスト用）
python upload_youtube.py --sign おひつじ座 --private

# スケジューラを常駐起動
python scheduler.py

# スケジューラのジョブを今すぐ1回実行
python scheduler.py --once
```

---

## cron 設定例（毎朝 6:00 JST に自動実行）

```bash
crontab -e
```

以下を追加：

```cron
# 毎朝 6:00 JST に占いテキスト生成
0 6 * * * cd /path/to/fortune_bot && python generate_fortune.py >> logs/cron.log 2>&1

# 毎朝 6:30 JST に動画生成＆アップロード（今日の6星座）
30 6 * * * cd /path/to/fortune_bot && python main.py --all >> logs/cron.log 2>&1
```

**または** APScheduler を使ってデーモン起動：

```bash
# バックグラウンドで起動
nohup python scheduler.py &

# systemd を使う場合は /etc/systemd/system/fortune-bot.service を作成
```

---

## YouTube 無料枠の制限と2日サイクルの説明

| 項目 | 制限 |
|------|------|
| YouTube API 無料枠 | 1日 10,000 ユニット |
| 動画アップロード | 1本あたり 1,600 ユニット |
| **1日の最大アップロード数** | **6本** |

12星座すべてを毎日投稿することはできないため、  
**奇数日**: おひつじ座〜おとめ座（前半6星座）  
**偶数日**: てんびん座〜うお座（後半6星座）  
という2日サイクルで投稿します。

---

## Gemini API の制限

| 項目 | 制限 |
|------|------|
| 無料枠レート制限 | 1分あたり 15 リクエスト |
| 1日の制限 | 1,500 リクエスト |

12星座の生成に約1分かかります（各リクエスト間に5秒のスリープ）。

---

## トラブルシューティング

### `ModuleNotFoundError: No module named 'moviepy'`
```bash
pip install -r requirements.txt
```

### `フォントが見つかりません`
```bash
python setup.py
```

### `背景画像が見つかりません`
```bash
python setup.py
```
`assets/backgrounds/` に12星座分の PNG が生成されます。

### `GEMINI_API_KEY が設定されていません`
`.env` ファイルに `GEMINI_API_KEY=AIza...` を設定してください。

### `YouTube 認証失敗`
```bash
python upload_youtube.py --auth
```
`token.json` を削除してから再認証してみてください。

### `quota exceeded` (YouTube API エラー)
1日のアップロード上限（6本）に達しています。翌日に実行してください。

### `TextClip` で文字化けする
フォントファイルが正しく配置されているか確認してください:
```bash
ls assets/fonts/
# NotoSansCJK-Bold.ttc が存在すること
```

### MoviePy で動画生成が遅い
1本あたり1〜3分かかるのは正常です。進捗バーが表示されます。

---

## フォルダ構成

```
fortune_bot/
├── setup.py              最初に実行（フォント・背景自動生成）
├── main.py               メインエントリーポイント
├── generate_fortune.py   Gemini API で占いテキスト生成
├── generate_video.py     MoviePy で動画生成
├── upload_youtube.py     YouTube Shorts アップロード
├── scheduler.py          APScheduler による自動実行
├── config.py             定数・星座定義
├── assets/
│   ├── bgm/              BGM（手動で配置）
│   ├── fonts/            フォント（setup.py が自動配置）
│   └── backgrounds/      背景画像（setup.py が自動生成）
├── output/               生成された動画・運勢JSON
├── logs/                 実行ログ（YYYY-MM-DD.log）
├── token.json            YouTube OAuth2 トークン（自動生成）
├── .env                  APIキー設定
└── requirements.txt
```
