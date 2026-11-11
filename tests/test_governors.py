"""知事情報の読み取り（scripts/governors/update_governors.py）のテスト。ウィキペディアの実際の記事の一部を使う。"""
import datetime as dt
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "governors"))

import update_governors as g  # noqa: E402

FX = json.loads((ROOT / "tests" / "fixtures" / "governors.json").read_text(encoding="utf-8"))


class ParseList(unittest.TestCase):
    def setUp(self):
        self.rows = g.parse_list(FX["list"])

    def test_rows(self):
        self.assertEqual(set(self.rows), {"北海道", "秋田県", "東京都", "沖縄県"})

    def test_hokkaido(self):
        r = self.rows["北海道"]
        self.assertEqual(r["name"], "鈴木直道")
        self.assertEqual(r["article"], "鈴木直道")
        self.assertEqual(r["since"], "2019-04-23")
        self.assertEqual(r["term"], 2)
        self.assertEqual(r["sinceElection"], "2019年北海道知事選挙")
        self.assertIn("夕張市長", r["career"])

    def test_disambiguated_article(self):
        r = self.rows["秋田県"]
        self.assertEqual(r["name"], "鈴木健太")
        self.assertEqual(r["article"], "鈴木健太 (政治家)")

    def test_wrapped_name(self):
        self.assertEqual(self.rows["沖縄県"]["name"], "古謝玄太")


class PartyHistory(unittest.TestCase):
    def test_factions(self):
        self.assertEqual(g.party_history(FX["yamamoto"]), "自由民主党（町村派 → 無派閥） → 無所属")

    def test_long_history(self):
        h = g.party_history(FX["koike"])
        self.assertTrue(h.startswith("日本新党 → 新進党"), h)
        self.assertIn("都民ファーストの会", h)


class Elections(unittest.TestCase):
    def test_date_from_start_date(self):
        self.assertEqual(g.election_date(FX["fukushima_election"], "2026年福島県知事選挙"), dt.date(2026, 10, 25))

    def test_template_winner(self):
        self.assertEqual(g.endorsements(FX["gunma_election"], "山本一太", "山本一太"), "自由民主党・公明党 推薦")

    def test_template_other_winner(self):
        self.assertIsNone(g.endorsements(FX["gunma_election"], "別の人", None))

    def test_template_empty_support(self):
        self.assertEqual(g.endorsements(FX["fukushima_election"], "内堀雅雄", "内堀雅雄"), "")

    def test_candidate_table_note(self):
        # 候補者表の党派欄の注記（{{Efn2|...推薦}}）から推薦を読む
        self.assertEqual(g.endorsements(FX["tokushima_election"], "飯泉嘉門", "飯泉嘉門"), "自由民主党徳島県連推薦")

    def test_table_end_not_in_cell(self):
        cells = g.split_cells("|A||無所属{{Efn2|支援：B党}}\n|}")
        self.assertEqual(cells[-1], "無所属{{Efn2|支援：B党}}")

    def test_career_no_blank(self):
        self.assertEqual(g.strip_markup("\n"), "")

    def test_tidy(self):
        self.assertEqual(g.tidy_support("（推薦）自由民主党・公明党"), "推薦：自由民主党・公明党")


class Build(unittest.TestCase):
    def test_build_with_fixture(self):
        texts = {g.LIST_PAGE: FX["list"].replace("\n|}\n", "\n") * 1}
        with self.assertRaises(RuntimeError):  # 4 都道府県しか読めない一覧は採用しない
            g.build(lambda ts: {t: texts[t] for t in ts if t in texts}, dt.date(2026, 11, 11))


if __name__ == "__main__":
    unittest.main()
