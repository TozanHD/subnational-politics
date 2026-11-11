"""【調査用】各都道府県議会サイトから議場図・議席表（画像 / PDF / 表）を探して probe/seats/ に保存する。"""
from __future__ import annotations

import heapq
import io
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from crawl import PREFS, UA, host_ok, seeds  # noqa: E402
from extract import decode, extract  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "probe" / "seats"
KEY = re.compile(r"議席|議場|座席|giseki|gijo|gijyo|gizyo|seat|zaseki|haichi|layout", re.I)
JUNK = re.compile(r"logo|icon|banner|bnr|btn|button|header|footer|spacer|arrow|\.gif|\.svg|qr|sns|twitter|facebook|line_|youtube|search|menu|pagetop|adobe|get_", re.I)
KW = [("議席", 15), ("議場", 14), ("座席", 10), ("配置", 6), ("見学", 6), ("キッズ", 6), ("こども", 6), ("子ども", 6),
      ("しくみ", 4), ("概要", 5), ("あらまし", 5), ("パンフレット", 5), ("ガイド", 3), ("議事堂", 8), ("案内", 3), ("議員名簿", 5), ("議員紹介", 5), ("議員の紹介", 5),
      ("議員一覧", 5), ("議会", 2)]
KWU = [("giseki", 12), ("gijo", 12), ("gijyo", 12), ("seat", 8), ("kids", 5), ("gaiyo", 3), ("shikumi", 3), ("meibo", 3)]
NEG = ["会議録", "中継", "請願", "予算", "入札", "採用", "日程", "議案", "政務活動", "条例", "質問", "録画", "報道", "定例会",
       "臨時会", "意見書", "陳情", "english", "決算", "広報紙", "だより"]


def get(url: str, limit: int = 12_000_000):
    try:
        safe = urllib.parse.quote(url, safe=":/?#[]@!$&'()*+,;=%~")
        req = urllib.request.Request(safe, headers={"User-Agent": UA, "Accept-Language": "ja"})
        with urllib.request.urlopen(req, timeout=30) as res:
            return res.read(limit), res.headers.get("Content-Type", ""), res.geturl()
    except Exception as e:  # noqa: BLE001
        print(f"   x {url}: {e}", file=sys.stderr)
        return None


def lscore(url: str, anchor: str) -> int:
    s = sum(w for k, w in KW if k in anchor) + sum(w for k, w in KWU if k in url.lower())
    if any(n in anchor for n in NEG):
        s -= 8
    return s


def save_image(data: bytes, path: Path) -> tuple[int, int] | None:
    from PIL import Image
    try:
        im = Image.open(io.BytesIO(data))
        im.load()
    except Exception:  # noqa: BLE001
        return None
    if im.width < 280 or im.height < 150:
        return None
    im = im.convert("RGB")
    if im.width > 1000:
        im = im.resize((1000, round(im.height * 1000 / im.width)))
    if im.height > 1400:
        im = im.resize((round(im.width * 1400 / im.height), 1400))
    im.save(path, "JPEG", quality=72)
    return im.size


PAGE_KW = [("議席表", 10), ("議席図", 10), ("議席配置", 10), ("議場配置", 10), ("議場図", 10), ("議場案内", 6), ("配席", 8),
           ("座席表", 8), ("議長席", 5), ("演壇", 5), ("傍聴席", 3), ("議場", 2), ("議席", 2)]


def save_pdf(data: bytes, path: Path, need_score: bool = False) -> tuple[int, int] | None:
    import pdfplumber
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            best, best_i = 0, 0
            if len(pdf.pages) > 1:
                for i, pg in enumerate(pdf.pages[:60]):
                    t = (pg.extract_text() or "").replace(" ", "")
                    sc = sum(w for k, w in PAGE_KW if k in t)
                    if sc > best:
                        best, best_i = sc, i
            if need_score and best < 10:
                return None
            img = pdf.pages[best_i].to_image(resolution=85).original
            buf = io.BytesIO()
            img.convert("RGB").save(buf, "PNG")
        return save_image(buf.getvalue(), path)
    except Exception as e:  # noqa: BLE001
        print(f"   pdf error {e}", file=sys.stderr)
        return None


