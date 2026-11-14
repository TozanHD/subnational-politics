"""一時的な調査: 指定の総務省ファイルを保存する。"""
import sys, time, urllib.request, pathlib
sys.path.insert(0, "scripts")
from update_data import USER_AGENT
OUT = pathlib.Path("probe/soumu"); OUT.mkdir(parents=True, exist_ok=True)
for u in ["https://www.soumu.go.jp/main_content/000115998.xls",
          "https://www.soumu.go.jp/main_content/000151834.xls",
          "https://www.soumu.go.jp/senkyo/senkyo_s/data/syozoku/h22.html",
          "https://www.soumu.go.jp/senkyo/senkyo_s/data/syozoku/ichiran.html"]:
    req = urllib.request.Request(u, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as r: (OUT / u.split("/")[-1]).write_bytes(r.read())
    time.sleep(1)
print("ok")
