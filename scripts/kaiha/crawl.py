"""都道府県議会サイトの巡回（会派ページ探し）。update_kaiha.py と probe.py で共用。"""
from __future__ import annotations

import heapq
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract import decode, extract, extract_pdf  # noqa: E402

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


def fetch(url: str, allow_pdf: bool = False) -> tuple[bytes, str, str] | None:
    try:
        safe = urllib.parse.quote(url, safe=":/?#[]@!$&'()*+,;=%~")
        req = urllib.request.Request(safe, headers={"User-Agent": UA, "Accept-Language": "ja"})
        with urllib.request.urlopen(req, timeout=30) as res:
            ctype = res.headers.get("Content-Type", "")
            is_pdf = "pdf" in ctype or url.lower().endswith(".pdf")
            if is_pdf and not allow_pdf:
                return None
            if not is_pdf and "html" not in ctype and not url.endswith((".html", ".htm", "/")):
                return None
            return res.read(15_000_000), ctype, res.geturl()
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



def fetch_doc(url: str) -> dict | None:
    """HTML / PDF を取得して正規化する。"""
    got = fetch(url, allow_pdf=True)
    if not got:
        return None
    body, ctype, final = got
    try:
        if "pdf" in ctype or final.lower().endswith(".pdf") or body[:5] == b"%PDF-":
            doc = extract_pdf(body)
        else:
            doc = extract(decode(body, ctype))
    except Exception as e:  # noqa: BLE001 - 壊れた PDF など
        print(f"   x {url}: 解析失敗 {e}", file=sys.stderr)
        return None
    doc["url"] = final
    return doc


def find_link(doc: dict, pattern: str, base: str | None = None) -> str | None:
    """ページ内で、リンク文字列か URL が pattern（正規表現）に合う最初のリンクを返す。"""
    rx = re.compile(pattern)
    for href, anchor in doc.get("links", []):
        if not href:
            continue
        u = urllib.parse.urljoin(base or doc.get("url", ""), href.strip()).split("#")[0]
        if rx.search(anchor) or rx.search(u):
            return u
    return None


def crawl(r: str, extra_seeds: list[str] | None = None, max_pages: int = 45, time_limit: int = 600) -> list[dict]:
    """会派ページらしさの高い順に探索し、取得したページ {url, score, doc, files} を返す。"""
    t0 = time.time()
    pq: list[tuple[int, int, str]] = []
    n = 0
    for u in (extra_seeds or []) + seeds(r):
        heapq.heappush(pq, (-100, n, u))
        n += 1
    seen: set[str] = set()
    pages = []
    while pq and len(seen) < max_pages and time.time() - t0 < time_limit:
        prio, _, url = heapq.heappop(pq)
        if url in seen:
            continue
        seen.add(url)
        doc = fetch_doc(url)
        time.sleep(0.4)
        if not doc:
            continue
        final = doc["url"]
        seen.add(final)
        files = []
        for href, anchor in doc["links"]:
            if not href or href.startswith(("mailto:", "javascript:", "tel:")):
                continue
            u = urllib.parse.urljoin(final, href.strip()).split("#")[0]
            p = urllib.parse.urlparse(u)
            if p.scheme not in ("http", "https") or not host_ok(p.netloc, r):
                continue
            if re.search(r"\.(pdf|xlsx?|docx?|csv)$", p.path, re.I):
                if "会派" in anchor or "名簿" in anchor or "kaiha" in u.lower():
                    files.append({"url": u, "anchor": anchor})
                continue
            if re.search(r"\.(jpg|jpeg|png|gif|zip|mp4)$", p.path, re.I):
                continue
            ls = link_score(u, anchor)
            if ls > 0 and u not in seen:
                heapq.heappush(pq, (-(ls + min(10, -prio // 10)), n, u))
                n += 1
        pages.append({"url": final, "score": page_score(doc), "prio": -prio, "doc": doc, "files": files})
    return pages
