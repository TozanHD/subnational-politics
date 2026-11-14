"""民主党政権期（2009〜2011年末）の所属党派別人員調を、比較用の JSON にする（一度だけ実行する）。

総務省「地方公共団体の議会の議員及び長の所属党派別人員調等」の過去分を読み、
src/data/history.json に書き出す。過去のデータは今後変わらないので定期更新はしない。

  python scripts/history/build_dpj_era.py [元データのディレクトリ]   # 省略時は data/raw/history/

- 平成21年12月31日現在（鳩山内閣）… PDF（000058817.pdf）。文字の位置から列を割り当てて読む
- 平成22年12月31日現在（菅内閣）  … xls（000115998.xls）
- 平成23年12月31日現在（野田内閣）… xls（000151834.xls）

読み取った表は、最新データと同じ検証（政党別の和＝合計、合計＋欠員＝定数 など）を通す。
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
import tempfile
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from update_data import (  # noqa: E402
    PREFECTURES, DataError, build_dataset, norm, parse_table, table_to_json, validate_table,
)

ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT = ROOT / "src" / "data" / "history.json"
PAGE = "https://www.soumu.go.jp/senkyo/senkyo_s/data/syozoku/ichiran.html"

SNAPSHOTS = [
    {"id": "2009", "asOf": "2009-12-31", "cabinet": "鳩山内閣", "label": "2009年末（鳩山内閣・政権交代直後）",
     "file": "000058817.pdf", "url": "https://www.soumu.go.jp/main_content/000058817.pdf", "page": PAGE},
    {"id": "2010", "asOf": "2010-12-31", "cabinet": "菅内閣", "label": "2010年末（菅内閣・統一地方選の前）",
     "file": "000115998.xls", "url": "https://www.soumu.go.jp/main_content/000115998.xls",
     "page": "https://www.soumu.go.jp/senkyo/senkyo_s/data/syozoku/h22.html"},
    {"id": "2011", "asOf": "2011-12-31", "cabinet": "野田内閣", "label": "2011年末（野田内閣・統一地方選の後）",
     "file": "000151834.xls", "url": "https://www.soumu.go.jp/main_content/000151834.xls",
     "page": "https://www.soumu.go.jp/senkyo/senkyo_s/data/syozoku/h23.html"},
]


# ---------------------------------------------------------------------------
# xls: 左右 2 段に分かれた表を 1 つにつなぎ直して xlsx にする
# ---------------------------------------------------------------------------

def xls_to_xlsx(src: Path, dst: Path) -> None:
    import xlrd

    book = xlrd.open_workbook(str(src))
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for s in book.sheets():
        rows = [[s.cell_value(r, c) for c in range(s.ncols)] for r in range(s.nrows)]
        ws = wb.create_sheet(s.name)
        hdr = next((i for i, r in enumerate(rows) if any(norm(v) == "団体名" for v in r)), None)
        if hdr is None:
            for r in rows:
                ws.append([v if v != "" else None for v in r])
            continue
        starts = [c for c, v in enumerate(rows[hdr]) if norm(v) == "団体名"]
        # 1 段目は「団体名」の列から、2 段目以降は「定数」の次の列から
        spans = [(starts[0], starts[1] if len(starts) > 1 else s.ncols)]
        for k, st in enumerate(starts[1:], start=1):
            spans.append((st + 2, starts[k + 1] if k + 1 < len(starts) else s.ncols))
        for r in rows:
            out: list = []
            for a, b in spans:
                out += r[a:b]
            ws.append([v if v != "" else None for v in out])
    wb.save(dst)


# ---------------------------------------------------------------------------
# PDF: 文字の位置から列を割り当てる
# ---------------------------------------------------------------------------

PDF_SECTIONS = {
    "governor": "（１）都道府県知事",
    "assembly": "（２）都道府県議会議員",
    "cityAssembly": "（４）市区議会議員",
    "townAssembly": "（６）町村議会議員",
}


def _lines(words):
    lines: list[list[dict]] = []
    for w in sorted(words, key=lambda w: (round(w["top"]), w["x0"])):
        if lines and abs(lines[-1][0]["top"] - w["top"]) < 3:
            lines[-1].append(w)
        else:
            lines.append([w])
    return [sorted(l, key=lambda w: w["x0"]) for l in lines]


def _num(t: str) -> int | None:
    t = t.replace(",", "")
    return int(t) if re.fullmatch(r"\d+", t) else None


def parse_pdf_page(page) -> dict[str, dict]:
    """1 ページ分の表を {団体名: {"fixed", "cols": {(政党, 男|女|計): 値}, "vacant"}} にする。"""
    lines = _lines(page.extract_words(keep_blank_chars=False, use_text_flow=False))
    hdr_i = next((i for i, l in enumerate(lines) if norm(l[0]["text"]) == "団体名"), None)
    if hdr_i is None:
        return {"_parties": []}
    hdr = lines[hdr_i]
    cols = [w for w in hdr if w["text"] in ("男", "女", "計")]
    fixed_w = next(w for w in hdr if w["text"] == "定数")
    # 政党名は見出し行の 1〜3 行上。各政党は「男 女 計」の 3 列にまたがる
    names = [w for l in lines[max(0, hdr_i - 3):hdr_i] for w in l
             if w["text"] not in ("区", "分") and not w["text"].startswith(("（", "("))]
    vac = next((w for w in names if w["text"] == "欠員"), None)
    names = [w for w in names if w["text"] != "欠員"]
    mid = lambda w: (w["x0"] + w["x1"]) / 2  # noqa: E731
    groups = []
    for k in range(0, len(cols) - 2, 3):
        cx = (cols[k]["x0"] + cols[k + 2]["x1"]) / 2
        name = min(names, key=lambda w: abs(mid(w) - cx))
        if abs(mid(name) - cx) > 20:
            raise DataError(f"政党名を特定できない列 (x={cx:.0f})")
        groups.append((norm(name["text"]), cols[k:k + 3]))
    # 列の中心を並べ、隣との中間を境界にする。数字はマスの右寄せなので右端で判定する
    centers = sorted(
        [(mid(fixed_w), "定数", 0)] + [(mid(w), g, i) for g, ws in groups for i, w in enumerate(ws)]
        + ([(mid(vac), "欠員", 0)] if vac is not None else []),
        key=lambda c: c[0],
    )
    bounds = [(centers[j][0] + centers[j + 1][0]) / 2 for j in range(len(centers) - 1)]

    def column(x: float):
        j = 0
        while j < len(bounds) and x > bounds[j]:
            j += 1
        return centers[j]

    out: dict[str, dict] = {}
    for l in lines[hdr_i + 1:]:
        label = norm("".join(w["text"] for w in l if _num(w["text"]) is None))
        if label not in PREFECTURES and label != "合計":
            continue
        row: dict = {"cols": {}}
        for w in l:
            v = _num(w["text"])
            if v is None:
                continue
            _, g, i = column(w["x1"] - 1)
            if g == "定数":
                row["fixed"] = v
            elif g == "欠員":
                row["vacant"] = v
            else:
                if (g, i) in row["cols"]:
                    raise DataError(f"同じ列に 2 つの値 {g} ({label})")
                row["cols"][(g, i)] = v
        out[label] = row
    out["_parties"] = [g for g, _ in groups]  # type: ignore[assignment]
    return out


def parse_pdf(path: Path) -> dict[str, dict]:
    import pdfplumber

    pdf = pdfplumber.open(str(path))
    tables: dict[str, dict] = {}
    for key, title in PDF_SECTIONS.items():
        pages = [p for p in pdf.pages if norm(title) in norm((p.extract_text() or "")[:80])]
        if not pages:
            raise DataError(f"PDF に「{title}」の表がありません")
        merged: dict[str, dict] = {}
        order: list[str] = []
        for p in pages:
            part = parse_pdf_page(p)
            for g in part.pop("_parties"):
                if g not in order:
                    order.append(g)
            for pref, row in part.items():
                m = merged.setdefault(pref, {"cols": {}})
                m["cols"].update(row["cols"])
                for k in ("fixed", "vacant"):
                    if k in row:
                        m[k] = row[k]
        table = {}
        for pref in PREFECTURES:
            row = merged.get(pref)
            if row is None:
                raise DataError(f"{key}: {pref} の行がありません")
            parties = {g: [row["cols"].get((g, i), 0) for i in range(3)] for g in order if g != "合計"}
            total = [row["cols"].get(("合計", i), 0) for i in range(3)]
            table[pref] = {"fixed": row.get("fixed", 0), "vacant": row.get("vacant"), "parties": parties, "total": total}
        if key == "governor":
            for r in table.values():
                r["vacant"] = r["vacant"] if r["vacant"] is not None else r["fixed"] - r["total"][2]
        validate_table(table, key)
        tables[key] = table_to_json(table)
    return tables


def dataset_from_pdf(path: Path, snap: dict) -> dict:
    tables = parse_pdf(path)
    order: list[str] = []
    for t in tables.values():
        for row in t.values():
            for p in row["parties"]:
                if p not in order:
                    order.append(p)
    prefs = []
    for i, pref in enumerate(PREFECTURES, start=1):
        e = {"code": i, "name": pref}
        for k in ("assembly", "cityAssembly", "townAssembly"):
            e[k] = tables[k][pref]
        g = tables["governor"][pref]
        party = next(iter(g["parties"]), None)
        e["governor"] = {"party": party, "female": bool(party and g["parties"][party][1] == 1)} if party else None
        prefs.append(e)
    return {"asOf": snap["asOf"], "parties": order, "prefectures": prefs}


# ---------------------------------------------------------------------------

# 年によって表記が違う政党名を、最新データの表記にそろえる
RENAME = {"共産党": "日本共産党"}


def slim(data: dict, snap: dict) -> dict:
    """表示に使う部分だけ残す（ファイルを小さくする）。人数は [男, 女, 計] の計だけ。"""
    def part(a):
        return {"fixed": a["fixed"], "vacant": a["vacant"],
                "parties": {RENAME.get(k, k): v[2] for k, v in a["parties"].items()}}

    return {
        "id": snap["id"], "asOf": snap["asOf"], "cabinet": snap["cabinet"], "label": snap["label"],
        "source": {"url": snap["url"], "pageUrl": snap["page"]},
        "parties": [RENAME.get(p, p) for p in data["parties"]],
        "prefectures": {
            p["name"]: {
                "assembly": part(p["assembly"]),
                "cityAssembly": part(p["cityAssembly"]) if p.get("cityAssembly") else None,
                "townAssembly": part(p["townAssembly"]) if p.get("townAssembly") else None,
                "governor": RENAME.get(p["governor"]["party"], p["governor"]["party"]) if p.get("governor") else None,
            }
            for p in data["prefectures"]
        },
    }


def main(argv: list[str]) -> int:
    src = Path(argv[1]) if len(argv) > 1 else ROOT / "data" / "raw" / "history"
    snaps = []
    with tempfile.TemporaryDirectory() as tmp:
        for snap in SNAPSHOTS:
            f = src / snap["file"]
            if f.suffix == ".pdf":
                data = dataset_from_pdf(f, snap)
            else:
                x = Path(tmp) / (f.stem + ".xlsx")
                xls_to_xlsx(f, x)
                data = build_dataset(x, dt.date.fromisoformat(snap["asOf"]), {})
            s = slim(data, snap)
            dpj = sum(p["assembly"]["parties"].get("民主党", 0) for p in s["prefectures"].values())
            print(f"{snap['asOf']}: 都道府県議会の民主党 {dpj} 人", file=sys.stderr)
            snaps.append(s)
    out = {
        "schemaVersion": 1,
        "note": "総務省「地方公共団体の議会の議員及び長の所属党派別人員調等」の過去分（民主党政権期）。",
        "default": "2009",
        "snapshots": snaps,
    }
    OUTPUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"書き出しました: {OUTPUT} ({OUTPUT.stat().st_size // 1024} KB)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except DataError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
