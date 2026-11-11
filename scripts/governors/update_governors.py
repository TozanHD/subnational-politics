#!/usr/bin/env python3
"""都道府県知事の経歴（過去の所属政党・派閥）と、当選した知事選挙での推薦・支持を取得し、
src/data/governors.json を更新する。

情報源（いずれもウィキペディア日本語版。編集者によって随時更新される）:
  1. 「日本の都道府県知事一覧」… 現職の知事、就任日、期数、主な前職
  2. 各知事の記事の経歴欄（{{政治家}} の「所属政党」）… 過去の所属政党と派閥
  3. 当選した知事選挙の記事の候補者表 … 党派欄の推薦・支持の注記

壊れにくさのための工夫:
  * 現職の特定は一覧ページを使う（Wikidata は退任済みの知事が残っていることがあるため使わない）
  * 都道府県ごとに独立して処理し、読めなかった県は前回のデータを残す
  * 一覧ページから 47 都道府県が読めなければ、何も更新せずに失敗する

使い方:
  python scripts/governors/update_governors.py
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "src" / "data" / "governors.json"
API = "https://ja.wikipedia.org/w/api.php"
UA = "subnational-politics-bot/1.0 (https://github.com/TozanHD/subnational-politics)"
LIST_PAGE = "日本の都道府県知事一覧"
WIKI = "https://ja.wikipedia.org/wiki/"

PREFECTURES = [
    "北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県",
    "茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県",
    "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県", "岐阜県",
    "静岡県", "愛知県", "三重県", "滋賀県", "京都府", "大阪府", "兵庫県",
    "奈良県", "和歌山県", "鳥取県", "島根県", "岡山県", "広島県", "山口県",
    "徳島県", "香川県", "愛媛県", "高知県", "福岡県", "佐賀県", "長崎県",
    "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県",
]


# ---------------------------------------------------------------------------
# 取得
# ---------------------------------------------------------------------------

def http_json(url: str) -> Any:
    last: Exception | None = None
    for i in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(3 * (i + 1))
    raise RuntimeError(f"取得失敗 {url[:100]}: {last}")


def fetch_wikitext(titles: list[str]) -> dict[str, str]:
    """記事名 → 本文（ウィキテキスト）。転送ページは転送先の本文を返す。"""
    out: dict[str, str] = {}
    for i in range(0, len(titles), 40):
        chunk = titles[i:i + 40]
        data = http_json(f"{API}?action=query&format=json&prop=revisions&rvprop=content&rvslots=main&redirects=1&titles="
                         + urllib.parse.quote("|".join(chunk)))["query"]
        norm = {r["from"]: r["to"] for r in data.get("normalized", [])}
        redirect = {r["from"]: r["to"] for r in data.get("redirects", [])}
        pages = {p["title"]: p for p in data["pages"].values()}
        for t in chunk:
            t2 = norm.get(t, t)
            p = pages.get(redirect.get(t2, t2))
            if p and "revisions" in p:
                out[t] = p["revisions"][0]["slots"]["main"]["*"]
        time.sleep(1)
    return out


# ---------------------------------------------------------------------------
# ウィキテキストの整形
# ---------------------------------------------------------------------------

def strip_markup(s: str) -> str:
    """リンク・参照・装飾を取り除いて読める文字列にする（注記 {{Efn}} の中身は残す）。"""
    s = re.sub(r"<ref[^>/]*/>", "", s)
    s = re.sub(r"<ref[^>]*>.*?</ref>", "", s, flags=re.S)
    s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
    s = re.sub(r"<br\s*/?>", " ", s, flags=re.I)
    s = re.sub(r"</?(small|span|sup|sub|big|b|i|s)[^>]*>", "", s, flags=re.I)
    s = re.sub(r"\[\[(?:ファイル|File|画像|Image):[^\]]*\]\]", "", s)
    s = re.sub(r"\[\[[^\]|]*\|([^\]]*)\]\]", r"\1", s)
    s = re.sub(r"\[\[([^\]]*)\]\]", r"\1", s)
    for _ in range(4):  # 入れ子のテンプレートを内側から処理する
        s = re.sub(r"\{\{\s*(?:Efn2?|efn2?|Efn-[a-z]+|Refnest|refnest|注釈)\s*\|(?:\s*group\s*=[^|}]*\|)?([^{}]*)\}\}", r"（\1）", s)
        s = re.sub(r"\{\{\s*(?:Ruby|ruby)\s*\|([^|{}]*)\|[^{}]*\}\}", r"\1", s)
        s = re.sub(r"\{\{\s*(?:small|Small|larger|Larger|big|Big|nowrap|Nowrap|nobr|Nobr|lang|Lang\|ja)\s*\|([^{}]*)\}\}", lambda m: m.group(1).split("|")[-1], s)
        s = re.sub(r"\{\{\s*(?:Start date|start date|Start Date)\s*\|\s*(\d{4})\s*\|\s*(\d{1,2})\s*\|\s*(\d{1,2})[^{}]*\}\}", r"\1年\2月\3日", s)
        s = re.sub(r"\{\{\s*(?:Display none|display none|R|r|Sfn|sfn|Refnest|JPN|flagicon)[^{}]*\}\}", "", s)
        s = re.sub(r"\{\{[^{}]*\}\}", "", s)
    s = re.sub(r"\[\[(?:ファイル|File|画像|Image):[^\]]*\]\]", "", s)
    s = re.sub(r"\[\[[^\]|]*\|([^\]]*)\]\]", r"\1", s)
    s = re.sub(r"\[\[([^\]]*)\]\]", r"\1", s)
    s = re.sub(r"\[https?://\S+\s+([^\]]*)\]", r"\1", s)
    s = s.replace("'''", "").replace("''", "")
    s = re.sub(r"[ \t　]+", " ", s)
    s = re.sub(r"\s*→\s*", "→", s)
    s = re.sub(r"（\s*", "（", s)
    s = re.sub(r"\s*）", "）", s)
    s = re.sub(r"\(\s*", "(", s)
    return s.strip(" ・|")


def template_params(text: str, name: str) -> dict[str, str] | None:
    """{{name|k=v|...}} の引数を返す（入れ子の {{ }} や [[ ]] の中の | は区切りとみなさない）。"""
    i = text.find("{{" + name)
    if i < 0:
        return None
    depth_t = depth_l = 0
    j = i
    parts: list[str] = []
    buf = ""
    while j < len(text):
        two = text[j:j + 2]
        if two == "{{":
            depth_t += 1
            buf += two
            j += 2
            continue
        if two == "}}":
            depth_t -= 1
            if depth_t == 0:
                parts.append(buf)
                break
            buf += two
            j += 2
            continue
        if two == "[[":
            depth_l += 1
            buf += two
            j += 2
            continue
        if two == "]]":
            depth_l -= 1
            buf += two
            j += 2
            continue
        if text[j] == "|" and depth_t == 1 and depth_l == 0:
            parts.append(buf)
            buf = ""
            j += 1
            continue
        buf += text[j]
        j += 1
    out: dict[str, str] = {}
    for part in parts[1:]:
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def link_target(s: str) -> str | None:
    m = re.search(r"\[\[([^\]|#]+)", s)
    return m.group(1).strip() if m else None


def split_cells(row: str) -> list[str]:
    """表の 1 行を、行頭の「|」「!」で始まるセルに分ける（同じ行の「||」区切りにも対応）。"""
    cells: list[str] = []
    for line in row.split("\n"):
        if line.startswith(("|", "!")) and not line.startswith(("|-", "|}", "{|", "|+")):
            body = line[1:]
            parts = re.split(r"\|\||!!", body)
            cells.extend(parts)
        elif cells:
            cells[-1] += "\n" + line
    out = []
    for c in cells:
        # 「style="..." |本文」の属性部分を落とす（リンクやテンプレートの中の | は対象外）
        m = re.match(r'^\s*[a-z\-]+\s*=\s*"[^"]*"\s*(?:[a-z\-]+\s*=\s*"[^"]*"\s*)*\|(.*)$', c, re.S)
        out.append(m.group(1) if m else c)
    return out


# ---------------------------------------------------------------------------
# 1. 現職知事の一覧
# ---------------------------------------------------------------------------

def parse_list(text: str) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for row in re.split(r"\n\|-", text):
        m = re.search(r"^!\s*\{\{Display none\|\d+/\}\}\s*\[\[([^\]|]+)", row.strip(), re.M)
        if not m or m.group(1) not in PREFECTURES:
            continue
        pref = m.group(1)
        cells = split_cells(row.strip().split("\n", 1)[1] if "\n" in row.strip() else "")
        name_i = next((i for i, c in enumerate(cells) if re.search(r"\{\{\s*Ruby", c)), None)
        if name_i is None:
            continue
        name_cell = cells[name_i]
        article = link_target(name_cell)
        name = strip_markup(name_cell)
        rest = cells[name_i + 1:]
        if len(rest) < 7:
            continue
        since_cell, _end, term, party, _school, career = rest[1], rest[2], rest[3], rest[4], rest[5], rest[6]
        since = re.search(r"((?:19|20)\d{2})年.*?(\d{1,2})月(\d{1,2})日", strip_markup(since_cell))
        career_items = [strip_markup(x) for x in re.split(r"\n\*|<br\s*/?>", "\n" + career) if strip_markup(x)]
        result[pref] = {
            "name": name.replace(" ", ""),
            "article": article,
            "since": f"{since.group(1)}-{int(since.group(2)):02d}-{int(since.group(3)):02d}" if since else None,
            "sinceElection": link_target(since_cell) if link_target(since_cell) and "知事選挙" in link_target(since_cell) else None,
            "term": int(re.sub(r"\D", "", strip_markup(term)) or 0) or None,
            "party": strip_markup(party) or None,
            "career": career_items[:6],
        }
    return result


# ---------------------------------------------------------------------------
# 2. 知事の記事: 所属政党の履歴（派閥を含む）と、出馬した知事選挙
# ---------------------------------------------------------------------------

def infobox_field(text: str, field: str) -> str | None:
    m = re.search(r"^\|\s*" + re.escape(field) + r"\s*=(.*?)(?=^\|\s*[^|=\n]+?\s*=|^\}\})", text, re.S | re.M)
    if not m:
        return None
    v = strip_markup(m.group(1))
    return v or None


def party_history(article_text: str) -> str | None:
    v = infobox_field(article_text, "所属政党")
    if not v:
        return None
    v = re.sub(r"^（(.*?)→）\s*", r"\1→", v)  # 「（無所属→）自由民主党」→「無所属→自由民主党」
    v = re.sub(r"（([^（）]*?)→）", r"\1→", v)
    v = re.sub(r"\s+", " ", v).replace(" →", "→").replace("→ ", "→")
    return v.replace("→", " → ").strip()


def election_titles(pref: str, *texts: str) -> list[str]:
    titles: set[str] = set()
    for t in texts:
        titles.update(re.findall(r"\[\[\s*((?:19|20)\d{2}年" + re.escape(pref) + r"知事選挙)", t))
    return sorted(titles, reverse=True)


# ---------------------------------------------------------------------------
# 3. 知事選挙の記事: 投票日と、当選者の推薦・支持
# ---------------------------------------------------------------------------

def election_date(text: str, title: str) -> dt.date | None:
    for field in ("投票日", "選挙日", "執行日", "election_date"):
        v = infobox_field(text, field)
        if v:
            m = re.search(r"((?:19|20)\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日", v)
            if m:
                return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.search(r"(?:投票日|投開票日|執行日|投票)[^\n]{0,20}?((?:19|20)\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日", text)
    if m:
        return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    y = re.match(r"(\d{4})年", title)
    return dt.date(int(y.group(1)), 12, 31) if y else None


def tidy_support(s: str) -> str:
    """「（推薦）自民・公明」→「推薦：自民・公明」のように表記をそろえる。"""
    s = re.sub(r"[（(](推薦|支持|支援)[）)]\s*", r"\1：", s.strip("。 "))
    s = re.sub(r"(推薦|支持|支援)\s*[:：]\s*", r"\1：", s)
    return re.sub(r"\s+", " ", s).strip()


def endorsements(text: str, name: str, article: str | None) -> str | None:
    """候補者表から当選者の行を探し、党派欄の注記（推薦・支持）と推薦・支持の列を返す。"""
    keys = {name, name.replace(" ", "")}
    if article:
        keys.add(article.split(" (")[0])
    res = template_params(text, "選挙結果 (日本の首長)") or template_params(text, "選挙結果(日本の首長)")
    if res and "当選者名" in res:
        winner = strip_markup(res["当選者名"]).replace(" ", "")
        if any(k and k.replace(" ", "") == winner for k in keys):
            return tidy_support(strip_markup(res.get("当選者推薦・支持", "")))
        return None  # 当選者が本人ではない選挙
    for table in re.findall(r"\{\|.*?\n\|\}", text, re.S):
        rows = re.split(r"\n\|-[^\n]*", table)
        header = next((r for r in rows if re.search(r"^!", r, re.M)), "")
        hcells = [strip_markup(c) for c in split_cells(header)]
        if not any("党派" in c or "推薦" in c or "支持" in c for c in hcells):
            continue
        for r in rows:
            plain = strip_markup(r).replace(" ", "")
            if not any(k.replace(" ", "") in plain for k in keys if k):
                continue
            cells = split_cells(r)
            if len(cells) < 2:
                continue
            notes: list[str] = []
            for i, c in enumerate(cells):
                h = hcells[i] if i < len(hcells) else ""
                if "推薦" in h or "支持" in h:
                    v = strip_markup(c)
                    if v and v not in ("-", "－", "なし"):
                        notes.append(f"{h}: {v}" if h not in ("推薦・支持", "推薦/支持") else v)
                elif "党派" in h or "政党" in h:
                    for m in re.finditer(r"\{\{\s*(?:Efn2?|efn2?|Efn-[a-z]+|注釈)\s*\|(?:\s*group\s*=[^|}]*\|)?([^{}]*)\}\}", c):
                        v = strip_markup(m.group(1))
                        if re.search(r"推薦|支持|支援", v):
                            notes.append(v)
                    v = strip_markup(re.sub(r"\{\{\s*(?:Efn2?|efn2?)[^{}]*\}\}", "", c))
                    for m in re.finditer(r"[（(]([^（）()]*(?:推薦|支持)[^（）()]*)[）)]", v):
                        notes.append(m.group(1))
            if notes:
                return tidy_support("、".join(dict.fromkeys(n.strip("。 ") for n in notes)))
            return ""
    return None


# ---------------------------------------------------------------------------
# 全体
# ---------------------------------------------------------------------------

def build(fetch: Callable[[list[str]], dict[str, str]], today: dt.date) -> tuple[dict[str, dict], list[str]]:
    lst = fetch([LIST_PAGE]).get(LIST_PAGE, "")
    current = parse_list(lst)
    missing = [p for p in PREFECTURES if p not in current]
    if len(current) < 40:
        raise RuntimeError(f"知事一覧から {len(current)} 都道府県しか読めませんでした（ページの構成が変わった可能性）")
    log = [f"一覧から読めなかった: {', '.join(missing)}"] if missing else []
    arts = fetch([c["article"] for c in current.values() if c.get("article")])
    # 出馬した知事選挙（新しい順）
    cand: dict[str, list[str]] = {}
    for pref, c in current.items():
        text = arts.get(c.get("article") or "", "")
        titles = election_titles(pref, text)
        if c.get("sinceElection") and c["sinceElection"] not in titles:
            titles.append(c["sinceElection"])
        cand[pref] = sorted(set(titles), reverse=True)
    el = fetch(sorted({t for ts in cand.values() for t in ts[:4]}))
    out: dict[str, dict] = {}
    for pref in PREFECTURES:
        c = current.get(pref)
        if not c:
            continue
        text = arts.get(c.get("article") or "", "")
        entry: dict[str, Any] = {
            "name": c["name"],
            "url": WIKI + urllib.parse.quote(c["article"]) if c.get("article") else None,
            "since": c["since"],
            "term": c["term"],
            "party": c["party"],
            "career": c["career"],
            "partyHistory": party_history(text) if text else None,
        }
        # 当選した直近の知事選挙: 投票日が今日以前で、候補者表に本人がいるもののうち最新
        for title in cand.get(pref, [])[:4]:
            et = el.get(title)
            if not et:
                continue
            d = election_date(et, title)
            if d and d > today:
                continue
            e = endorsements(et, c["name"], c.get("article"))
            if e is None:
                continue
            entry["election"] = {"title": title, "url": WIKI + urllib.parse.quote(title),
                                 "date": d.isoformat() if d else None, "support": e or None}
            break
        else:
            log.append(f"{pref}: 当選した知事選挙の候補者表を読み取れませんでした")
        if not entry["partyHistory"]:
            log.append(f"{pref}: 所属政党の履歴が記事にありません")
        out[pref] = entry
    return out, log


def main() -> int:
    today = dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date()
    try:
        data, log = build(fetch_wikitext, today)
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    for line in log:
        print("  " + line, file=sys.stderr)
    prev = json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.exists() else {"prefectures": {}}
    merged = dict(prev.get("prefectures", {}))
    for pref, entry in data.items():
        old = merged.get(pref)
        # 本人が同じで今回読めなかった項目は前回の値を残す
        if old and old.get("name") == entry["name"]:
            for k in ("partyHistory", "election"):
                if not entry.get(k) and old.get(k):
                    entry[k] = old[k]
        merged[pref] = entry
    out = {"source": WIKI + urllib.parse.quote(LIST_PAGE), "prefectures": {p: merged[p] for p in PREFECTURES if p in merged}}
    if out != prev:
        OUTPUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"更新: {OUTPUT}", file=sys.stderr)
    else:
        print("変更なし", file=sys.stderr)
    print(f"知事 {len(data)} 人", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
