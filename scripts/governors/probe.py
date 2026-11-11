"""【調査用】知事の情報源（Wikidata / ウィキペディア）から取れる内容を確かめる。結果を probe/governors/ に保存する。"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "probe" / "governors"
UA = "subnational-politics-bot/1.0 (https://github.com/TozanHD/subnational-politics)"


def get(url: str) -> bytes | None:
    for i in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            print(f"  x {url[:120]}: {e}", file=sys.stderr)
            time.sleep(3 * (i + 1))
    return None


def sparql(q: str):
    b = get("https://query.wikidata.org/sparql?format=json&query=" + urllib.parse.quote(q))
    return json.loads(b)["results"]["bindings"] if b else []


def wikitext(titles: list[str]) -> dict[str, str]:
    out = {}
    for i in range(0, len(titles), 40):
        chunk = titles[i:i + 40]
        b = get("https://ja.wikipedia.org/w/api.php?action=query&format=json&prop=revisions&rvprop=content&rvslots=main"
                "&redirects=1&titles=" + urllib.parse.quote("|".join(chunk)))
        if not b:
            continue
        data = json.loads(b)["query"]
        redirect = {r["from"]: r["to"] for r in data.get("redirects", [])}
        norm = {r["from"]: r["to"] for r in data.get("normalized", [])}
        pages = {p["title"]: p for p in data["pages"].values()}
        for t in chunk:
            t2 = redirect.get(norm.get(t, t), norm.get(t, t))
            p = pages.get(t2)
            if p and "revisions" in p:
                out[t] = p["revisions"][0]["slots"]["main"]["*"]
        time.sleep(1)
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    gov = sparql("""
SELECT ?pref ?prefLabel ?gov ?govLabel ?start ?article WHERE {
  ?pref wdt:P31 wd:Q50337 .
  ?pref p:P6 ?st . ?st ps:P6 ?gov . OPTIONAL { ?st pq:P580 ?start }
  FILTER NOT EXISTS { ?st pq:P582 ?end }
  OPTIONAL { ?article schema:about ?gov ; schema:isPartOf <https://ja.wikipedia.org/> . }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "ja". }
}""")
    rows = [{"pref": g["prefLabel"]["value"], "qid": g["gov"]["value"].rsplit("/", 1)[-1], "name": g["govLabel"]["value"],
             "start": g.get("start", {}).get("value"), "article": urllib.parse.unquote(g.get("article", {}).get("value", "").rsplit("/", 1)[-1])}
            for g in gov]
    (OUT / "wikidata_governors.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wikidata governors: {len(rows)}", file=sys.stderr)
    qids = " ".join("wd:" + r["qid"] for r in rows)
    parties = sparql(f"""
SELECT ?gov ?partyLabel ?start ?end WHERE {{
  VALUES ?gov {{ {qids} }}
  ?gov p:P102 ?s . ?s ps:P102 ?party . OPTIONAL {{ ?s pq:P580 ?start }} OPTIONAL {{ ?s pq:P582 ?end }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "ja". }}
}}""")
    (OUT / "wikidata_parties.json").write_text(json.dumps(
        [{"qid": p["gov"]["value"].rsplit("/", 1)[-1], "party": p["partyLabel"]["value"], "start": p.get("start", {}).get("value"),
          "end": p.get("end", {}).get("value")} for p in parties], ensure_ascii=False, indent=1), encoding="utf-8")
    # ウィキペディア: 現職知事の一覧ページ、各知事の記事、直近の知事選挙の記事
    lists = wikitext(["日本の都道府県知事一覧", "都道府県知事の一覧"])
    for k, v in lists.items():
        (OUT / f"list_{k}.txt").write_text(v, encoding="utf-8")
    titles = [r["article"] for r in rows if r["article"]]
    arts = wikitext(titles)
    elections = {}
    for r in rows:
        t = arts.get(r["article"], "")
        (OUT / f"gov_{r['pref']}.txt").write_text(t, encoding="utf-8")
        cands = sorted(set(re.findall(r"\[\[((?:19|20)\d{2}年" + re.escape(r["pref"]) + r"知事選挙)", t)))
        if cands:
            elections[r["pref"]] = cands[-1]
    el = wikitext(list(elections.values()))
    for pref, title in elections.items():
        (OUT / f"election_{pref}.txt").write_text(el.get(title, ""), encoding="utf-8")
    (OUT / "elections.json").write_text(json.dumps(elections, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"articles: {len(arts)}, elections: {len(elections)}, election texts: {len(el)}", file=sys.stderr)


if __name__ == "__main__":
    main()
