"""【調査用】指定した記事のウィキテキストを probe/governors/ に保存する。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from update_governors import fetch_wikitext  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "probe" / "governors"
TITLES = ["吉村美栄子", "2025年山形県知事選挙", "2021年山形県知事選挙", "浜田省司", "2023年高知県知事選挙",
          "塩田康一", "2024年鹿児島県知事選挙"]

OUT.mkdir(parents=True, exist_ok=True)
for t, text in fetch_wikitext(TITLES).items():
    (OUT / f"dbg_{t}.txt").write_text(text, encoding="utf-8")
    print(t, len(text))
