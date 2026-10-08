"""www1.nisiq.net/~t-takaya の全ページを巡回し、隠しページ調査用に保存するスクリプト。

GitHub Actions 上で実行する（標準ライブラリのみ使用）。
出力:
  crawl_report/pages/...     取得した HTML（UTF-8 に変換して保存）
  crawl_report/report.md     ページ一覧・リンク・コメント・怪しい箇所のまとめ
  crawl_report/cdx.txt       Wayback Machine に記録されている URL 一覧
"""

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from html.parser import HTMLParser

START = "http://www1.nisiq.net/~t-takaya/index.html"
HOST = "www1.nisiq.net"
PREFIX = "/~t-takaya/"
OUT = sys.argv[1] if len(sys.argv) > 1 else "crawl_report"
UA = "Mozilla/5.0 (compatible; hidden-page-survey)"
DELAY = 0.3
MAX_PAGES = 3000

GUESS_NAMES = [
    "secret", "himitsu", "himitu", "kakushi", "kakusi", "hidden", "hiden",
    "ura", "omake", "test", "index2", "top", "menu", "special", "sp",
    "new", "bonus", "xxx", "a", "b", "1", "2",
]

HTML_EXT = (".html", ".htm", ".shtml", "/")
LINK_RE = re.compile(r"""["'(=\s]([^"'()\s<>]+?\.(?:s?html?|cgi|gif|jpe?g|png|swf|mid|txt))""", re.I)


def in_scope(url):
    p = urllib.parse.urlparse(url)
    return p.netloc.lower() == HOST and p.path.startswith(PREFIX)


def normalize(url):
    url, _ = urllib.parse.urldefrag(url)
    p = urllib.parse.urlparse(url)
    return urllib.parse.urlunparse(("http", p.netloc.lower(), p.path, "", p.query, ""))


def fetch(url, tries=3):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, r.read(), r.headers.get("Content-Type", ""), r.geturl()
        except urllib.error.HTTPError as e:
            return e.code, e.read() if e.fp else b"", e.headers.get("Content-Type", ""), url
        except Exception as e:  # ネットワークエラーは再試行
            last = e
            time.sleep(2 ** i)
    return None, str(last).encode(), "", url


def decode(raw, ctype):
    m = re.search(rb"charset=[\"']?([\w-]+)", raw[:2000], re.I)
    cands = []
    if m:
        cands.append(m.group(1).decode("ascii", "ignore"))
    m2 = re.search(r"charset=([\w-]+)", ctype or "", re.I)
    if m2:
        cands.append(m2.group(1))
    cands += ["shift_jis", "cp932", "euc_jp", "iso2022_jp", "utf-8"]
    for enc in cands:
        try:
            return raw.decode(enc)
        except (LookupError, UnicodeDecodeError):
            continue
    return raw.decode("cp932", "replace")


