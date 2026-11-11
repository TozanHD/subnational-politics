#!/usr/bin/env python3
"""各都道府県議会の公式サイトから会派別の議席数を取得し、src/data/kaiha.json を更新する。

仕組み（壊れにくさのための工夫）:
  1. まず前回読めた URL と方式を試す（src/data/kaiha.json に記録済み）。
  2. 次に県ごとの設定 (scripts/kaiha/sites.json) の URL と方式を試す。
  3. それでも読めなければ議会サイトを巡回してページを探し直す（URL の変更に自動で追従）。
  4. 読めた結果は「会派の合計 ≦ 定数」「欠員が多すぎない」などを検証してから採用する。
     定数は総務省データ (src/data/latest.json) を使う。
  5. どうしても読めない県は前回のデータを残したまま、失敗一覧 (kaiha-report.md) に書き出す。
     GitHub Actions がこれを Issue にして知らせる。

使い方:
  python scripts/kaiha/update_kaiha.py            # 全都道府県
  python scripts/kaiha/update_kaiha.py 群馬県 栃木県
"""
from __future__ import annotations

import datetime as dt
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import re
import urllib.parse

from crawl import PREFS, crawl, fetch_doc, find_link  # noqa: E402
from readers import KAIHA_HINT, READERS, clean_name  # noqa: E402

# 設定なしの自動探索で使う方式（誤読しにくいものだけ）
SAFE_READERS = ["table", "paren", "text", "roster", "columns"]

ROOT = Path(__file__).resolve().parents[2]
SITES = Path(__file__).resolve().parent / "sites.json"
OUTPUT = ROOT / "src" / "data" / "kaiha.json"
LATEST = ROOT / "src" / "data" / "latest.json"
REPORT = ROOT / "kaiha-report.md"


def load_json(p: Path, default: Any) -> Any:
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def validate(counts: dict[str, int], fixed: int) -> str | None:
    """問題があれば理由を返す。"""
    if not counts:
        return "会派を読み取れません"
    total = sum(counts.values())
    if len(counts) < 2:
        return f"会派が {len(counts)} つしかありません"
    if len(counts) > 30:
        return f"会派が多すぎます ({len(counts)})"
    if any(v <= 0 for v in counts.values()):
        return "0 人以下の会派があります"
    if total > fixed:
        return f"会派の合計 {total} が定数 {fixed} を超えています"
    if total < fixed - max(6, round(fixed * 0.12)):
        return f"会派の合計 {total} が定数 {fixed} に比べて少なすぎます"
    if max(counts.values()) > fixed * 0.9:
        return "1 会派が 9 割を超えています（読み取り誤りの可能性）"
    hinted = sum(v for k, v in counts.items() if KAIHA_HINT.search(k))
    if hinted < total * 0.5:
        return "会派名らしくない名前が多すぎます（読み取り誤りの可能性）"
    return None


def run_reader(doc: dict, reader: str, args: dict | None) -> dict[str, int]:
    try:
        return READERS[reader](doc, **(args or {}))
    except Exception as e:  # noqa: BLE001 - 想定外のページ構造
        print(f"    reader {reader} error: {e}", file=sys.stderr)
        return {}


def try_read(doc: dict, reader: str | None, args: dict | None) -> list[tuple[str, dict, dict[str, int]]]:
    """(方式, 引数, 結果) の候補を返す。方式未指定なら安全な方式を全部試す。"""
    if reader:
        return [(reader, args or {}, run_reader(doc, reader, args))]
    return [(name, {}, run_reader(doc, name, None)) for name in SAFE_READERS]


def apply_aliases(counts: dict[str, int], aliases: dict[str, str] | None) -> dict[str, int]:
    if not aliases:
        return counts
    out: dict[str, int] = {}
    for k, v in counts.items():
        k2 = aliases.get(k, k)
        out[k2] = out.get(k2, 0) + v
    return out


def read_source(src: dict, fixed: int) -> tuple[dict | None, str]:
    """設定 1 件を実行する。(結果, ログ) を返す。"""
    url = src["url"]
    doc = fetch_doc(url)
    if doc is None:
        return None, f"取得できません: {url}"
    if src.get("link"):
        target = find_link(doc, src["link"])
        if not target:
            return None, f"リンク /{src['link']}/ が見つかりません: {url}"
        url = target
        doc = fetch_doc(url)
        if doc is None:
            return None, f"取得できません: {url}"
    if src.get("subpages"):
        rx = re.compile(src["subpages"])
        urls = []
        for href, _ in doc.get("links", []):
            u = urllib.parse.urljoin(doc["url"], (href or "").strip()).split("#")[0]
            if href and rx.search(u) and u not in urls:
                urls.append(u)
        counts: dict[str, int] = {}
        for u in urls[:30]:
            sub = fetch_doc(u)
            time.sleep(0.3)
            if sub is None:
                return None, f"取得できません: {u}"
            for k, v in run_reader(sub, src["reader"], src.get("args")).items():
                counts[k] = counts.get(k, 0) + v
    else:
        counts = run_reader(doc, src["reader"], src.get("args"))
    counts = apply_aliases(counts, src.get("aliases"))
    err = validate(counts, fixed)
    if err:
        return None, f"検証に失敗 ({err}): {url} [{src['reader']}] {counts}"
    return {"url": url if not src.get("subpages") else src["url"], "reader": src["reader"], "counts": counts}, ""


