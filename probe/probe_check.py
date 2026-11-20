"""一時的な調査: 知事・会派の整合性確認のための資料を保存する。"""
import json, pathlib, sys, time, urllib.parse, urllib.request
OUT = pathlib.Path("probe/check"); OUT.mkdir(parents=True, exist_ok=True)
UA = "subnational-politics-data-bot/1.0 (+https://github.com/TozanHD/subnational-politics)"
def get(u):
    req = urllib.request.Request(u, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r: return r.read()
titles = ["石田嵩人", "古謝玄太", "中道改革連合", "鈴木健太 (政治家)", "2026年福井県知事選挙", "山野之義", "平田研", "杉本達治"]
api = "https://ja.wikipedia.org/w/api.php?action=query&format=json&prop=revisions&rvprop=content&rvslots=main&redirects=1&titles="
for t in titles:
    try:
        d = json.loads(get(api + urllib.parse.quote(t)))
        page = next(iter(d["query"]["pages"].values()))
        txt = page.get("revisions", [{}])[0].get("slots", {}).get("main", {}).get("*", "")
        (OUT / f"wiki_{t.replace(' ', '_')}.txt").write_text(txt, encoding="utf-8")
    except Exception as e:
        print("fail", t, e)
    time.sleep(1)
for name, u in {"miyagi": "https://www.pref.miyagi.jp/site/kengikai/18meibo-kaiha.html",
                "tochigi": "https://www.pref.tochigi.lg.jp/p01/assembly/giin/meibo/giinmeibokaihayobi.html",
                "saitama": "https://www.pref.saitama.lg.jp/e1601/gikai-member-kaiha.html",
                "chiba": "https://www.pref.chiba.lg.jp/gikai/giji/giin/kaihabetsu.html"}.items():
    try: (OUT / f"{name}.html").write_bytes(get(u))
    except Exception as e: print("fail", name, e)
    time.sleep(1)
print("ok")
