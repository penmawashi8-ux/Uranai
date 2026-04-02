# Uranai プロジェクト ガイドライン

## 禁止事項

- **Pillow（PIL）は絶対に使用しない**
  - 画像生成が必要な場合は ImageMagick または numpy+zlib（標準ライブラリ）を使う
  - `requirements.txt` に Pillow を追加しない
  - `import PIL` / `from PIL import ...` は書かない

## 技術スタック

- 動画生成: MoviePy（ColorClip, TextClip, CompositeVideoClip など）
- 背景画像: ImageMagick 優先、なければ numpy+zlib（`setup.py`）
- 占いテキスト: Gemini API（`google-genai`）
- YouTube アップロード: YouTube Data API v3（`google-api-python-client`）
