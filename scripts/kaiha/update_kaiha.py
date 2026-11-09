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
from crawl import PREFS, crawl, fetch_doc  # noqa: E402
from readers import READERS  # noqa: E402

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
    return None


def try_read(doc: dict, reader: str | None, args: dict | None) -> list[tuple[str, dict, dict[str, int]]]:
    """(方式, 引数, 結果) の候補を返す。方式未指定なら全方式を試す。"""
    out = []
    names = [reader] if reader else list(READERS)
    for name in names:
        a = dict(args or {}) if reader else {}
        try:
            res = READERS[name](doc, **a)
        except Exception as e:  # noqa: BLE001 - 想定外のページ構造
            print(f"    reader {name} error: {e}", file=sys.stderr)
            continue
        out.append((name, a, res))
    return out


def best_candidate(url: str, doc: dict, reader: str | None, args: dict | None, fixed: int):
    cands = []
    for name, a, counts in try_read(doc, reader, args):
        err = validate(counts, fixed)
        if err is None:
            # 合計が定数に近いほど、表の方式ほど優先
            cands.append((sum(counts.values()), name == "table", name, a, counts))
    if not cands:
        return None
    cands.sort(key=lambda c: (c[0], c[1]), reverse=True)
    _, _, name, a, counts = cands[0]
    return {"url": url, "reader": name, "args": a, "counts": counts}


def scrape(pref: str, romaji: str, site: dict, prev: dict | None, fixed: int) -> tuple[dict | None, list[str]]:
    log: list[str] = []
    tried: set[str] = set()
    attempts: list[tuple[str, str | None, dict | None]] = []
    if prev and prev.get("url"):
        attempts.append((prev["url"], prev.get("reader"), prev.get("args")))
    for u in site.get("urls", []):
        attempts.append((u, site.get("reader"), site.get("args")))
    for url, reader, args in attempts:
        key = f"{url}|{reader}|{json.dumps(args, sort_keys=True)}"
        if key in tried:
            continue
        tried.add(key)
        doc = fetch_doc(url)
        if doc is None:
            log.append(f"取得できません: {url}")
            continue
        found = best_candidate(url, doc, reader, args, fixed)
        if found:
            return found, log
        log.append(f"読み取り/検証に失敗: {url} ({reader or '自動'})")

    # 巡回して探し直す
    log.append("議会サイトを巡回して探し直します")
    pages = crawl(romaji, extra_seeds=site.get("seeds", []), max_pages=60)
    pages.sort(key=lambda p: -p["score"])
    for p in pages[:12]:
        found = best_candidate(p["url"], p["doc"], site.get("reader"), site.get("args"), fixed)
        if found is None and site.get("reader"):
            found = best_candidate(p["url"], p["doc"], None, None, fixed)
        if found:
            log.append(f"新しいページを発見: {p['url']}")
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
        entry = {"url": found["url"], "reader": found["reader"], "args": found["args"], "kaiha": kaiha}
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
