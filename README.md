# 都道府県議会の党派構成

全国 47 都道府県議会の**会派構成**（各県議会の公式サイトから取得）と、議会・知事・市区町村議会の**所属党派別の構成**（総務省の公式統計）を可視化するサイトです。
**データの取得から公開まで全自動**で、通常は人の手による保守は不要です。

## 仕組み

### 会派構成（各県議会の公式サイト・毎週）

```
scripts/kaiha/sites.json … 47 都道府県それぞれの会派ページと読み取り方式
        │  毎週月曜に GitHub Actions が実行（.github/workflows/update-data.yml）
        ▼
scripts/kaiha/update_kaiha.py
  1. 各県の会派ページ（HTML / PDF）を取得。日付入りの PDF はページ内のリンクから最新を探す
  2. 県ごとの方式で会派と人数を読み取る（scripts/kaiha/readers.py）
  3. 「会派の合計 ≦ 定数」「欠員が多すぎない」「会派名らしい名前か」を検証
  4. 設定どおり読めない県は、議会サイトを巡回して代わりのページを自動で探す
  5. 変化があれば src/data/kaiha.json を更新して main にコミット
  6. 読めなかった県は前回のデータを表示し続け、「会派データ取得エラー」Issue で知らせる
```

| 読み取り方式 | ページの形 | 例 |
| --- | --- | --- |
| `table` | 「会派名｜人数」の表 | 東京・神奈川・京都 |
| `roster` | 議員名簿の「会派」列を数える | 茨城・岐阜・福岡 |
| `paren` | 「自由民主党(30名)」 | 長崎・長野・群馬 |
| `text` | 「自由民主党 29人」 | 埼玉・広島 |
| `grouped` | 会派名の下に議員名が並ぶ | 岩手・石川・滋賀 |
| `columns` | 会派名の行と人数の行が横に並ぶ表（PDF） | 北海道・山梨 |
| `table_rows` | 会派ごとに分かれた表の行数 | 栃木・鳥取 |
| `page_members` | 会派ごとの個別ページの議員数 | 宮崎 |
| `regex` | 議員ごとに「(会派名)」が付く | 佐賀 |

**Issue が届いたら**：県のサイトが大きく改装された可能性があります。`sites.json` の該当県の URL や方式を直してください。
Actions の「会派ページ調査（開発用）」を手動実行すると、現在の取得結果とログが `probe/` に保存されます。

### 所属党派（総務省・年 1 回）

```
総務省「地方公共団体の議会の議員及び長の所属党派別人員調等」（毎年12月31日現在、翌3月ごろ公表）
        │  毎週月曜に GitHub Actions が自動で確認（.github/workflows/update-data.yml）
        ▼
scripts/update_data.py
  1. 総務省サイトを巡回して最新の Excel を自動で探す（URL の決め打ちなし）
  2. 表の見出しから政党名を読み取る（新党が増えても自動で追従）
  3. 47都道府県が揃っているか・政党別の和＝合計か・合計＋欠員＝定数か を検証
  4. 新しい年次なら src/data/latest.json を更新して main にコミット
        │
        ▼
Cloudflare Pages が main へのプッシュを検知して自動ビルド・公開
```

### 壊れないための工夫

| 想定されるトラブル | 対策 |
| --- | --- |
| 総務省のページ構成や Excel の URL が変わる | 選挙関連資料のページを巡回して xlsx を探すので、URL を決め打ちしていない |
| 新しい政党ができる・政党名が変わる | 列を決め打ちせず見出しから読む。色は既知の政党以外は名前から自動で割り当て |
| 表の形式が大きく変わって読めない | 検証に通らなければ既存データは一切変更しない。サイトは前回のデータで動き続け、GitHub から失敗通知メールが届く |
| 古い年次のデータで上書きしてしまう | 既存データより古い基準日では更新しない |
| 長期間コミットが無いと GitHub が定期実行を止める | ワークフローが毎回自分自身を再有効化する |
| 依存ライブラリの更新で壊れる | 依存は React と Vite のみ。`package-lock.json` と `.nvmrc` でバージョンを固定 |
| 県議会サイトの URL が変わる | 日付入りの PDF はリンクから探す。設定の URL で読めなければサイトを巡回して探し直す |
| 県議会サイトの表を読み違える | 選挙区名・委員会名などは会派名として認めず、合計と定数を照合する。おかしければ採用しない |

> 所属党派（総務省）は議員が選挙管理委員会に届け出ている党派、会派は議会内のグループで、両者は一致しないことがあります。

## 開発

```bash
npm install
npm run dev          # http://localhost:5173
npm run build        # build/ に出力（Cloudflare Pages の出力先）

pip install -r scripts/requirements.txt
npm run update-data  # 総務省から最新データを取得
npm run test:data    # データ解析のテスト
python3 scripts/kaiha/update_kaiha.py 群馬県   # 会派データを取得（県名を省略すると全県）
```

手元の Excel から生成する場合:

```bash
python3 scripts/update_data.py --file 手元の.xlsx --as-of 2025-12-31 --source-url https://www.soumu.go.jp/main_content/xxxx.xlsx
```

## Cloudflare Pages の設定

| 項目 | 値 |
| --- | --- |
| ビルドコマンド | `npm run build` |
| 出力ディレクトリ | `build` |
| 本番ブランチ | `main` |

Node のバージョンは `.nvmrc` から自動で読まれます。

## ファイル構成

- `scripts/update_data.py` … 総務省データの取得・解析・検証
- `scripts/kaiha/` … 会派データの取得（`sites.json` 設定 / `readers.py` 読み取り方式 / `update_kaiha.py` 本体 / `crawl.py` 巡回 / `extract.py` HTML・PDF の正規化）
- `tests/` … テスト（実際の総務省の Excel・県議会サイトの文書を使用）
- `src/data/latest.json` / `src/data/kaiha.json` … サイトが表示するデータ（自動生成）
- `data/raw/` … 取り込んだ総務省の Excel の原本（記録用）
- `src/` … フロントエンド（React + Vite）
