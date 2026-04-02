"""
post_comment.py - GitHub Issue #5 に実行結果をコメントする。

使い方:
    GITHUB_TOKEN=... RUN_ID=... JOB_STATUS=... REPO=... python3 post_comment.py
"""
import json
import os
import glob
import urllib.request
from datetime import datetime, timezone, timedelta

run_id = os.environ["RUN_ID"]
status = os.environ["JOB_STATUS"]
repo = os.environ["REPO"]
token = os.environ["GITHUB_TOKEN"]
jst = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M JST")
run_url = f"https://github.com/{repo}/actions/runs/{run_id}"

lines = [f"## {jst} ({status})", "", f"[Actions ログを見る]({run_url})", ""]

jsons = sorted(glob.glob("fortune_bot/output/fortune_*.json"))
if jsons:
    try:
        data = json.load(open(jsons[-1]))
        fb = sum(1 for f in data if f.get("hook") == "今日も運気上昇中")
        lines += [
            "### 運勢生成結果",
            "```",
            f"API成功: {len(data)-fb}/12  フォールバック: {fb}/12",
        ]
        for f in data:
            mark = "!!" if f.get("hook") == "今日も運気上昇中" else "OK"
            lines.append(f"{mark} {f['sign']}: {f['hook']}")
        lines += ["```", ""]
    except Exception as e:
        lines.append(f"(JSON解析失敗: {e})")

logs = sorted(glob.glob("fortune_bot/logs/*.log"))
if logs:
    lines += ["### ログ", "```"]
    for lf in logs:
        lines += open(lf, encoding="utf-8").read().splitlines()
    lines.append("```")

body = "\n".join(lines)
payload = json.dumps({"body": body}).encode()
req = urllib.request.Request(
    f"https://api.github.com/repos/{repo}/issues/5/comments",
    data=payload,
    headers={
        "Authorization": f"token {token}",
        "Content-Type": "application/json",
    },
)
try:
    resp = urllib.request.urlopen(req)
    print(f"コメント投稿完了: HTTP {resp.status}")
except urllib.error.HTTPError as e:
    print(f"コメント投稿失敗: HTTP {e.code} {e.reason}")
    print(e.read().decode())
    raise
except Exception as e:
    print(f"コメント投稿エラー: {e}")
    raise
