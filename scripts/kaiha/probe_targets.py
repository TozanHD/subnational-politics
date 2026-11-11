"""【調査用】指定した URL と、そこから「会派」関連リンクをたどった先（PDF 含む）を正規化して保存する。

入力: probe/targets.json  {都道府県: [URL, ...]}
出力: probe/docs/NN.json
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from crawl import PREFS, fetch_doc  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "probe" / "docs"
FOLLOW = re.compile(r"会派|党派|kaiha|名簿|meibo")


def slim(doc: dict) -> dict:
    return {
        "url": doc["url"],
        "lines": doc["lines"][:700],
        "tables": [{"heading": t["heading"], "rows": t["rows"][:150]} for t in doc["tables"][:30]],
        "links": [(h, a) for h, a in doc.get("links", []) if FOLLOW.search(a or "") or FOLLOW.search(h or "")][:80],
    }


def run(pref: str, urls: list[str]) -> dict:
    docs = []
    seen = set()
    queue = [(u, 0) for u in urls]
    while queue and len(docs) < 16:
        url, depth = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        doc = fetch_doc(url)
        time.sleep(0.4)
        if not doc:
            docs.append({"url": url, "error": True})
            continue
        docs.append(slim(doc))
        if depth == 0:
            for h, a in doc.get("links", []):
                if not h:
                    continue
                u = urllib.parse.urljoin(doc["url"], h.strip()).split("#")[0]
                same_dir = u.startswith(doc["url"].rsplit("/", 1)[0] + "/") and u != doc["url"]
                if not (re.search(r"会派|党派|名簿", a or "") or "kaiha" in h.lower()
                        or (same_dir and re.search(r"党|会|クラブ|連合|無所属", a or ""))):
                    continue
                if u not in seen and urllib.parse.urlparse(u).netloc:
                    queue.append((u, 1))
    print(f"{pref}: {sum(1 for d in docs if not d.get('error'))}/{len(docs)}", file=sys.stderr)
    return {"pref": pref, "docs": docs}


def main():
    targets = json.loads((ROOT / "probe" / "targets.json").read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    codes = {p: i + 1 for i, (p, _) in enumerate(PREFS)}

    def job(item):
        pref, urls = item
        res = run(pref, urls)
        (OUT / f"{codes[pref]:02d}.json").write_text(json.dumps(res, ensure_ascii=False, indent=0), encoding="utf-8")

    with ThreadPoolExecutor(max_workers=12) as ex:
        list(ex.map(job, targets.items()))


if __name__ == "__main__":
    main()
