"""scripts/update_data.py のテスト（標準ライブラリの unittest のみ使用）。

実行: python -m unittest discover -s tests
"""
import copy
import datetime as dt
import sys
import tempfile
import unittest
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import update_data as u  # noqa: E402

FULL = ROOT / "tests" / "fixtures" / "soumu_full_2024-12-31.xlsx"
ASSEMBLY_ONLY = ROOT / "data" / "raw" / "2024-12-31_001006911.xlsx"


class ParseDates(unittest.TestCase):
    def test_reiwa(self):
        self.assertEqual(u.parse_japanese_date("（令和６年１２月３１日現在）"), dt.date(2024, 12, 31))

    def test_gannen_and_latest(self):
        text = "令和元年12月31日現在 / 平成30年12月31日現在"
        self.assertEqual(u.parse_japanese_date(text), dt.date(2019, 12, 31))

    def test_none(self):
        self.assertIsNone(u.parse_japanese_date("所属党派別人員調"))


class ParseWorkbook(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = u.build_dataset(FULL, None, {"xlsxUrl": None, "pageUrl": None})

    def test_date_detected_from_summary_sheet(self):
        self.assertEqual(self.data["asOf"], "2024-12-31")

    def test_all_prefectures(self):
        self.assertEqual([p["name"] for p in self.data["prefectures"]], u.PREFECTURES)

    def test_parties_read_from_header(self):
        self.assertEqual(self.data["parties"][0], "自由民主党")
        self.assertIn("参政党", self.data["parties"])
        self.assertIn("無所属", self.data["parties"])
        self.assertNotIn("合計", self.data["parties"])
        self.assertNotIn("欠員", self.data["parties"])

    def test_known_values(self):
        hokkaido = self.data["prefectures"][0]["assembly"]
        self.assertEqual(hokkaido["fixed"], 100)
        self.assertEqual(hokkaido["vacant"], 1)
        self.assertEqual(hokkaido["parties"]["自由民主党"], [44, 4, 48])
        self.assertEqual(sum(v[2] for v in hokkaido["parties"].values()), hokkaido["total"][2])

    def test_national_total(self):
        total = sum(p["assembly"]["total"][2] for p in self.data["prefectures"])
        self.assertEqual(total, 2614)

    def test_governor(self):
        tokyo = self.data["prefectures"][12]
        self.assertEqual(tokyo["governor"], {"party": "無所属", "female": True})

    def test_optional_sheets_present(self):
        p = self.data["prefectures"][0]
        self.assertIn("cityAssembly", p)
        self.assertIn("townAssembly", p)

    def test_assembly_only_workbook(self):
        d = u.build_dataset(ASSEMBLY_ONLY, dt.date(2024, 12, 31), {})
        self.assertNotIn("governor", d["prefectures"][0])
        self.assertEqual(d["prefectures"][0]["assembly"], self.data["prefectures"][0]["assembly"])

    def test_missing_date_is_error(self):
        with self.assertRaises(u.DataError):
            u.build_dataset(ASSEMBLY_ONLY, None, {})

    def test_fallback_date(self):
        d = u.build_dataset(ASSEMBLY_ONLY, None, {}, fallback_as_of=dt.date(2024, 12, 31))
        self.assertEqual(d["asOf"], "2024-12-31")


class Validation(unittest.TestCase):
    def _mutated(self, fn):
        wb = openpyxl.load_workbook(ASSEMBLY_ONLY)
        fn(wb["都道府県議会"])
        tmp = Path(tempfile.mkdtemp()) / "x.xlsx"
        wb.save(tmp)
        return tmp

    def test_broken_sum_rejected(self):
        # 北海道の自民 計 を書き換えると合計と一致しなくなる
        path = self._mutated(lambda ws: ws.cell(row=4, column=5, value=49))
        with self.assertRaises(u.DataError):
            u.build_dataset(path, dt.date(2024, 12, 31), {})

    def test_missing_prefecture_rejected(self):
        path = self._mutated(lambda ws: ws.cell(row=4, column=1, value="蝦夷"))
        with self.assertRaises(u.DataError):
            u.build_dataset(path, dt.date(2024, 12, 31), {})

    def test_new_party_column_is_followed(self):
        """新しい政党の列が追加されても自動で読み取れること。"""
        src = openpyxl.load_workbook(ASSEMBLY_ONLY, data_only=True)["都道府県議会"]
        rows = [list(r) for r in src.iter_rows(values_only=True)]
        mudan = rows[1].index("無所属")  # 無所属の「男」列 (0 始まり)
        for i, r in enumerate(rows):
            if i == 1:
                ins = ["新しい党", None, None]
            elif i == 2:
                ins = ["男", "女", "計"]
            elif 3 <= i <= 49:
                ins = [0, 0, 0]
            else:
                ins = [None, None, None]
            r[2:2] = ins
        # 北海道: 無所属の男性 1 人を新党へ移す
        rows[3][2], rows[3][4] = 1, 1
        rows[3][mudan + 3] -= 1
        rows[3][mudan + 5] -= 1
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "都道府県議会"
        for r in rows:
            ws.append(r)
        path = Path(tempfile.mkdtemp()) / "new_party.xlsx"
        wb.save(path)
        d = u.build_dataset(path, dt.date(2024, 12, 31), {})
        self.assertEqual(d["parties"][0], "新しい党")
        self.assertEqual(d["prefectures"][0]["assembly"]["parties"]["新しい党"], [1, 0, 1])
        self.assertEqual(d["prefectures"][0]["assembly"]["total"][2], 99)


class WriteIfChanged(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()) / "latest.json"
        self.orig = u.OUTPUT
        u.OUTPUT = self.tmp
        self.data = u.build_dataset(ASSEMBLY_ONLY, dt.date(2024, 12, 31), {})

    def tearDown(self):
        u.OUTPUT = self.orig

    def test_no_change_no_write(self):
        self.assertTrue(u.write_if_changed(self.data))
        self.assertFalse(u.write_if_changed(self.data))

    def test_older_data_not_written(self):
        self.assertTrue(u.write_if_changed(self.data))
        older = copy.deepcopy(self.data)
        older["asOf"] = "2023-12-31"
        older["prefectures"][0]["assembly"]["fixed"] = 1
        self.assertFalse(u.write_if_changed(older))


class Discovery(unittest.TestCase):
    def test_content_id(self):
        self.assertEqual(u.content_id("https://www.soumu.go.jp/main_content/001006911.xlsx"), 1006911)
        self.assertEqual(u.content_id("https://example.com/a.pdf"), 0)

    def test_relevant_page(self):
        self.assertTrue(u.is_relevant_page("https://www.soumu.go.jp/senkyo/senkyo_s/data/syozoku/r06.html", ""))
        self.assertTrue(u.is_relevant_page("https://www.soumu.go.jp/senkyo/senkyo_s/data/x.html", "所属党派別人員調等"))
        self.assertFalse(u.is_relevant_page("https://example.com/senkyo/syozoku.html", ""))
        self.assertFalse(u.is_relevant_page("https://www.soumu.go.jp/main_content/000.pdf", "所属党派"))


if __name__ == "__main__":
    unittest.main()


class CrawlWithMock(unittest.TestCase):
    """総務省サイトを模した HTML で巡回ロジックを確認する。"""

    PAGES = {
        "https://www.soumu.go.jp/senkyo/senkyo_s/data/syozoku/index.html": """
            <html><head><meta charset="utf-8"></head><body>
            <h1>地方公共団体の議会の議員及び長の所属党派別人員調等</h1>
            <a href="r06.html">令和6年12月31日現在</a>
            <a href="r05.html">令和5年12月31日現在</a>
            <a href="https://example.com/x.html">外部</a>
            </body></html>""",
        "https://www.soumu.go.jp/senkyo/senkyo_s/data/syozoku/r06.html": """
            <html><body><p>所属党派別人員調（令和６年１２月３１日現在）</p>
            <a href="/main_content/001006911.xlsx">都道府県別（Excel）</a>
            <a href="/main_content/001006912.pdf">PDF</a></body></html>""",
        "https://www.soumu.go.jp/senkyo/senkyo_s/data/syozoku/r05.html": """
            <html><body><p>所属党派別人員調（令和５年１２月３１日現在）</p>
            <a href="/main_content/000940000.xlsx">都道府県別（Excel）</a></body></html>""",
    }

    def setUp(self):
        self.orig_get, self.orig_sleep = u.http_get, u.time.sleep
        u.time.sleep = lambda s: None

        def fake_get(url, retries=3):
            if url in self.PAGES:
                return self.PAGES[url].encode("utf-8")
            if url == "https://www.soumu.go.jp/main_content/001006911.xlsx":
                return FULL.read_bytes()
            raise u.DataError(f"404 {url}")

        u.http_get = fake_get

    def tearDown(self):
        u.http_get, u.time.sleep = self.orig_get, self.orig_sleep

    def test_discover_orders_newest_first(self):
        cands = u.discover_candidates()
        self.assertEqual([c["url"] for c in cands], [
            "https://www.soumu.go.jp/main_content/001006911.xlsx",
            "https://www.soumu.go.jp/main_content/000940000.xlsx",
        ])
        self.assertEqual(cands[0]["date"], "2024-12-31")
        self.assertEqual(cands[1]["date"], "2023-12-31")

    def test_run_auto_writes_data(self):
        tmpdir = Path(tempfile.mkdtemp())
        orig_out, orig_raw = u.OUTPUT, u.RAW_DIR
        u.OUTPUT, u.RAW_DIR = tmpdir / "latest.json", tmpdir / "raw"
        try:
            self.assertEqual(u.run_auto(), 0)
            self.assertTrue(u.OUTPUT.exists())
            self.assertTrue((tmpdir / "raw" / "2024-12-31_001006911.xlsx").exists())
            # 2 回目は変更なし
            self.assertEqual(u.run_auto(), 0)
        finally:
            u.OUTPUT, u.RAW_DIR = orig_out, orig_raw
