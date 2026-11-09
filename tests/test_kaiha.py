"""会派の読み取り方式のテスト。実際の県議会サイトから取得した文書（正規化済み）を使う。

実行: python -m unittest discover -s tests
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "kaiha"))

import readers as r  # noqa: E402
import update_kaiha as u  # noqa: E402
from extract import extract  # noqa: E402

DOCS = json.loads((ROOT / "tests" / "fixtures" / "kaiha_docs.json").read_text(encoding="utf-8"))


class Readers(unittest.TestCase):
    def check(self, pref, reader, fixed, expected, **args):
        counts = r.READERS[reader](DOCS[pref], **args)
        self.assertIsNone(u.validate(counts, fixed), counts)
        for name, n in expected.items():
            self.assertEqual(counts.get(name), n, counts)
        return counts

    def test_table_tokyo(self):
        self.check("東京都", "table", 127, {"都民ファーストの会 東京都議団": 31, "都議会公明党": 19})

    def test_paren_nagasaki(self):
        c = self.check("長崎県", "paren", 46, {"自由民主党": 30, "改革21": 9})
        self.assertEqual(sum(c.values()), 46)

    def test_paren_with_url_nagano(self):
        self.check("長野県", "paren", 57, {"自由民主党県議団": 24, "改革信州": 13, "無所属": 2})

    def test_paren_lone_count_kagoshima_subpage(self):
        self.assertEqual(r.paren_counts(DOCS["鹿児島県"]), {"自由民主党鹿児島県議会議員団": 34})

    def test_grouped_ishikawa(self):
        self.check("石川県", "grouped", 41, {"自由民主党石川県議会議員協議会": 29, "未来石川議員会": 6},
                   start="会派別名簿", end="お問い合わせ")

    def test_grouped_iwate(self):
        self.check("岩手県", "grouped", 48, {"自由民主党": 17, "希望いわて": 14},
                   start="会派別名簿", end="名前の表記")

    def test_roster_okayama_with_aliases(self):
        c = r.roster_counts(DOCS["岡山県"])
        c = u.apply_aliases(c, {"自民": "自由民主党岡山県議団"})
        self.assertEqual(c["自由民主党岡山県議団"], 33)

    def test_roster_short_rows_gifu(self):
        self.check("岐阜県", "roster", 46, {"県政自民クラブ": 34})

    def test_regex_saga(self):
        c = self.check("佐賀県", "regex", 37, {"自由民主党": 17, "自由民主党ネクストさが": 11},
                       pattern=r"[\(（]([^()（）]+?)[\)）]\s*[\(（]\d+期[\)）]")
        self.assertEqual(sum(c.values()), 37)

    def test_table_rows_tottori(self):
        c = self.check("鳥取県", "table_rows", 35, {"鳥取県議会自由民主党": 19})
        self.assertEqual(sum(c.values()), 35)

    def test_columns_hokkaido_pdf(self):
        self.check("北海道", "columns", 100, {"自民党・道民会議": 51, "民主・道民連合": 26}, start_col=2)

    def test_table_spaced_pdf_okinawa(self):
        # PDF の「沖 縄 自 民 党」のような文字間の空白を詰める
        self.check("沖縄県", "table", 48, {"沖縄自民党・無所属の会": 23})


class Validation(unittest.TestCase):
    def test_rejects_districts(self):
        """選挙区別の人数表を会派と誤認しない（香川県で実際に起きた誤読）。"""
        doc = {"lines": [], "tables": [{"heading": "", "rows": [["選挙区", "人数"], ["高松市選挙区", "15"],
                                                               ["丸亀市選挙区", "4"], ["坂出市選挙区", "3"]]}]}
        self.assertEqual(r.table_counts(doc), {})

    def test_rejects_over_fixed(self):
        self.assertIsNotNone(u.validate({"自民党": 40, "公明党": 5}, 41))

    def test_rejects_too_few(self):
        self.assertIsNotNone(u.validate({"自民党": 10, "公明党": 5}, 41))

    def test_accepts_normal(self):
        self.assertIsNone(u.validate({"自民党": 30, "県民クラブ": 8, "公明党": 2}, 41))


class CleanName(unittest.TestCase):
    def test_cases(self):
        self.assertEqual(r.clean_name("大阪維新の会大阪府議会議員団(外部サイトへリンク)"), "大阪維新の会大阪府議会議員団")
        self.assertEqual(r.clean_name("〇 自由民主党島根県議会議員連盟"), "自由民主党島根県議会議員連盟")
        self.assertEqual(r.clean_name("​自由民主党"), "自由民主党")
        self.assertEqual(r.clean_name("自 由 民 主 党"), "自由民主党")
        self.assertEqual(r.clean_name("埼玉県議会自由民主党議員団(自民)"), "埼玉県議会自由民主党議員団")
        self.assertEqual(r.clean_name("無所属(グリーンな東京)"), "無所属(グリーンな東京)")
        self.assertEqual(r.clean_name("無所属県民会議(県民)"), "無所属県民会議")


class Extract(unittest.TestCase):
    def test_html_table_and_lines(self):
        d = extract("<h2>会派別</h2><table><tr><th>会派名</th><th>人数</th></tr>"
                    "<tr><td>自民党</td><td>29</td></tr></table><script>x</script>")
        self.assertEqual(d["tables"][0]["heading"], "会派別")
        self.assertEqual(r.table_counts(d), {"自民党": 29})


class Sites(unittest.TestCase):
    def test_all_prefectures_configured(self):
        sites = json.loads((ROOT / "scripts" / "kaiha" / "sites.json").read_text(encoding="utf-8"))
        from crawl import PREFS
        for pref, _ in PREFS:
            self.assertIn(pref, sites)
            for src in sites[pref]["sources"]:
                self.assertIn(src["reader"], r.READERS, pref)
                self.assertTrue(src["url"].startswith("https://"), pref)


if __name__ == "__main__":
    unittest.main()
