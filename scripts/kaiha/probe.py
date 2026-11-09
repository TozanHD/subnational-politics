"""【調査用】各都道府県のサイトを巡回し、会派構成が載っていそうなページを探して保存する。

GitHub Actions 上で実行し、結果 (probe/*.json) を見ながら読み取り設定を作るためのもの。
"""
from __future__ import annotations

import heapq
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract import decode, extract  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "probe"
UA = "Mozilla/5.0 (compatible; subnational-politics-bot/1.0; +https://github.com/TozanHD/subnational-politics)"

PREFS = [
    ("北海道", "hokkaido"), ("青森県", "aomori"), ("岩手県", "iwate"), ("宮城県", "miyagi"),
    ("秋田県", "akita"), ("山形県", "yamagata"), ("福島県", "fukushima"), ("茨城県", "ibaraki"),
    ("栃木県", "tochigi"), ("群馬県", "gunma"), ("埼玉県", "saitama"), ("千葉県", "chiba"),
    ("東京都", "tokyo"), ("神奈川県", "kanagawa"), ("新潟県", "niigata"), ("富山県", "toyama"),
    ("石川県", "ishikawa"), ("福井県", "fukui"), ("山梨県", "yamanashi"), ("長野県", "nagano"),
    ("岐阜県", "gifu"), ("静岡県", "shizuoka"), ("愛知県", "aichi"), ("三重県", "mie"),
    ("滋賀県", "shiga"), ("京都府", "kyoto"), ("大阪府", "osaka"), ("兵庫県", "hyogo"),
    ("奈良県", "nara"), ("和歌山県", "wakayama"), ("鳥取県", "tottori"), ("島根県", "shimane"),
    ("岡山県", "okayama"), ("広島県", "hiroshima"), ("山口県", "yamaguchi"), ("徳島県", "tokushima"),
    ("香川県", "kagawa"), ("愛媛県", "ehime"), ("高知県", "kochi"), ("福岡県", "fukuoka"),
    ("佐賀県", "saga"), ("長崎県", "nagasaki"), ("熊本県", "kumamoto"), ("大分県", "oita"),
    ("宮崎県", "miyazaki"), ("鹿児島県", "kagoshima"), ("沖縄県", "okinawa"),
]

MAX_PAGES = 45

KW_ANCHOR = [("会派", 12), ("議員名簿", 9), ("議員一覧", 9), ("名簿", 5), ("議員", 4), ("県議会", 5),
             ("府議会", 5), ("都議会", 5), ("道議会", 5), ("議会", 3), ("構成", 3)]
KW_URL = [("kaiha", 10), ("meibo", 7), ("giin", 5), ("gikai", 3), ("member", 5)]
NEG = ["議事録", "会議録", "傍聴", "中継", "請願", "予算", "入札", "採用", "english", "kids", "こども", "子ども",
       "広報", "定例会", "日程", "審議", "政務活動費", "議案", "交際費", "条例"]


def seeds(r: str) -> list[str]:
    if r == "tokyo":
        return ["https://www.gikai.metro.tokyo.lg.jp/", "https://www.metro.tokyo.lg.jp/"]
    return [
        f"https://www.gikai.pref.{r}.lg.jp/",
        f"https://www.pref.{r}.lg.jp/",
        f"https://www.pref.{r}.jp/",
    ]


def host_ok(host: str, r: str) -> bool:
    if r == "tokyo":
        return host.endswith("metro.tokyo.lg.jp") or host.endswith("metro.tokyo.jp")
    return host.endswith(".jp") and f".{r}." in f".{host}." and ("pref" in host or "gikai" in host)


def fetch(url: str) -> tuple[bytes, str, str] | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ja"})
        with urllib.request.urlopen(req, timeout=25) as res:
            ctype = res.headers.get("Content-Type", "")
            if "html" not in ctype and not url.endswith((".html", ".htm", "/")):
                return None
            return res.read(3_000_000), ctype, res.geturl()
    except Exception as e:  # noqa: BLE001
        print(f"   x {url}: {e}", file=sys.stderr)
        return None