class PageParser(HTMLParser):
    URL_ATTRS = {"href", "src", "background", "action", "data", "code", "lowsrc", "dynsrc", "usemap"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.urls = []          # (tag, attr, value)
        self.comments = []
        self.anchors = []       # dict(href, text, imgs, colors)
        self.body_attrs = {}
        self.font_stack = []
        self.cur_a = None
        self.scripts = []
        self.in_script = False

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "body":
            self.body_attrs = a
        if tag == "font":
            self.font_stack.append(a.get("color", ""))
        if tag == "script":
            self.in_script = True
            self.scripts.append("")
        if tag == "meta" and a.get("http-equiv", "").lower() == "refresh":
            m = re.search(r"url=(.+)", a.get("content", ""), re.I)
            if m:
                self.urls.append((tag, "refresh", m.group(1).strip("'\" ")))
        for k, v in a.items():
            if k in self.URL_ATTRS and v:
                self.urls.append((tag, k, v))
            if k.startswith("on") and v:
                self.scripts.append(v)
        if tag in ("a", "area"):
            info = {"tag": tag, "href": a.get("href", ""), "text": "", "imgs": [],
                    "colors": [c for c in self.font_stack if c], "attrs": a}
            if tag == "a":
                self.cur_a = info
            self.anchors.append(info)
        if tag == "img" and self.cur_a is not None:
            self.cur_a["imgs"].append({k: a.get(k, "") for k in ("src", "width", "height", "alt")})

    def handle_endtag(self, tag):
        if tag == "font" and self.font_stack:
            self.font_stack.pop()
        if tag == "a":
            self.cur_a = None
        if tag == "script":
            self.in_script = False

    def handle_data(self, data):
        if self.in_script and self.scripts:
            self.scripts[-1] += data
        if self.cur_a is not None:
            self.cur_a["text"] += data

    def handle_comment(self, data):
        self.comments.append(data.strip())


def local_path(url):
    p = urllib.parse.urlparse(url).path[len(PREFIX):] or "index.html"
    if p.endswith("/"):
        p += "_dir_.html"
    return os.path.join(OUT, "pages", urllib.parse.unquote(p))


def suspicious_anchor(an, bg):
    """見えにくいリンクかどうかの判定理由を返す。"""
    reasons = []
    text = an["text"].replace("　", " ").strip()
    if not text and not an["imgs"] and an["tag"] == "a":
        reasons.append("リンク文字が空白のみ")
    for im in an["imgs"]:
        try:
            if int(im["width"] or 99) <= 10 or int(im["height"] or 99) <= 10:
                reasons.append(f"極小画像 {im['src']} {im['width']}x{im['height']}")
        except ValueError:
            pass
    if bg and any(c.lower() == bg.lower() for c in an["colors"]):
        reasons.append(f"文字色が背景色と同じ ({bg})")
    if len(text) == 1 and not an["imgs"]:
        reasons.append(f"1文字だけのリンク「{text}」")
    return reasons


def main():
    os.makedirs(os.path.join(OUT, "pages"), exist_ok=True)
    seen = {}
    queue = deque([normalize(START)])
    queued = {normalize(START)}
    referrers = {}
    report = {}

    def enqueue(u, src):
        u = normalize(u)
        referrers.setdefault(u, set()).add(src)
        if in_scope(u) and u not in queued:
            queued.add(u)
            queue.append(u)

    while queue and len(seen) < MAX_PAGES:
        url = queue.popleft()
        status, raw, ctype, final = fetch(url)
        time.sleep(DELAY)
        seen[url] = (status, ctype, len(raw))
        print(f"[{status}] {url} ({ctype}, {len(raw)}B)", flush=True)
        if status != 200:
            continue
        is_html = "html" in ctype.lower() or url.lower().endswith(HTML_EXT)
        if not is_html:
            continue
        text = decode(raw, ctype)
        path = local_path(url)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)

        pp = PageParser()
        try:
            pp.feed(text)
        except Exception as e:
            print("parse error", url, e)
        found = set()
        for tag, attr, v in pp.urls:
            if v.lower().startswith(("mailto:", "javascript:")):
                continue
            found.add(urllib.parse.urljoin(final, v.strip()))
        # スクリプト・コメント・生 HTML 中の URL らしき文字列も拾う
        for blob in pp.scripts + pp.comments + [text]:
            for m in LINK_RE.finditer(" " + blob):
                found.add(urllib.parse.urljoin(final, m.group(1)))
        for u in found:
            enqueue(u, url)

        bg = pp.body_attrs.get("bgcolor", "")
        report[url] = {
            "body": pp.body_attrs,
            "comments": [c for c in pp.comments if c],
            "scripts": [s.strip() for s in pp.scripts if s.strip()],
            "links": sorted(found),
            "suspicious": [
                {"href": an["href"], "text": an["text"].strip(), "why": r}
                for an in pp.anchors for r in [suspicious_anchor(an, bg)] if r
            ],
            "maps": [an for an in pp.anchors if an["tag"] == "area"],
        }

    # 推測ファイル名・ディレクトリ一覧を試す
    dirs = sorted({u.rsplit("/", 1)[0] + "/" for u in seen if in_scope(u)})
    guesses = []
    for d in dirs:
        cands = [d] + [d + n + ext for n in GUESS_NAMES for ext in (".html", ".htm")]
        for c in cands:
            c = normalize(c)
            if c in seen:
                continue
            status, raw, ctype, _ = fetch(c, tries=1)
            time.sleep(DELAY)
            seen[c] = (status, ctype, len(raw))
            if status == 200:
                guesses.append(c)
                print(f"[GUESS HIT] {c}", flush=True)
                path = local_path(c)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(decode(raw, ctype))

    # Wayback Machine に残っている URL 一覧
    cdx_lines = []
    for host in ("www1.nisiq.net", "www.nisiq.net", "nisiq.net"):
        q = ("http://web.archive.org/cdx/search/cdx?url=" + host + PREFIX
             + "&matchType=prefix&fl=timestamp,original,statuscode,mimetype&collapse=urlkey&limit=5000")
        status, raw, _, _ = fetch(q)
        cdx_lines.append(f"# {host} status={status}")
        if status == 200:
            cdx_lines += raw.decode("utf-8", "replace").splitlines()
    with open(os.path.join(OUT, "cdx.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(cdx_lines) + "\n")

    # レポート作成
    linked_from_menu = set()
    for u, r in report.items():
        linked_from_menu.update(normalize(x) for x in r["links"])
    lines = ["# 巡回レポート", "", f"取得URL数: {len(seen)}", "",
             "## 全URL（ステータス）", ""]
    for u, (st, ct, n) in sorted(seen.items()):
        refs = ", ".join(sorted(referrers.get(u, [])))[:300]
        lines.append(f"- [{st}] {u} ({ct}, {n}B) ← {refs}")
    lines += ["", "## 推測ファイル名でヒットしたURL", ""] + [f"- {g}" for g in guesses]
    lines += ["", "## ページ別の詳細", ""]
    for u, r in sorted(report.items()):
        lines.append(f"### {u}")
        lines.append(f"- body: `{json.dumps(r['body'], ensure_ascii=False)}`")
        for c in r["comments"]:
            lines.append(f"- コメント: `{c[:300]}`")
        for s in r["scripts"]:
            lines.append(f"- スクリプト: `{s[:300].replace(chr(10), ' ')}`")
        for s in r["suspicious"]:
            lines.append(f"- **怪しいリンク** {s['href']} 「{s['text'][:40]}」 {'; '.join(s['why'])}")
        for m in r["maps"]:
            lines.append(f"- area: {m['href']} {m['attrs']}")
        for l in r["links"]:
            lines.append(f"  - {l}")
        lines.append("")
    with open(os.path.join(OUT, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"done: {len(seen)} urls, {len(report)} html pages")


if __name__ == "__main__":
    main()
