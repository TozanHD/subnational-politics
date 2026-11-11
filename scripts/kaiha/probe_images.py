"""【調査用】議場の形を調べるため、指定ページ・画像検索・YouTube・Wikimedia から議場の写真を集める。"""
from __future__ import annotations

import html as htmllib
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
from crawl import PREFS  # noqa: E402
from extract import decode  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "probe" / "img"
BROWSER = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
JUNK = re.compile(r"logo|icon|banner|bnr|btn|button|header|footer|spacer|arrow|\.gif|\.svg|qr|sns|twitter|facebook|line_|search|menu|pagetop|adobe|get_", re.I)
PAGE_KW = [("議席表", 10), ("議席図", 10), ("議席配置", 10), ("議場配置", 10), ("議場図", 10), ("配席", 8), ("座席表", 8),
           ("議長席", 5), ("演壇", 5), ("傍聴席", 3), ("議場", 2), ("議席", 2)]


def get(url, limit=15_000_000, referer=None):
    try:
        safe = urllib.parse.quote(url, safe=":/?#[]@!$&'()*+,;=%~")
        h = {"User-Agent": BROWSER, "Accept-Language": "ja,en;q=0.8"}
        if referer:
            h["Referer"] = referer
        with urllib.request.urlopen(urllib.request.Request(safe, headers=h), timeout=30) as res:
            return res.read(limit), res.headers.get("Content-Type", ""), res.geturl()
    except Exception as e:  # noqa: BLE001
        print(f"   x {url[:120]}: {e}", file=sys.stderr)
        return None


def save_image(data, path, min_w=260):
    from PIL import Image
    try:
        im = Image.open(io.BytesIO(data))
        im.load()
    except Exception:  # noqa: BLE001
        return None
    if im.width < min_w or im.height < 140:
        return None
    im = im.convert("RGB")
    if im.width > 900:
        im = im.resize((900, round(im.height * 900 / im.width)))
    if im.height > 1200:
        im = im.resize((round(im.width * 1200 / im.height), 1200))
    im.save(path, "JPEG", quality=70)
    return im.size


def pdf_pages(data, n=2):
    import pdfplumber
    out = []
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            scored = []
            for i, pg in enumerate(pdf.pages[:80]):
                t = (pg.extract_text() or "").replace(" ", "")
                scored.append((sum(w for k, w in PAGE_KW if k in t), -i))
            order = sorted(range(len(scored)), key=lambda i: scored[i], reverse=True)[:n] if len(scored) > 1 else [0]
            for i in order:
                buf = io.BytesIO()
                pdf.pages[i].to_image(resolution=85).original.convert("RGB").save(buf, "PNG")
                out.append((buf.getvalue(), f"p{i + 1} score{scored[i][0]}"))
    except Exception as e:  # noqa: BLE001
        print(f"   pdf error {e}", file=sys.stderr)
    return out


def bing_images(q):
    got = get("https://www.bing.com/images/search?form=HDRSC2&first=1&q=" + urllib.parse.quote(q))
    if not got:
        return []
    page = htmllib.unescape(got[0].decode("utf-8", "replace"))
    res = []
    for m in re.finditer(r'\{[^{}]*"murl":"([^"]+)"[^{}]*\}', page):
        blob = m.group(0)
        turl = re.search(r'"turl":"([^"]+)"', blob)
        purl = re.search(r'"purl":"([^"]+)"', blob)
        title = re.search(r'"t":"([^"]*)"', blob)
        res.append({"murl": m.group(1), "turl": turl.group(1) if turl else None,
                    "page": purl.group(1) if purl else "", "title": title.group(1) if title else ""})
    return res


def ddg_images(q):
    got = get("https://duckduckgo.com/?ia=images&iax=images&q=" + urllib.parse.quote(q))
    if not got:
        return []
    m = re.search(rb"vqd=[\"']?([\d-]+)", got[0])
    if not m:
        return []
    got = get("https://duckduckgo.com/i.js?l=jp-jp&o=json&f=,,,,,&p=1&q=" + urllib.parse.quote(q) + "&vqd=" + m.group(1).decode(),
              referer="https://duckduckgo.com/")
    if not got:
        return []
    try:
        return [{"murl": r["image"], "turl": r.get("thumbnail"), "page": r.get("url", ""), "title": r.get("title", "")}
                for r in json.loads(got[0]).get("results", [])]
    except Exception:  # noqa: BLE001
        return []