def link_score(url: str, anchor: str) -> int:
    s = 0
    for k, w in KW_ANCHOR:
        if k in anchor:
            s += w
    low = url.lower()
    for k, w in KW_URL:
        if k in low:
            s += w
    if any(n in anchor for n in NEG):
        s -= 8
    return s


def page_score(doc: dict) -> int:
    text = "\n".join(doc["lines"])
    s = text.count("会派") * 3
    s += len(re.findall(r"\d{1,3}\s*(人|名)", text))
    for t in doc["tables"]:
        head = " ".join(" ".join(r) for r in t["rows"][:2]) + t["heading"]
        if "会派" in head:
            s += 40
    return s


def probe(pref: str, r: str) -> dict:
    t0 = time.time()
    pq: list[tuple[int, int, str]] = []
    n = 0
    for u in seeds(r):
        heapq.heappush(pq, (-100, n, u))
        n += 1
    seen: set[str] = set()
    pages = []
    docs = {}
    files = []
    while pq and len(seen) < MAX_PAGES and time.time() - t0 < 600:
        prio, _, url = heapq.heappop(pq)
        if url in seen:
            continue
        seen.add(url)
        got = fetch(url)
        time.sleep(0.4)
        if not got:
            continue
        body, ctype, final = got
        doc = extract(decode(body, ctype))
        sc = page_score(doc)
        title = doc["lines"][0] if doc["lines"] else ""
        pages.append({"url": final, "score": sc, "prio": -prio, "title": title[:80]})
        docs[final] = doc
        for href, anchor in doc["links"]:
            if not href or href.startswith(("mailto:", "javascript:", "tel:")):
                continue
            u = urllib.parse.urljoin(final, href.strip()).split("#")[0]
            p = urllib.parse.urlparse(u)
            if p.scheme not in ("http", "https") or not host_ok(p.netloc, r):
                continue
            if re.search(r"\.(pdf|xlsx?|docx?|csv)$", p.path, re.I):
                if "会派" in anchor or "名簿" in anchor or "kaiha" in u.lower():
                    files.append({"url": u, "anchor": anchor, "from": final})
                continue
            if re.search(r"\.(jpg|png|gif|zip|mp4)$", p.path, re.I):
                continue
            ls = link_score(u, anchor)
            if ls > 0 and u not in seen:
                heapq.heappush(pq, (-(ls + min(10, -prio // 10)), n, u))
                n += 1
    pages.sort(key=lambda x: -x["score"])
    top = []
    for pg in pages[:4]:
        d = docs[pg["url"]]
        lines = d["lines"]
        if len(lines) > 300:
            idx = [i for i, l in enumerate(lines) if "会派" in l]
            keep = sorted({j for i in idx for j in range(max(0, i - 3), min(len(lines), i + 25))})
            lines = [lines[j] for j in keep][:400]
        top.append({**pg, "tables": [{"heading": t["heading"], "rows": t["rows"][:120]} for t in d["tables"][:12]], "lines": lines})
    seen_files = {f["url"]: f for f in files}
    print(f"{pref}: {len(seen)} pages, best={pages[0]['score'] if pages else None} {pages[0]['url'] if pages else ''}", file=sys.stderr)
    return {"pref": pref, "visited": len(seen), "pages": pages[:25], "top": top, "files": list(seen_files.values())[:30]}


def main():
    only = set(sys.argv[1:])
    OUT.mkdir(exist_ok=True)
    targets = [(i + 1, p, r) for i, (p, r) in enumerate(PREFS) if not only or p in only]

    def run(t):
        code, p, r = t
        res = probe(p, r)
        (OUT / f"{code:02d}.json").write_text(json.dumps(res, ensure_ascii=False, indent=0), encoding="utf-8")

    with ThreadPoolExecutor(max_workers=12) as ex:
        list(ex.map(run, targets))


if __name__ == "__main__":
    main()
