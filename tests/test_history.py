"""scripts/history/build_dpj_era.py（民主党政権期の比較データ）のテスト。

総務省が公表した全国集計（各年の「調査結果の概要」）と、県別の表から読んだ値の合計が一致するかを確かめる。
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "history"))

import build_dpj_era as h  # noqa: E402

RAW = ROOT / "data" / "raw" / "history"
COMMITTED = ROOT / "src" / "data" / "history.json"

# 総務省の公表値（都道府県議会議員の党派別人員）
OFFICIAL = {
    "2009": {"自由民主党": 1277, "民主党": 429, "公明党": 208, "日本共産党": 114, "社会民主党": 59, "国民新党": 1, "諸派": 45, "無所属": 575},
    "2010": {"自由民主党": 1268, "民主党": 443, "公明党": 207, "日本共産党": 115, "社会民主党": 57},
    "2011": {"自由民主党": 1271, "民主党": 455, "公明党": 209, "日本共産党": 105, "社会民主党": 41, "みんなの党": 46},
}
# 市区町村議会の民主党（2009年末の概要: 1,105 人）
OFFICIAL_LOCAL_DPJ_2009 = 1105


def totals(snap, key="assembly"):
    out = {}
    for p in snap["prefectures"].values():
        if p[key]:
            for k, n in p[key]["parties"].items():
                out[k] = out.get(k, 0) + n
    return out


class HistoryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "history.json"
            orig = h.OUTPUT
            h.OUTPUT = out
            try:
                h.main(["x", str(RAW)])
            finally:
                h.OUTPUT = orig
            cls.data = json.loads(out.read_text(encoding="utf-8"))

    def test_matches_official_totals(self):
        for snap in self.data["snapshots"]:
            t = totals(snap)
            for party, n in OFFICIAL[snap["id"]].items():
                self.assertEqual(t.get(party), n, f"{snap['asOf']} {party}")

    def test_local_assemblies_2009(self):
        snap = next(s for s in self.data["snapshots"] if s["id"] == "2009")
        n = totals(snap, "cityAssembly").get("民主党", 0) + totals(snap, "townAssembly").get("民主党", 0)
        self.assertEqual(n, OFFICIAL_LOCAL_DPJ_2009)

    def test_each_prefecture_is_consistent(self):
        for snap in self.data["snapshots"]:
            self.assertEqual(len(snap["prefectures"]), 47)
            for name, p in snap["prefectures"].items():
                a = p["assembly"]
                self.assertEqual(sum(a["parties"].values()) + a["vacant"], a["fixed"], f"{snap['id']} {name}")
                self.assertIsNotNone(p["governor"], f"{snap['id']} {name}")

    def test_committed_file_is_up_to_date(self):
        self.assertEqual(json.loads(COMMITTED.read_text(encoding="utf-8")), self.data)


if __name__ == "__main__":
    unittest.main()