def run(code: int, pref: str, romaji: str, seed_urls: list[str], direct: list[str]) -> None:
    t0 = time.time()
    hosts = {urllib.parse.urlparse(u).netloc for u in seed_urls}
    pq: list = []
    n = 0
    extra = []
    for u in seed_urls:
        p = urllib.parse.urlparse(u)
        extra.append(f"{p.scheme}://{p.netloc}/")
        parts = p.path.split("/")
        for i, seg in enumerate(parts):
            if "gikai" in seg.lower() or "assembly" in seg.lower():
                extra.append(f"{p.scheme}://{p.netloc}{'/'.join(parts[:i + 1])}/")
    for u in seed_urls + extra + seeds(romaji):
        heapq.heappush(pq, (-100, n, u, ""))
        n += 1
    seen: set[str] = set()
    cands = []
    assets: list[tuple[int, str, str, str]] = [(100, u, "指定", "") for u in direct]  # (優先度, url, 説明, 元ページ)
    while pq and len(seen) < 110 and time.time() - t0 < 600:
        prio, _, url, via = heapq.heappop(pq)
        if url in seen:
            continue
        seen.add(url)
        got = get(url, 3_000_000)
        time.sleep(0.35)
        if not got:
            continue
        body, ctype, final = got
        seen.add(final)
        if "html" not in ctype and not final.endswith((".html", ".htm", "/")):
            continue
        html = decode(body, ctype)
        doc = extract(html)
        text = "\n".join(doc["lines"])
        head = " ".join(doc["lines"][:60])
        is_cand = bool(KEY.search(via) or KEY.search(final) or re.search(r"議席表|議席図|議席配置|議場図|議場の(様子|案内|紹介|しくみ)|議場案内|座席表", text))
        pscore = text.count("議席") + text.count("議場") * 2 + (40 if is_cand else 0)
        for href, anchor in doc["links"]:
            if not href or href.startswith(("mailto:", "javascript:", "tel:")):
                continue
            u = urllib.parse.urljoin(final, href.strip()).split("#")[0]
            p = urllib.parse.urlparse(u)
            if p.scheme not in ("http", "https") or not (p.netloc in hosts or host_ok(p.netloc, romaji)):
                continue
            if re.search(r"\.(pdf|jpe?g|png)$", p.path, re.I):
                if KEY.search(anchor) or KEY.search(p.path):
                    assets.append((60 + (20 if "議席" in anchor else 0), u, anchor, final))
                elif p.path.lower().endswith(".pdf") and re.search(r"概要|あらまし|パンフレット|しおり|ガイド|ハンドブック|わたしたちの|私たちの|みんなの|見学", anchor):
                    assets.append((30, u, "?" + anchor, final))
                continue
            if re.search(r"\.(xlsx?|docx?|csv|zip|mp4|gif)$", p.path, re.I):
                continue
            ls = lscore(u, anchor)
            if ls > 0 and u not in seen:
                heapq.heappush(pq, (-(ls + min(8, -prio // 12)), n, u, anchor))
                n += 1
        if is_cand:
            for m in re.finditer(r"<img\b[^>]*>", html, re.I):
                tag = m.group(0)
                src = re.search(r'src\s*=\s*["\']?([^"\'\s>]+)', tag, re.I)
                alt = re.search(r'alt\s*=\s*["\']([^"\']*)', tag, re.I)
                if not src:
                    continue
                u = urllib.parse.urljoin(final, src.group(1))
                a = alt.group(1) if alt else ""
                if JUNK.search(u) and not KEY.search(a):
                    continue
                key = bool(KEY.search(a) or KEY.search(urllib.parse.urlparse(u).path.rsplit("/", 1)[-1]))
                assets.append(((50 if key else 15) + min(20, pscore // 10), u, a, final))
            idx = [i for i, l in enumerate(doc["lines"]) if re.search(r"議席|議場|座席", l)]
            keep = sorted({j for i in idx for j in range(max(0, i - 1), min(len(doc["lines"]), i + 3))})[:60]
            tables = [t["rows"][:30] for t in doc["tables"] if len(t["rows"]) >= 3 and max(len(r) for r in t["rows"]) >= 5][:3]
            cands.append({"url": final, "via": via, "score": pscore, "lines": [doc["lines"][j][:160] for j in keep],
                          "tables": [[[c[:14] for c in r[:40]] for r in t] for t in tables]})
    cands.sort(key=lambda c: -c["score"])
    assets.sort(key=lambda a: -a[0])
    saved = []
    done: set[str] = set()
    for prio, u, desc, src in assets:
        if len(saved) >= 6 or u in done:
            continue
        done.add(u)
        got = get(u)
        time.sleep(0.3)
        if not got:
            continue
        data = got[0]
        name = f"{code:02d}_{len(saved) + 1}.jpg"
        size = save_pdf(data, OUT / name, desc.startswith("?")) if data[:5] == b"%PDF-" else save_image(data, OUT / name)
        if size:
            saved.append({"file": name, "url": u, "desc": desc, "page": src, "prio": prio, "size": size})
    (OUT / f"{code:02d}.json").write_text(json.dumps(
        {"pref": pref, "visited": len(seen), "images": saved, "pages": cands[:6]}, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"{pref}: pages={len(seen)} cands={len(cands)} assets={len(assets)} saved={len(saved)}", file=sys.stderr)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    sites = json.loads((Path(__file__).resolve().parent / "sites.json").read_text(encoding="utf-8"))
    extra = {}
    tp = ROOT / "probe" / "seat_targets.json"
    if tp.exists():
        extra = json.loads(tp.read_text(encoding="utf-8"))
    only = set(extra) if extra.get("_only") else None
    direct = extra.get("_assets", {})
    jobs = []
    for i, (pref, romaji) in enumerate(PREFS, start=1):
        if only is not None and pref not in only:
            continue
        s = list(extra.get(pref, [])) + [x["url"] for x in sites[pref]["sources"]]
        jobs.append((i, pref, romaji, list(dict.fromkeys(s)), direct.get(pref, [])))
    with ThreadPoolExecutor(max_workers=12) as ex:
        list(ex.map(lambda j: run(*j), jobs))


if __name__ == "__main__":
    main()