def youtube_thumbs(q):
    got = get("https://www.youtube.com/results?search_query=" + urllib.parse.quote(q))
    if not got:
        return []
    page = got[0].decode("utf-8", "replace")
    out, seen = [], set()
    for m in re.finditer(r'"videoRenderer":\{"videoId":"([\w-]{11})".{0,1500}?"title":\{"runs":\[\{"text":"([^"]*)"', page):
        if m.group(1) not in seen:
            seen.add(m.group(1))
            out.append({"murl": f"https://i.ytimg.com/vi/{m.group(1)}/maxresdefault.jpg",
                        "turl": f"https://i.ytimg.com/vi/{m.group(1)}/hqdefault.jpg",
                        "page": "https://www.youtube.com/watch?v=" + m.group(1), "title": m.group(2)})
    return out


def commons(q):
    got = get("https://commons.wikimedia.org/w/api.php?action=query&format=json&generator=search&gsrnamespace=6&gsrlimit=8"
              "&prop=imageinfo&iiprop=url&iiurlwidth=900&gsrsearch=" + urllib.parse.quote(q))
    if not got:
        return []
    try:
        pages = json.loads(got[0]).get("query", {}).get("pages", {})
    except Exception:  # noqa: BLE001
        return []
    out = []
    for p in pages.values():
        ii = (p.get("imageinfo") or [{}])[0]
        if ii.get("thumburl") and not p["title"].lower().endswith((".svg", ".pdf")):
            out.append({"murl": ii["thumburl"], "turl": None, "page": ii.get("descriptionurl", ""), "title": p["title"]})
    return out


def run(code, pref, t):
    saved = []

    def add(data, kind, src, page, title, min_w=260):
        name = f"{code:02d}_{len(saved) + 1:02d}.jpg"
        size = save_image(data, OUT / name, min_w)
        if size:
            saved.append({"file": name, "kind": kind, "src": src, "page": page, "title": title[:80], "size": size})
        return bool(size)

    for url in t.get("pages", []):
        got = get(url)
        time.sleep(0.4)
        if not got:
            continue
        body, ctype, final = got
        if body[:5] == b"%PDF-":
            for png, note in pdf_pages(body):
                add(png, "pdf", url, url, note)
            continue
        if ctype.startswith("image/"):
            add(body, "image", url, url, "")
            continue
        page = decode(body, ctype)
        srcs = []
        og = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', page, re.I)
        if og:
            srcs.append((og.group(1), "og:image"))
        for m in re.finditer(r"<img\b[^>]*>", page, re.I):
            tag = m.group(0)
            s = re.search(r'(?:data-src|src)\s*=\s*["\']?([^"\'\s>]+)', tag, re.I)
            a = re.search(r'alt\s*=\s*["\']([^"\']*)', tag, re.I)
            if s and not JUNK.search(s.group(1)):
                srcs.append((s.group(1), a.group(1) if a else ""))
        for m in re.finditer(r'<a\b[^>]*href=["\']([^"\']+\.(?:jpe?g|png|pdf))["\']', page, re.I):
            srcs.append((m.group(1), "link"))
        k = 0
        done = set()
        for s, alt in srcs:
            u = urllib.parse.urljoin(final, htmllib.unescape(s))
            if u in done or k >= 6:
                continue
            done.add(u)
            g2 = get(u, referer=final)
            time.sleep(0.3)
            if not g2:
                continue
            if g2[0][:5] == b"%PDF-":
                for png, note in pdf_pages(g2[0], 1):
                    k += add(png, "pdf", u, final, alt + " " + note)
            else:
                k += add(g2[0], "page", u, final, alt, 300)
    for engine, fn, per in (("bing", bing_images, 6), ("ddg", ddg_images, 5), ("commons", commons, 4), ("youtube", youtube_thumbs, 4)):
        for q in t.get("queries", {}).get(engine, []):
            res = fn(q)
            time.sleep(1.0)
            print(f"   {pref} {engine} '{q}': {len(res)}", file=sys.stderr)
            k = 0
            for r in res[:per * 3]:
                if k >= per:
                    break
                ok = False
                for u in (r["murl"], r["turl"]):
                    if not u:
                        continue
                    g2 = get(u, 8_000_000)
                    time.sleep(0.2)
                    if g2 and add(g2[0], engine, u, r["page"], r["title"]):
                        ok = True
                        break
                k += ok
    (OUT / f"{code:02d}.json").write_text(json.dumps({"pref": pref, "images": saved}, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"{pref}: saved={len(saved)}", file=sys.stderr)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    targets = json.loads((ROOT / "probe" / "image_targets.json").read_text(encoding="utf-8"))
    codes = {p: i + 1 for i, (p, _) in enumerate(PREFS)}
    with ThreadPoolExecutor(max_workers=6) as ex:
        list(ex.map(lambda kv: run(codes[kv[0]], kv[0], kv[1]), targets.items()))


if __name__ == "__main__":
    main()
