"""正規化済みページ（extract.extract の結果）から会派別人数を読み取る方式の集まり。

どの方式も {会派名: 人数} を返す（読めなければ空の dict）。
県ごとの設定 (sites.json) で方式と引数を指定できるほか、指定が無ければ全方式を試す。
"""
from __future__ import annotations

import re
from collections import Counter

NUM = r"(\d{1,3})"
KAIHA_HEAD = re.compile(r"会派")
COUNT_HEAD = re.compile(r"(人数|議員数|所属議員|人員|数|名)")
TOTAL_WORDS = ("合計", "計", "総数", "議員定数", "定数", "現員", "欠員", "総計", "小計")


def _int(s: str) -> int | None:
    s = s.replace("人", "").replace("名", "").replace("議席", "").strip()
    m = re.fullmatch(r"\(?(\d{1,3})\)?", s)
    return int(m.group(1)) if m else None


def clean_name(name: str) -> str:
    name = re.sub(r"[\(（]\s*\d+\s*(人|名)?\s*[\)）]$", "", name).strip()
    name = re.sub(r"^\d+[\.．、]\s*", "", name)  # 番号付き
    name = re.sub(r"\s*\d+\s*(人|名)$", "", name)
    return name.strip(" ・:：")


def is_total(name: str) -> bool:
    n = name.replace(" ", "")
    return any(n == w or n.startswith(w) for w in TOTAL_WORDS)


def _valid_name(name: str) -> bool:
    if not name or len(name) > 60 or is_total(name):
        return False
    if re.fullmatch(r"[\d\s\-.,()（）人名計]+", name):
        return False
    return True


# --- 方式1: 「会派名 | 人数」の表 ------------------------------------------------

def table_counts(doc: dict, table: int | None = None, name_col: int | None = None, count_col: int | None = None,
                 heading: str | None = None) -> dict[str, int]:
    tables = doc["tables"]
    if heading:
        tables = [t for t in tables if heading in t["heading"] or any(heading in c for c in t["rows"][0])]
    if table is not None:
        tables = tables[table:table + 1]
    best: dict[str, int] = {}
    for t in tables:
        rows = t["rows"]
        if len(rows) < 2:
            continue
        hdr_idx, nc, cc = _find_header(rows) if name_col is None or count_col is None else (0, name_col, count_col)
        if nc is None:
            continue
        out: dict[str, int] = {}
        for r in rows[hdr_idx + 1:]:
            if max(nc, cc) >= len(r):
                continue
            name, cnt = clean_name(r[nc]), _int(r[cc])
            if cnt is None or not _valid_name(name):
                continue
            out[name] = out.get(name, 0) + cnt
        if sum(out.values()) > sum(best.values()):
            best = out
    return best


def _find_header(rows: list[list[str]]) -> tuple[int, int | None, int | None]:
    for i, r in enumerate(rows[:3]):
        nc = next((j for j, c in enumerate(r) if KAIHA_HEAD.search(c) and len(c) < 15), None)
        if nc is None:
            continue
        cc = next((j for j, c in enumerate(r) if j != nc and COUNT_HEAD.search(c) and len(c) < 12 and "氏名" not in c), None)
        if cc is not None:
            return i, nc, cc
    # 見出しが無い 2 列の表（会派名, 人数）
    if all(len(r) >= 2 for r in rows) and sum(1 for r in rows if _int(r[-1]) is not None) >= max(2, len(rows) - 2):
        return -1, 0, len(rows[0]) - 1
    return 0, None, None


# --- 方式2: 議員名簿の表で「会派」列を数える ------------------------------------

def roster_counts(doc: dict, table: int | None = None, col: int | None = None, heading: str | None = None) -> dict[str, int]:
    tables = doc["tables"]
    if heading:
        tables = [t for t in tables if heading in t["heading"]]
    if table is not None:
        tables = tables[table:table + 1]
    counter: Counter[str] = Counter()
    for t in tables:
        rows = t["rows"]
        hdr = next((i for i, r in enumerate(rows[:3]) if any("会派" in c and len(c) < 12 for c in r)), None)
        if hdr is None and col is None:
            continue
        c = col if col is not None else next(j for j, x in enumerate(rows[hdr]) if "会派" in x and len(x) < 12)
        start = (hdr + 1) if hdr is not None else 0
        for r in rows[start:]:
            if c < len(r):
                name = clean_name(r[c])
                if _valid_name(name):
                    counter[name] += 1
    return dict(counter)


# --- 方式3: 本文の「自由民主党 29人」「公明党（8名）」形式 -------------------------

LINE_RE = re.compile(r"^(?P<name>[^\d|]{2,40}?)\s*[:：|]?\s*[\(（]?\s*" + NUM + r"\s*(人|名)\s*[\)）]?$")


def text_counts(doc: dict, start: str | None = None, end: str | None = None) -> dict[str, int]:
    lines = doc["lines"]
    if start:
        idx = next((i for i, l in enumerate(lines) if start in l), None)
        if idx is None:
            return {}
        lines = lines[idx + 1:]
    out: dict[str, int] = {}
    for l in lines:
        if end and end in l:
            break
        for part in re.split(r"\s{2,}| \| |、", l):
            m = LINE_RE.match(part.strip())
            if m:
                name = clean_name(m.group("name"))
                if _valid_name(name):
                    out[name] = out.get(name, 0) + int(m.group(2))
    return out


READERS = {"table": table_counts, "roster": roster_counts, "text": text_counts}
