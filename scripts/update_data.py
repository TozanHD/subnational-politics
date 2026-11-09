#!/usr/bin/env python3
"""総務省「地方公共団体の議会の議員及び長の所属党派別人員調」を取得し、
サイト用の JSON (src/data/latest.json) を生成する。

設計方針（人手による保守を不要にするため）:
  * URL を決め打ちしない。総務省サイトを巡回して xlsx を自動で探す。
  * 政党の列を決め打ちしない。表の見出しから政党名を読み取る（新党が増えても追従）。
  * 合計・定数・欠員の整合性を検証し、少しでもおかしければ既存データを壊さず失敗する。
    （GitHub Actions が失敗するとリポジトリ所有者にメール通知が届く）
  * 既存データより古い年次のデータでは上書きしない。

使い方:
  python scripts/update_data.py               # 総務省サイトから自動取得
  python scripts/update_data.py --file X.xlsx --as-of 2024-12-31 [--source-url URL]
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import openpyxl

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "src" / "data" / "latest.json"
RAW_DIR = ROOT / "data" / "raw"

USER_AGENT = "subnational-politics-data-bot/1.0 (+https://github.com/TozanHD/subnational-politics)"
SOUMU_HOST = "www.soumu.go.jp"
SEED_URLS = [
    "https://www.soumu.go.jp/senkyo/senkyo_s/data/syozoku/index.html",
    "https://www.soumu.go.jp/senkyo/senkyo_s/data/syozoku/",
    "https://www.soumu.go.jp/senkyo/senkyo_s/data/index.html",
    "https://www.soumu.go.jp/senkyo/senkyo_s/data/",
    "https://www.soumu.go.jp/senkyo/senkyo_s/index.html",
]
MAX_PAGES = 60
MAX_CANDIDATES = 6

PREFECTURES = [
    "北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県",
    "茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県",
    "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県", "岐阜県",
    "静岡県", "愛知県", "三重県", "滋賀県", "京都府", "大阪府", "兵庫県",
    "奈良県", "和歌山県", "鳥取県", "島根県", "岡山県", "広島県", "山口県",
    "徳島県", "香川県", "愛媛県", "高知県", "福岡県", "佐賀県", "長崎県",
    "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県",
]

# シート種別: (キー, シート名/表題に含まれる語, 必須か)
SHEETS = [
    ("assembly", "都道府県議会", True),
    ("governor", "都道府県知事", False),
    ("cityAssembly", "市区議会", False),
    ("townAssembly", "町村議会", False),
]

TOTAL_LABEL = "合計"
VACANCY_LABEL = "欠員"


class DataError(Exception):
    """取得・解析・検証に失敗したことを表す。"""


# ---------------------------------------------------------------------------
# 文字列ユーティリティ
# ---------------------------------------------------------------------------

def norm(value: Any) -> str:
    """全角/半角・空白の揺れを吸収した文字列にする。"""
    if value is None:
        return ""
    s = unicodedata.normalize("NFKC", str(value))
    return re.sub(r"\s+", "", s)


def to_int(value: Any) -> int:
    if value is None or value == "" or value == "-" or value == "－":
        return 0
    if isinstance(value, bool):
        raise DataError(f"数値ではない値: {value!r}")
    if isinstance(value, (int, float)):
        if float(value) != int(value):
            raise DataError(f"整数ではない値: {value!r}")
        return int(value)
    s = norm(value).replace(",", "")
    if s in ("", "-", "―", "ー"):
        return 0
    if not re.fullmatch(r"-?\d+", s):
        raise DataError(f"数値ではない値: {value!r}")
    return int(s)


ERA_BASE = {"令和": 2018, "平成": 1988}


def parse_japanese_date(text: str) -> dt.date | None:
    """「令和6年12月31日現在」などから日付を取り出す（最も新しいもの）。"""
    found = parse_japanese_dates(text)
    return max(found) if found else None


def parse_japanese_dates(text: str) -> set[dt.date]:
    t = unicodedata.normalize("NFKC", text)
    found: list[dt.date] = []
    for era, year, month, day in re.findall(r"(令和|平成)\s*(元|\d{1,2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日\s*現在", t):
        y = ERA_BASE[era] + (1 if year == "元" else int(year))
        try:
            found.append(dt.date(y, int(month), int(day)))
        except ValueError:
            continue
    for year, month, day in re.findall(r"((?:19|20)\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日\s*現在", t):
        try:
            found.append(dt.date(int(year), int(month), int(day)))
        except ValueError:
            continue
    return set(found)


# ---------------------------------------------------------------------------
# xlsx 解析
# ---------------------------------------------------------------------------

def find_sheet(wb: openpyxl.Workbook, keyword: str):
    for ws in wb.worksheets:
        if keyword in norm(ws.title):
            return ws
    for ws in wb.worksheets:
        for row in ws.iter_rows(min_row=1, max_row=3, values_only=True):
            if any(keyword in norm(c) and "所属党派別" in norm(c) for c in row if c):
                return ws
    return None


def parse_table(ws) -> dict[str, dict[str, Any]]:
    """「団体名 / 定数 / 政党ごとの男・女・計 / 合計 / 欠員」形式の表を読む。

    戻り値: {団体名: {"fixed": 定数, "vacant": 欠員, "parties": {政党: [男, 女, 計]}, "total": [男, 女, 計]}}
    政党の並びは表の並び順を保つ。
    """
    rows = [list(r) for r in ws.iter_rows(values_only=True)]
    header_idx = next((i for i, r in enumerate(rows) if r and norm(r[0]) == "団体名"), None)
    if header_idx is None:
        raise DataError(f"シート「{ws.title}」に『団体名』の見出し行がありません")
    header = [norm(c) for c in rows[header_idx]]
    if len(header) < 2 or header[1] != "定数":
        raise DataError(f"シート「{ws.title}」の2列目が『定数』ではありません: {header[:3]}")

    # 政党名の行: 見出し行より上で、政党名らしき文字列が最も多い行
    name_row: list[str] | None = None
    best = 0
    for i in range(max(0, header_idx - 3), header_idx):
        cand = [norm(c) for c in rows[i]]
        score = sum(1 for c in cand[2:] if c)
        if score > best:
            best, name_row = score, cand
    if not name_row:
        raise DataError(f"シート「{ws.title}」の政党名の行が見つかりません")

    ncol = max(len(header), len(name_row))
    header += [""] * (ncol - len(header))
    name_row += [""] * (ncol - len(name_row))

    groups: list[tuple[str, int]] = []  # (政党名, 男の列)
    vacancy_col: int | None = None
    c = 2
    while c < ncol:
        if header[c] == "男" and c + 2 < ncol and header[c + 1] == "女" and header[c + 2] == "計":
            name = name_row[c]
            if not name:
                raise DataError(f"シート「{ws.title}」の {c + 1} 列目の政党名が空です")
            groups.append((name, c))
            c += 3
            continue
        if name_row[c] == VACANCY_LABEL:
            vacancy_col = c
        c += 1

    names = [g[0] for g in groups]
    if TOTAL_LABEL not in names:
        raise DataError(f"シート「{ws.title}」に『合計』列がありません")
    if len(set(names)) != len(names):
        raise DataError(f"シート「{ws.title}」の政党名が重複しています: {names}")
    if len(groups) < 4:
        raise DataError(f"シート「{ws.title}」の政党列が少なすぎます: {names}")

    result: dict[str, dict[str, Any]] = {}
    for r in rows[header_idx + 1:]:
        if not r or r[0] is None:
            continue
        label = norm(r[0])
        if not label:
            continue
        if label == TOTAL_LABEL:
            break
        r = r + [None] * (ncol - len(r))
        parties: dict[str, list[int]] = {}
        total: list[int] | None = None
        for name, col in groups:
            m, f, t = to_int(r[col]), to_int(r[col + 1]), to_int(r[col + 2])
            if min(m, f, t) < 0:
                raise DataError(f"{ws.title}/{label}/{name}: 負の値があります")
            # 性別非公表の議員がいると 男+女 < 計 になる（総務省の注記あり）
            if m + f > t:
                raise DataError(f"{ws.title}/{label}/{name}: 男({m})+女({f}) > 計({t})")
            if name == TOTAL_LABEL:
                total = [m, f, t]
            else:
                parties[name] = [m, f, t]
        assert total is not None
        result[label] = {
            "fixed": to_int(r[1]),
            "vacant": to_int(r[vacancy_col]) if vacancy_col is not None else None,
            "parties": parties,
            "total": total,
        }
    return result


def validate_table(table: dict[str, dict[str, Any]], kind: str) -> None:
    missing = [p for p in PREFECTURES if p not in table]
    extra = [p for p in table if p not in PREFECTURES]
    if missing or extra:
        raise DataError(f"{kind}: 都道府県の一覧が一致しません (不足: {missing}, 余分: {extra})")
    for pref, row in table.items():
        sums = [sum(v[i] for v in row["parties"].values()) for i in range(3)]
        if sums != row["total"]:
            raise DataError(f"{kind}/{pref}: 政党別の和 {sums} が合計 {row['total']} と一致しません")
        if row["vacant"] is not None and row["total"][2] + row["vacant"] != row["fixed"]:
            raise DataError(
                f"{kind}/{pref}: 合計({row['total'][2]}) + 欠員({row['vacant']}) != 定数({row['fixed']})"
            )
        if row["total"][2] > row["fixed"]:
            raise DataError(f"{kind}/{pref}: 現員が定数を超えています")
    if kind == "assembly":
        fixed = sum(r["fixed"] for r in table.values())
        # 都道府県議会の総定数は 2,600 人前後。桁違いなら表の取り違え。
        if not 1500 <= fixed <= 4000:
            raise DataError(f"都道府県議会の総定数が想定外です: {fixed}")
        for pref, r in table.items():
            if not 30 <= r["fixed"] <= 200:
                raise DataError(f"{pref} の都道府県議会定数が想定外です: {r['fixed']}")
    if kind == "governor":
        for pref, r in table.items():
            if r["fixed"] != 1:
                raise DataError(f"{pref} の知事定数が 1 ではありません")


def detect_date_in_workbook(wb: openpyxl.Workbook) -> dt.date | None:
    """ブック内の「○年12月31日現在」や総括表の日付セルから基準日を推定する。"""
    best: dt.date | None = None
    for ws in wb.worksheets:
        for row in ws.iter_rows(values_only=True):
            for c in row:
                d: dt.date | None = None
                if isinstance(c, str) and "現在" in c:
                    d = parse_japanese_date(c)
                elif isinstance(c, dt.datetime):
                    d = c.date()
                elif isinstance(c, (int, float)) and "総括" in ws.title and 36000 <= c <= 80000 and float(c).is_integer():
                    # 総括表の日付列は Excel のシリアル値 (例: 45657 = 2024-12-31)
                    cand = dt.date(1899, 12, 30) + dt.timedelta(days=int(c))
                    if (cand.month, cand.day) == (12, 31):
                        d = cand
                if d and 2000 <= d.year <= 2100 and (best is None or d > best):
                    best = d
    return best


def table_to_json(table: dict[str, dict[str, Any]]) -> dict[str, Any]:
    out = {}
    for pref in PREFECTURES:
        row = table[pref]
        out[pref] = {
            "fixed": row["fixed"],
            "vacant": row["vacant"] if row["vacant"] is not None else row["fixed"] - row["total"][2],
            "total": row["total"],
            "parties": {k: v for k, v in row["parties"].items() if v[2] > 0},
        }
    return out


def build_dataset(
    xlsx_path: Path,
    as_of: dt.date | None,
    source: dict[str, Any],
    fallback_as_of: dt.date | None = None,
) -> dict[str, Any]:
    """as_of を指定すればそれを優先。無ければブック内から推定し、それも無ければ fallback_as_of。"""
    try:
        wb = openpyxl.load_workbook(xlsx_path, data_only=True, read_only=False)
    except Exception as e:  # noqa: BLE001 - 破損ファイル等
        raise DataError(f"xlsx を開けません: {e}") from e

    tables: dict[str, Any] = {}
    party_order: list[str] = []
    for key, keyword, required in SHEETS:
        ws = find_sheet(wb, keyword)
        if ws is None:
            if required:
                raise DataError(f"シート「{keyword}」が見つかりません")
            print(f"  [warn] シート「{keyword}」が無いため省略します", file=sys.stderr)
            continue
        try:
            table = parse_table(ws)
            validate_table(table, key)
        except DataError:
            if required:
                raise
            print(f"  [warn] シート「{keyword}」の解析に失敗したため省略します", file=sys.stderr)
            continue
        tables[key] = table_to_json(table)
        for p in next(iter(table.values()))["parties"].keys():
            if p not in party_order:
                party_order.append(p)

    if as_of is None:
        as_of = detect_date_in_workbook(wb) or fallback_as_of
    if as_of is None:
        raise DataError("データの基準日（○年12月31日現在）を特定できません")

    prefectures = []
    for i, pref in enumerate(PREFECTURES, start=1):
        entry: dict[str, Any] = {"code": i, "name": pref}
        for key in ("assembly", "cityAssembly", "townAssembly"):
            if key in tables:
                entry[key] = tables[key][pref]
        if "governor" in tables:
            g = tables["governor"][pref]
            party = next(iter(g["parties"]), None)
            entry["governor"] = {
                "party": party,
                "female": bool(party and g["parties"][party][1] == 1),
            } if party else None
        prefectures.append(entry)

    return {
        "schemaVersion": 1,
        "asOf": as_of.isoformat(),
        "source": source,
        "parties": party_order,
        "prefectures": prefectures,
    }


# ---------------------------------------------------------------------------
# 総務省サイトの巡回
# ---------------------------------------------------------------------------

class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []
        self.text: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            self.links.append((self._href, "".join(self._text)))
            self._href = None

    def handle_data(self, data):
        self.text.append(data)
        if self._href is not None:
            self._text.append(data)


def http_get(url: str, retries: int = 3) -> bytes:
    last: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=60) as res:
                return res.read()
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 ** (attempt + 1))
    raise DataError(f"取得失敗 {url}: {last}")


def decode_html(body: bytes) -> str:
    m = re.search(rb"charset=[\"']?([A-Za-z0-9_\-]+)", body[:2000])
    encodings = [m.group(1).decode() if m else "utf-8", "utf-8", "cp932", "euc_jp"]
    for enc in encodings:
        try:
            return body.decode(enc)
        except (LookupError, UnicodeDecodeError):
            continue
    return body.decode("utf-8", errors="replace")


def is_relevant_page(url: str, anchor: str) -> bool:
    p = urllib.parse.urlparse(url)
    if p.netloc != SOUMU_HOST or not p.path.startswith("/senkyo/"):
        return False
    if not re.search(r"\.html?$|/$", p.path):
        return False
    a = norm(anchor)
    return "syozoku" in p.path or "所属党派" in a or "選挙関連資料" in a or p.path.rstrip("/").endswith("/data")


def content_id(url: str) -> int:
    m = re.search(r"(\d{6,})\.xlsx?$", url)
    return int(m.group(1)) if m else 0


def discover_candidates() -> list[dict[str, Any]]:
    """総務省サイトを巡回し、所属党派別人員調の xlsx 候補を新しい順に返す。"""
    queue: list[str] = list(SEED_URLS)
    seen: set[str] = set()
    candidates: dict[str, dict[str, Any]] = {}
    while queue and len(seen) < MAX_PAGES:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        try:
            body = http_get(url, retries=2)
        except DataError as e:
            print(f"  [skip] {e}", file=sys.stderr)
            continue
        parser = LinkParser()
        parser.feed(decode_html(body))
        page_text = html.unescape("".join(parser.text))
        page_is_syozoku = "所属党派別" in norm(page_text)
        # 1つのページに1つの基準日しか書かれていない場合だけ、その日付をページの基準日とみなす
        page_dates = parse_japanese_dates(page_text) if page_is_syozoku else set()
        page_date = next(iter(page_dates)) if len(page_dates) == 1 else None
        for href, anchor in parser.links:
            abs_url = urllib.parse.urljoin(url, href.strip()).split("#")[0]
            if re.search(r"\.xlsx$", abs_url, re.I) and page_is_syozoku:
                a = norm(anchor)
                d = parse_japanese_date(a) or page_date
                prev = candidates.get(abs_url)
                if prev is None or (prev["date"] is None and d is not None):
                    candidates[abs_url] = {
                        "url": abs_url,
                        "pageUrl": url,
                        "anchor": a,
                        "date": d.isoformat() if d else None,
                    }
            elif is_relevant_page(abs_url, anchor) and abs_url not in seen:
                queue.append(abs_url)
        time.sleep(1)
    print(f"  巡回ページ数: {len(seen)}, xlsx 候補: {len(candidates)}", file=sys.stderr)
    # 総務省の main_content の番号は公開順に増えるので、番号の大きい順 = 新しい順
    return sorted(candidates.values(), key=lambda c: (content_id(c["url"]), c["date"] or ""), reverse=True)


# ---------------------------------------------------------------------------
# メイン
# ---------------------------------------------------------------------------

def load_existing() -> dict[str, Any] | None:
    if OUTPUT.exists():
        return json.loads(OUTPUT.read_text(encoding="utf-8"))
    return None


def comparable(d: dict[str, Any] | None) -> Any:
    if d is None:
        return None
    d = dict(d)
    d.pop("updatedAt", None)
    return d


def write_if_changed(data: dict[str, Any], force: bool = False) -> bool:
    existing = load_existing()
    if existing and not force and existing.get("asOf", "") > data["asOf"]:
        print(f"既存データ ({existing['asOf']}) の方が新しいため更新しません", file=sys.stderr)
        return False
    if comparable(existing) == comparable(data):
        print("データに変更はありません", file=sys.stderr)
        return False
    data = dict(data)
    data["updatedAt"] = dt.datetime.now(dt.timezone.utc).date().isoformat()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"更新しました: {OUTPUT} (基準日 {data['asOf']})", file=sys.stderr)
    return True


def run_auto() -> int:
    candidates = discover_candidates()
    if not candidates:
        raise DataError("総務省サイトで所属党派別人員調の xlsx を見つけられませんでした（サイト構成が変わった可能性）")
    existing = load_existing()
    errors = []
    for cand in candidates[:MAX_CANDIDATES]:
        print(f"  試行: {cand['url']} ({cand['date']})", file=sys.stderr)
        if existing and cand["date"] and cand["date"] < existing.get("asOf", ""):
            print("  既存データより古いので終了", file=sys.stderr)
            break
        tmp = RAW_DIR / "_download.xlsx"
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        tmp.write_bytes(http_get(cand["url"]))
        try:
            hint = dt.date.fromisoformat(cand["date"]) if cand["date"] else None
            data = build_dataset(
                tmp, None, {"xlsxUrl": cand["url"], "pageUrl": cand["pageUrl"]}, fallback_as_of=hint
            )
        except DataError as e:
            errors.append(f"{cand['url']}: {e}")
            print(f"  [skip] {e}", file=sys.stderr)
            tmp.unlink(missing_ok=True)
            continue
        if write_if_changed(data):
            name = Path(urllib.parse.urlparse(cand["url"]).path).name
            final = RAW_DIR / f"{data['asOf']}_{name}"
            tmp.replace(final)
        else:
            tmp.unlink(missing_ok=True)
        return 0
    if existing and not errors:
        return 0
    raise DataError("有効な xlsx を解析できませんでした:\n  " + "\n  ".join(errors))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--file", type=Path, help="ローカルの xlsx から生成する")
    ap.add_argument("--as-of", type=dt.date.fromisoformat, help="基準日 (YYYY-MM-DD)")
    ap.add_argument("--source-url", help="--file の取得元 URL")
    ap.add_argument("--page-url", help="--file の掲載ページ URL")
    ap.add_argument("--force", action="store_true", help="既存データより古くても上書きする")
    args = ap.parse_args(argv)
    try:
        if args.file:
            data = build_dataset(args.file, args.as_of, {"xlsxUrl": args.source_url, "pageUrl": args.page_url})
            write_if_changed(data, force=args.force)
            return 0
        return run_auto()
    except DataError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