def best_candidate(url: str, doc: dict, fixed: int):
    cands = []
    for name, a, counts in try_read(doc, None, None):
        if validate(counts, fixed) is None:
            cands.append((sum(counts.values()), name == "table", name, counts))
    if not cands:
        return None
    cands.sort(key=lambda c: (c[0], c[1]), reverse=True)
    _, _, name, counts = cands[0]
    return {"url": url, "reader": name, "counts": counts}


def scrape(pref: str, romaji: str, site: dict, prev: dict | None, fixed: int) -> tuple[dict | None, list[str]]:
    log: list[str] = []
    for src in site.get("sources", []):
        found, msg = read_source(src, fixed)
        if found:
            return found, log
        log.append(msg)

    # 設定どおりに読めない（ページの移転・改装）→ 議会サイトを巡回して探し直す
    log.append("議会サイトを巡回して探し直します")
    seeds = [s["url"] for s in site.get("sources", [])]
    if prev and prev.get("url"):
        seeds.insert(0, prev["url"])
    pages = crawl(romaji, extra_seeds=seeds, max_pages=50)
    pages.sort(key=lambda p: -p["score"])
    for p in pages[:12]:
        found = best_candidate(p["url"], p["doc"], fixed)
        if found:
            log.append(f"代わりのページで読み取りました（設定の見直しを推奨）: {p['url']}")
            found["auto"] = True
            return found, log
    return None, log


def main(argv: list[str]) -> int:
    sites: dict[str, dict] = load_json(SITES, {})
    latest = load_json(LATEST, None)
    if latest is None:
        print("src/data/latest.json がありません", file=sys.stderr)
        return 1
    fixed_by_pref = {p["name"]: p["assembly"]["fixed"] for p in latest["prefectures"]}
    state: dict[str, Any] = load_json(OUTPUT, {"prefectures": {}})
    prev_all: dict[str, dict] = state.get("prefectures", {})
    only = set(argv)
    targets = [(p, r) for p, r in PREFS if not only or p in only]
    today = dt.datetime.now(dt.timezone.utc).astimezone(dt.timezone(dt.timedelta(hours=9))).date().isoformat()

    def run(t):
        pref, romaji = t
        t0 = time.time()
        found, log = scrape(pref, romaji, sites.get(pref, {}), prev_all.get(pref), fixed_by_pref[pref])
        print(f"{pref}: {'OK' if found else 'NG'} ({time.time() - t0:.0f}s) {found['url'] if found else ''}", file=sys.stderr)
        return pref, found, log

    with ThreadPoolExecutor(max_workers=10) as ex:
        results = list(ex.map(run, targets))

    failures = []
    new_all = dict(prev_all)
    for pref, found, log in results:
        prev = prev_all.get(pref)
        if found is None:
            failures.append((pref, log, prev))
            if prev and not prev.get("stale"):
                new_all[pref] = {**prev, "stale": True}
            continue
        kaiha = [{"name": k, "seats": v} for k, v in sorted(found["counts"].items(), key=lambda kv: -kv[1])]
        entry = {"url": found["url"], "kaiha": kaiha}
        if found.get("auto"):
            entry["auto"] = True
            failures.append((pref, log, prev))  # 読めたが設定の見直しが必要なので報告する
        if prev and {k: prev.get(k) for k in entry} == entry and not prev.get("stale"):
            continue  # 変化なし（取得日も変えない）
        entry["fetchedAt"] = today
        new_all[pref] = entry

    order = [p for p, _ in PREFS]
    out = {"prefectures": {p: new_all[p] for p in order if p in new_all}}
    if out != state:
        OUTPUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"更新: {OUTPUT}", file=sys.stderr)
    else:
        print("変更なし", file=sys.stderr)

    if failures and not only:
        lines = [
            "会派別議席数を自動取得できなかった都道府県があります。",
            "サイトには前回取得したデータ（無い場合は総務省の所属党派別データのみ）を表示しています。",
            "",
            "対応方法: `scripts/kaiha/sites.json` の該当県に正しい URL と読み取り方式を設定してください。",
            "",
        ]
        for pref, log, prev in failures:
            lines.append(f"### {pref}")
            lines.append(f"- 前回の取得: {prev.get('fetchedAt') if prev else 'なし'}")
            lines += [f"- {l}" for l in log[-6:]]
            lines.append("")
        REPORT.write_text("\n".join(lines), encoding="utf-8")
    elif REPORT.exists() and not only:
        REPORT.unlink()
    print(f"成功 {len(results) - len(failures)} / {len(results)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
