# 都道府県議会の党派構成

全国 47 都道府県の議会・知事・市区町村議会の所属党派別の構成を、総務省の公式統計から可視化するサイトです。
**データの取得から公開まで全自動で、人の手による保守は不要**です。

## 仕組み

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
| 各県議会サイトのリンク切れ | 県ごとの URL を持たない（Wikipedia と検索へのリンクのみ） |

> **注意**: 表示しているのは議員が選挙管理委員会に届け出ている「所属党派」で、議会内の「会派」とは異なります。
> 会派は県ごとに名称も公開形式もバラバラで自動取得が安定しないため、扱っていません。

## 開発

```bash
npm install
npm run dev          # http://localhost:5173
npm run build        # build/ に出力（Cloudflare Pages の出力先）

pip install -r scripts/requirements.txt
npm run update-data  # 総務省から最新データを取得
npm run test:data    # データ解析のテスト
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
- `tests/` … 解析ロジックのテスト（実際の総務省の Excel を使用）
- `src/data/latest.json` … サイトが表示するデータ（自動生成）
- `data/raw/` … 取り込んだ総務省の Excel の原本（記録用）
- `src/` … フロントエンド（React + Vite）
