"""HTML を「表（セル文字列の2次元配列）」と「本文の行」に正規化する。

読み取り設定はこの正規化結果に対して書くので、サイトの装飾（CSS やレイアウト用の div）が
変わっても影響を受けにくい。
"""
from __future__ import annotations

import re
import unicodedata
from html.parser import HTMLParser

SKIP_TAGS = {"script", "style", "noscript", "svg", "head"}
BLOCK_TAGS = {
    "p", "div", "li", "br", "h1", "h2", "h3", "h4", "h5", "h6", "dt", "dd", "section",
    "article", "tr", "caption", "header", "footer", "ul", "ol", "dl", "blockquote",
}


def clean(s: str) -> str:
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("　", " ")
    return re.sub(r"\s+", " ", s).strip()


class _Parser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.skip = 0
        self.lines: list[str] = []
        self.buf: list[str] = []
        self.tables: list[dict] = []
        self.stack: list[dict] = []  # 入れ子の表
        self.cell: list[str] | None = None
        self.cell_span = 1
        self.links: list[tuple[str, str]] = []
        self.href: str | None = None
        self.atext: list[str] = []
        self.last_heading = ""
        self.in_heading = False
        self.hbuf: list[str] = []

    def _flush(self):
        t = clean("".join(self.buf))
        if t:
            self.lines.append(t)
        self.buf = []

    def handle_starttag(self, tag, attrs):
        if tag in SKIP_TAGS:
            self.skip += 1
            return
        if self.skip:
            return
        a = dict(attrs)
        if tag == "a":
            self.href = a.get("href")
            self.atext = []
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.in_heading = True
            self.hbuf = []
        if tag == "table":
            self.stack.append({"rows": [], "row": None, "caption": "", "heading": self.last_heading})
        elif tag == "tr" and self.stack:
            self.stack[-1]["row"] = []
        elif tag in ("td", "th") and self.stack:
            if self.stack[-1]["row"] is None:
                self.stack[-1]["row"] = []
            self.cell = []
            try:
                self.cell_span = max(1, min(20, int(a.get("colspan") or 1)))
            except ValueError:
                self.cell_span = 1
        if tag in BLOCK_TAGS and not self.stack:
            self._flush()

    def handle_endtag(self, tag):
        if tag in SKIP_TAGS:
            self.skip = max(0, self.skip - 1)
            return
        if self.skip:
            return
        if tag == "a" and self.href is not None:
            self.links.append((self.href, clean("".join(self.atext))))
            self.href = None
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6") and self.in_heading:
            self.in_heading = False
            h = clean("".join(self.hbuf))
            if h:
                self.last_heading = h
        if tag in ("td", "th") and self.stack and self.cell is not None:
            text = clean("".join(self.cell))
            row = self.stack[-1]["row"]
            if row is not None:
                row.append(text)
                row.extend([""] * (self.cell_span - 1))
            self.cell = None
        elif tag == "tr" and self.stack:
            t = self.stack[-1]
            if t["row"] is not None and any(t["row"]):
                t["rows"].append(t["row"])
            t["row"] = None
        elif tag == "table" and self.stack:
            t = self.stack.pop()
            if t["rows"]:
                self.tables.append({"heading": t["heading"], "rows": t["rows"]})
                # 表の中身は本文にも残す（表以外の読み取りにも使えるように）
                for r in t["rows"]:
                    self.lines.append(" | ".join(c for c in r if c))
        if tag in BLOCK_TAGS and not self.stack:
            self._flush()

    def handle_data(self, data):
        if self.skip:
            return
        if self.cell is not None:
            self.cell.append(data)
        elif not self.stack:
            self.buf.append(data)
        if self.href is not None:
            self.atext.append(data)
        if self.in_heading:
            self.hbuf.append(data)


def extract(html: str) -> dict:
    p = _Parser()
    p.feed(html)
    p.close()
    p._flush()
    return {"lines": p.lines, "tables": p.tables, "links": p.links}


def decode(body: bytes, content_type: str = "") -> str:
    m = re.search(r"charset=([\w\-]+)", content_type) or re.search(rb"charset=[\"']?([A-Za-z0-9_\-]+)", body[:3000])
    enc = m.group(1) if m else None
    if isinstance(enc, bytes):
        enc = enc.decode()
    for e in [enc, "utf-8", "cp932", "euc_jp"]:
        if not e:
            continue
        try:
            return body.decode(e)
        except (LookupError, UnicodeDecodeError):
            continue
    return body.decode("utf-8", errors="replace")


def extract_pdf(body: bytes) -> dict:
    """PDF から本文の行と表を取り出す（HTML と同じ形にする）。"""
    import io

    import pdfplumber  # 遅延 import（HTML だけなら不要）

    lines: list[str] = []
    tables: list[dict] = []
    with pdfplumber.open(io.BytesIO(body)) as pdf:
        for page in pdf.pages[:30]:
            text = page.extract_text() or ""
            lines += [clean(l) for l in text.splitlines() if clean(l)]
            for t in page.extract_tables() or []:
                rows = [[clean(c or "") for c in r] for r in t]
                rows = [r for r in rows if any(r)]
                if rows:
                    tables.append({"heading": "", "rows": rows})
    return {"lines": lines, "tables": tables, "links": []}
