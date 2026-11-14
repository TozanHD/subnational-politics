"""一時的な調査: 総務省の所属党派別人員調の過去分（2008〜2012年末）を探して保存する。"""
import json, re, sys, time, urllib.parse, urllib.request, html, pathlib
sys.path.insert(0, "scripts")
from update_data import LinkParser, decode_html, USER_AGENT
OUT = pathlib.Path("probe/soumu"); OUT.mkdir(parents=True, exist_ok=True)
def get(u):
    req = urllib.request.Request(u, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as r: return r.read()
seeds = ["https://www.soumu.go.jp/senkyo/senkyo_s/data/syozoku/index.html",
         "https://www.soumu.go.jp/senkyo/senkyo_s/data/index.html"]
queue, seen, pages, files = list(seeds), set(), [], []
while queue and len(seen) < 80:
    u = queue.pop(0)
    if u in seen: continue
    seen.add(u)
    try: body = get(u)
    except Exception as e: pages.append({"url": u, "error": str(e)}); continue
    p = LinkParser(); p.feed(decode_html(body))
    text = html.unescape("".join(p.text))
    pages.append({"url": u, "title": re.sub(r"\s+", " ", text)[:300]})
    for href, a in p.links:
        au = urllib.parse.urljoin(u, href.strip()).split("#")[0]
        a = re.sub(r"\s+", " ", a).strip()
        if re.search(r"\.(xlsx?|pdf|zip|csv)$", au, re.I):
            files.append({"page": u, "url": au, "anchor": a})
        else:
            pp = urllib.parse.urlparse(au)
            if pp.netloc == "www.soumu.go.jp" and pp.path.startswith("/senkyo/") and ("syozoku" in pp.path or "所属党派" in a) and au not in seen:
                queue.append(au)
    time.sleep(1)
json.dump({"pages": pages, "files": files}, open(OUT / "index.json", "w"), ensure_ascii=False, indent=1)
want = re.compile(r"平成(20|21|22|23|24)年|20(08|09|10|11|12)年")
got = 0
for f in files:
    if want.search(f["anchor"]) or want.search(f["page"]):
        name = re.sub(r"[^\w.]", "_", f["url"].split("/")[-1])
        try:
            (OUT / name).write_bytes(get(f["url"])); got += 1; time.sleep(1)
        except Exception as e: print("fail", f["url"], e)
print("pages", len(pages), "files", len(files), "downloaded", got)
