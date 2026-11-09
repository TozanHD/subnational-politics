"""正規化済みページ（extract.extract / extract_pdf の結果）から会派別人数を読み取る方式の集まり。

どの方式も {会派名: 人数} を返す（読めなければ空の dict）。
県ごとの設定 (sites.json) で方式と引数を指定する。

方式一覧:
  table    … 「会派名 | 人数」の表
  roster   … 議員名簿の表の「会派」列を数える
  paren    … 「自由民主党(30名)」「公明党 (3)」のように会派名の直後に人数がある行・セル
  text     … 「自由民主党 29人」のような行
  blocks   … 会派名の行 → 議員名… → 「計29人」の行 が繰り返される
  grouped  … 会派名の行 → 議員名… が繰り返される（議員名を数える）
  columns  … 表の 1 行に会派名、別の 1 行に人数が並ぶ（横向きの表）
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter

TOTAL_WORDS = ("合計", "計", "総数", "議員定数", "定数", "現員", "総計", "小計", "人数", "会派名", "会派", "氏名")
# 会派名ではありえない語（選挙区別・委員会別の表を誤って読まないため）
NOT_KAIHA = re.compile(r"(選挙区|委員会|[市郡町村区]$|地域$|^\d|議席|ページ|定数|現在|令和|平成|年|月|日$|期$|^(会長|副会長|幹事長|副幹事長|会員|相談役|顧問|代表|団長|副団長|議長|副議長|委員長|副委員長|所属議員|政審会長|政調会長)$)")
KAIHA_HINT = re.compile(r"(党|会|団|クラブ|倶楽部|ネット|派|議員|無所属|連合|フォーラム|の声|みらい|未来|改革|維新|県政|民主|自民|公明|共産|社民|参政|新政|チーム)")
JP_NAME = re.compile(r"^[぀-ヿ㐀-鿿豈-﫿々〆ヶ\U00020000-\U0002ffff]{1,6}[ 　][぀-ヿ㐀-鿿豈-﫿々〆ヶ\U00020000-\U0002ffffー]{1,7}$")
CJK = r"[぀-ヿ㐀-鿿豈-﫿々〆ヶー・]"


def collapse_spaced(s: str) -> str:
    """PDF で「自 由 民 主 党」のように 1 文字ずつ空白が入るのを詰める。"""
    tokens = s.split(" ")
    if len(tokens) >= 3 and sum(1 for t in tokens if len(t) == 1) >= len(tokens) * 0.7:
        return re.sub(rf"(?<={CJK}) (?={CJK})", "", s)
    return s


def clean_name(name: str) -> str:
    name = unicodedata.normalize("NFKC", name)
    name = re.sub(r"[​-‏﻿⁠]", "", name)
    name = re.sub(r"[\U000e0100-\U000e01ef︀-️]", "", name)  # 異体字セレクタ
    name = re.sub(r"\s+", " ", name).strip()
    name = collapse_spaced(name)
    name = re.sub(r"https?://\S+", "", name)
    name = re.sub(r"\((外部サイト|別ウィンドウ|外部リンク|新しいウィンドウ)[^)]*\)", "", name)
    name = re.sub(r"[\(（]\s*\d+\s*(人|名)?\s*[\)）]", "", name)
    name = re.sub(r"【\s*\d+\s*(人|名)\s*】", "", name)
    name = re.sub(r"\s*\d+\s*(人|名)$", "", name)
    name = re.sub(r"^[\d\.．、\s]+", "", name)
    name = re.sub(r"^[○〇●◎■□◆◇・※\-\s]+", "", name)
    # 末尾の略称「(自民)」は外す（ただし無所属(○○) のように中身が本体の場合は残す）
    m = re.match(r"^(.{5,}?)\s*[\(（]([^()（）]{1,8})[\)）]$", name)
    if m and (not m.group(1).startswith("無所属") or set(m.group(2)) <= set(m.group(1))):
        name = m.group(1)
    name = re.sub(r"・\s+", "・", name)
    return name.strip(" ・:：|")


def is_total(name: str) -> bool:
    n = name.replace(" ", "")
    return n in TOTAL_WORDS or n.startswith(("合計", "計", "総計", "小計")) or "欠員" in n


def valid_kaiha_name(name: str) -> bool:
    if not name or len(name) < 2 or len(name) > 60 or is_total(name):
        return False
    if re.fullmatch(r"[\d\s\-.,()（）人名計]+", name):
        return False
    if NOT_KAIHA.search(name) and not KAIHA_HINT.search(name):
        return False
    if re.search(r"(選挙区|委員会)", name):
        return False
    return True


def _int(s: str) -> int | None:
    s = unicodedata.normalize("NFKC", s).replace("人", "").replace("名", "").replace("議席", "").strip()
    m = re.fullmatch(r"\(?(\d{1,3})\)?", s)
    return int(m.group(1)) if m else None


def is_person(token: str) -> bool:
    t = unicodedata.normalize("NFKC", token).strip()
    t = re.sub(r"[\(（].*?[\)）]", "", t).strip()
    return bool(JP_NAME.match(t)) and not KAIHA_HINT.search(t.replace(" ", ""))


def _tables(doc: dict, table: int | None, heading: str | None) -> list[dict]:
    tables = doc["tables"]
    if heading:
        tables = [t for t in tables if heading in t["heading"] or any(heading in c for c in t["rows"][0])]
    if table is not None:
        tables = tables[table:table + 1]
    return tables


def _add(out: dict[str, int], name: str, n: int) -> None:
    name = clean_name(name)
    if valid_kaiha_name(name) and n > 0:
        out[name] = out.get(name, 0) + n


# --- table: 「会派名 | 人数」の表 ------------------------------------------------

def table_counts(doc: dict, table: int | None = None, name_col: int | None = None, count_col: int | None = None,
                 heading: str | None = None) -> dict[str, int]:
    best: dict[str, int] = {}
    for t in _tables(doc, table, heading):
        rows = t["rows"]
        if len(rows) < 2:
            continue
        if name_col is not None and count_col is not None:
            hdr, nc, cc = -1, name_col, count_col
        else:
            hdr, nc, cc = _find_header(rows)
        if nc is None:
            continue
        out: dict[str, int] = {}
        for r in rows[hdr + 1:]:
            if max(nc, cc) >= len(r):
                continue
            n = _int(r[cc])
            if n is not None:
                _add(out, r[nc], n)
        if sum(out.values()) > sum(best.values()):
            best = out
    return best


def _find_header(rows: list[list[str]]) -> tuple[int, int | None, int | None]:
    for i, r in enumerate(rows[:3]):
        rr = [c.replace(" ", "") for c in r]
        nc = next((j for j, c in enumerate(rr) if "会派" in c and len(c) < 15), None)
        if nc is None:
            continue
        cc = next((j for j, c in enumerate(rr) if j != nc and re.search(r"(人数|議員数|所属議員|人員|総数|議席数|現員|^数$|^人$|^計$)", c) and len(c) < 12), None)
        if cc is not None:
            return i, nc, cc
    return 0, None, None


# --- roster: 議員名簿の「会派」列を数える ---------------------------------------

def roster_counts(doc: dict, table: int | None = None, col: int | None = None, heading: str | None = None,
                  header: str = "会派") -> dict[str, int]:
    counter: Counter[str] = Counter()
    for t in _tables(doc, table, heading):
        rows = t["rows"]
        hdr = next((i for i, r in enumerate(rows[:3]) if any(header in c.replace(" ", "") and len(c) < 12 for c in r)), None)
        if hdr is None and col is None:
            continue
        width = len(rows[hdr]) if hdr is not None else None
        c = col if col is not None else next(j for j, x in enumerate(rows[hdr]) if header in x.replace(" ", "") and len(x) < 12)
        for r in rows[(hdr + 1 if hdr is not None else 0):]:
            # 先頭列が結合されて行が短い場合（50音の見出し列など）は右端に揃える
            idx = c - (width - len(r)) if width and len(r) < width else c
            if 0 <= idx < len(r):
                name = clean_name(r[idx])
                if valid_kaiha_name(name):
                    counter[name] += 1
    return dict(counter)


# --- paren: 「自由民主党(30名)」 ---------------------------------------------------

PAREN = re.compile(r"^(?P<name>[^|()（）【】]{2,50}?)\s*(?:[\(（]\s*(?P<n1>\d{1,3})\s*(?:人|名)?\s*[\)）]|【\s*(?P<n2>\d{1,3})\s*(?:人|名)\s*】)")


LONE_COUNT = re.compile(r"^(?:[\(（]\s*(\d{1,3})\s*(?:人|名)\s*[\)）]|【\s*(\d{1,3})\s*(?:人|名)\s*】)$")


def paren_counts(doc: dict, start: str | None = None, end: str | None = None) -> dict[str, int]:
    out: dict[str, int] = {}
    prev = ""
    for part in _parts(doc, start, end):
        lone = LONE_COUNT.match(part)
        if lone and prev:
            _add(out, prev, int(lone.group(1) or lone.group(2)))
        else:
            m = PAREN.match(part)
            if m:
                _add(out, m.group("name"), int(m.group("n1") or m.group("n2")))
        prev = part
    return out


def _parts(doc: dict, start: str | None, end: str | None) -> list[str]:
    lines = doc["lines"]
    if start:
        idx = next((i for i, l in enumerate(lines) if start in l), None)
        if idx is None:
            return []
        lines = lines[idx + 1:]
    out = []
    for l in lines:
        if end and end in l:
            break
        out += [p.strip() for p in l.split(" | ") if p.strip()]
    return out


# --- text: 「自由民主党 29人」 -----------------------------------------------------

LINE_RE = re.compile(r"^(?P<name>[^\d|]{2,50}?)\s*[:：]?\s*[\(（【]?\s*(?P<n>\d{1,3})\s*(人|名)\s*[\)）】]?(?:\s*[\(（][^)）]{1,20}[\)）])?$")


def text_counts(doc: dict, start: str | None = None, end: str | None = None) -> dict[str, int]:
    out: dict[str, int] = {}
    for part in _parts(doc, start, end):
        for p in re.split(r"\s{2,}|、", part):
            m = LINE_RE.match(p.strip())
            if m:
                _add(out, m.group("name"), int(m.group("n")))
    return out


# --- blocks: 会派名 → 議員… → 「計29人」 ------------------------------------------

def blocks_counts(doc: dict, start: str | None = None, end: str | None = None) -> dict[str, int]:
    out: dict[str, int] = {}
    current: str | None = None
    for part in _parts(doc, start, end):
        m = re.match(r"^(?:計|合計)\s*(\d{1,3})\s*(人|名)$", part)
        if m and current:
            _add(out, current, int(m.group(1)))
            current = None
        elif not is_person(part) and valid_kaiha_name(clean_name(part)) and current is None:
            current = part
    return out


# --- grouped: 会派名 → 議員名… （議員名を数える） ---------------------------------

def grouped_counts(doc: dict, start: str | None = None, end: str | None = None) -> dict[str, int]:
    out: dict[str, int] = {}
    current: str | None = None
    n = 0
    for part in _parts(doc, start, end):
        if is_person(part):
            if current:
                n += 1
            continue
        if current and n:
            _add(out, current, n)
        current, n = (part if valid_kaiha_name(clean_name(part)) else None), 0
    if current and n:
        _add(out, current, n)
    return out


# --- columns: 会派名の行と人数の行 --------------------------------------------------

def columns_counts(doc: dict, table: int | None = None, count_row: str = r"^(計|人数|合計)", start_col: int = 0) -> dict[str, int]:
    best: dict[str, int] = {}
    for t in _tables(doc, table, None):
        rows = t["rows"]
        cnt = next((r for r in rows if r and re.search(count_row, r[0].replace(" ", ""))
                    or (r and re.search(count_row, r[-1].replace(" ", "")))), None)
        if cnt is None:
            continue
        for names in rows:
            if names is cnt:
                continue
            out: dict[str, int] = {}
            for j in range(start_col, min(len(names), len(cnt))):
                n = _int(cnt[j])
                if n is not None:
                    _add(out, names[j], n)
            if len(out) >= 2 and sum(out.values()) > sum(best.values()):
                best = out
    # 表に計の行が無く、本文に「計 100 51 人 26 人 …」とある場合（北海道の PDF）
    if not best:
        line = next((l for l in doc["lines"] if re.match(r"^計\s+\d", l)), None)
        hdr = next((t["rows"][0] for t in doc["tables"] if t["rows"]), None)
        if line and hdr:
            nums = [int(x) for x in re.findall(r"(\d{1,3})\s*人", line)]
            names = [c for c in hdr[start_col:] if c]
            if len(nums) == len(names):
                for name, n in zip(names, nums):
                    _add(best, name, n)
    return best


# --- page_members: 1 ページ = 1 会派（会派名の後に議員名が並ぶ） ----------------

def page_members(doc: dict, start: str = "ここから本文です", end: str | None = None) -> dict[str, int]:
    parts = _parts(doc, start, end)
    name = next((p for p in parts if valid_kaiha_name(clean_name(p)) and not is_person(p)), None)
    if not name:
        return {}
    n = sum(1 for p in parts if is_person(p))
    out: dict[str, int] = {}
    _add(out, name, n)
    return out


# --- regex: 「氏名(会派名)(9期)」のように会派名が議員ごとに書かれている -----------

def regex_counts(doc: dict, pattern: str, start: str | None = None, end: str | None = None) -> dict[str, int]:
    rx = re.compile(pattern)
    counter: Counter[str] = Counter()
    for part in _parts(doc, start, end):
        for m in rx.finditer(part):
            name = clean_name(m.group(1))
            if valid_kaiha_name(name):
                counter[name] += 1
    return dict(counter)


# --- table_rows: 会派ごとに表が分かれていて、表の行数 = 人数 ------------------------

def table_rows(doc: dict, heading: str | None = None) -> dict[str, int]:
    out: dict[str, int] = {}
    for t in doc["tables"]:
        name = t["heading"]
        rows = t["rows"]
        if heading and heading not in name:
            continue
        n = sum(1 for r in rows if any(is_person(c) for c in r))
        if name and n:
            _add(out, name, n)
    return out


READERS = {
    "page_members": page_members,
    "regex": regex_counts,
    "table_rows": table_rows,
    "table": table_counts,
    "roster": roster_counts,
    "paren": paren_counts,
    "text": text_counts,
    "blocks": blocks_counts,
    "grouped": grouped_counts,
    "columns": columns_counts,
}
