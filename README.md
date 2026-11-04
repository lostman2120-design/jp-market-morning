# jp-market-morning（朝の日本株チェック）

平日朝、スマホで「前日の東証 値上がり上位15・値下がり上位15」と、その理由を確認するための個人用ページです。対象は東証の内国株式（プライム／スタンダード／グロース）のうち、売買代金（概算）が10億円以上の銘柄です。運用コストは0円（GitHub Actions + GitHub Pages + ntfy.sh）。

## 処理の流れ

```
06:00 JST  GitHub Actions morning.yml
             fetch_movers.py -> data/latest.json, data/movers/DATE.json
             build_page.py   -> GitHub Pages へデプロイ（ランキングのみ）
06:40 JST  Claude スケジュールセッション（prompts/reasons_task.md）
             Web検索で理由調査 -> data/reasons/DATE.json を main に push
push 契機   publish.yml: ページ再生成・デプロイ -> ntfy 通知（理由付き）
07:30 JST  fallback.yml: 未通知なら ntfy 通知（ランキングのみ）
```

休場日は `data/latest.json` の日付が変わらないため何も更新されません。

## セットアップ

1. GitHub リポジトリの Settings -> Pages -> Source を **GitHub Actions** にする。
2. Settings -> Secrets and variables -> Actions に `NTFY_TOPIC` を追加（推測されにくい長めの文字列）。
3. スマホの ntfy アプリで同じトピックを購読する。
4. Claude のスケジュールセッションに `prompts/reasons_task.md` の内容を指示として登録する（毎営業日 06:40 JST 頃）。
5. ページ URL: https://lostman2120-design.github.io/jp-market-morning/

## 手動実行

- Actions タブ -> `morning` / `publish` / `fallback` -> Run workflow。
- ローカル: `pip install -r requirements.txt` の後 `python scripts/fetch_movers.py` -> `python scripts/build_page.py`（出力は `site/`）。
- テスト: `python -m pytest -q`

## 売買代金のしきい値

`scripts/fetch_movers.py` の `MIN_TURNOVER`（既定 `1e9` = 10億円）。環境変数 `MIN_TURNOVER` で上書きできます（workflow の `env` に追加するか、ローカルで `MIN_TURNOVER=5e8 python scripts/fetch_movers.py`）。

## 注意・リスク

- データは Yahoo Finance を yfinance 経由で取得しており、非公式です。仕様変更・取得失敗の可能性があります（取得銘柄が1000未満なら異常として失敗させます）。
- 売買代金は「終値×出来高」の概算です。
- 理由は AI による Web 検索ベースの推定で、誤りを含む場合があります。投資判断はご自身で行ってください。
- 銘柄一覧は JPX 公開の `data_j.xls` を使用します。ページ構成が変わると取得に失敗する可能性があります。
