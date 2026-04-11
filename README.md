# Uranai - 占いショート動画 自動生成システム

YouTube ショート向け縦長占い動画（1080×1920px）を毎日自動生成する Python システムです。

## ファイル構成

```
uranai/
├── .github/workflows/generate_video.yml  # GitHub Actions（毎日 UTC 21:00 = JST 06:00）
├── generate_video.py                      # メイン動画生成スクリプト
├── fortune_content.py                     # 運勢テキスト生成（日付ベース）
├── card_generator.py                      # カード画像生成（numpy+zlib、PIL不使用）
├── requirements.txt
└── output/                                # 生成動画の保存先（.gitignore 対象）
```

## 動画仕様

| 項目 | 内容 |
|------|------|
| 解像度 | 1080×1920px（縦長） |
| フレームレート | 30fps |
| 長さ | 40秒 |
| 形式 | MP4（H.264） |
| 音声 | なし |
| 言語 | 日本語 |

## 動画構成

1. **イントロ（0〜3秒）** - 日付とタイトル
2. **カード選択（3〜8秒）** - 3枚の裏向きカードが出現
3. **カードフリップ（8〜20秒）** - 1枚ずつ順番にめくれる
4. **運勢発表（20〜35秒）** - 3枚のカードとメッセージ・ランキング
5. **エンディング（35〜40秒）** - 締めの言葉

## セットアップと実行

```bash
# 依存関係のインストール
sudo apt-get install -y fonts-noto-cjk ffmpeg imagemagick
pip install -r requirements.txt

# 今日の動画を生成
python generate_video.py

# 特定日付で生成
python generate_video.py --date 20240411

# テストモード（簡略生成で動作確認）
python generate_video.py --test
```

生成した動画は `output/fortune_YYYYMMDD.mp4` に保存されます。

## 技術スタック

- **動画生成**: MoviePy（ColorClip, TextClip, CompositeVideoClip）
- **画像生成**: numpy + zlib（PIL/Pillow 不使用）
- **フォント**: Noto Sans CJK JP（`fc-list` で自動検出）
- **運勢テキスト**: 日付ベースのシード乱数生成

## GitHub Actions

毎日 UTC 21:00（JST 06:00）に自動実行され、生成した動画を Artifact として 7日間保存します。
`workflow_dispatch` から手動実行も可能です。
