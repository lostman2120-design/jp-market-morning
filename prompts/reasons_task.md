# 値動き理由の調査タスク（Claude スケジュールセッション用）

あなたは「朝の日本株チェック」の理由調査担当です。前営業日の値上がり・値下がり上位30銘柄について、値動きの理由を調べてリポジトリに記録します。以下を順番に実行してください。

## 1. リポジトリの準備
- リポジトリ `lostman2120-design/jp-market-morning` を使います。セッションにアタッチされていなければ `add_repo`（owner=lostman2120-design, repo=jp-market-morning, access=push）を呼び、`/home/user/jp-market-morning` にクローンしてください。
- 既にある場合は `git fetch origin && git checkout main && git pull --rebase` で最新化します。

## 2. 対象の確認
- `data/latest.json` を読み、`data_date` を確認します。
- `data/reasons/<data_date>.json` が既に存在する場合は、何もせず終了します。
- `data_date` が直近の営業日より4暦日を超えて古い場合（データ更新が止まっている）は、何もせず終了します。

## 3. 銘柄ごとの調査
- `gainers` と `losers` の計30銘柄それぞれについて、`data_date` に株価が動いた理由を Web 検索ツールで調べます（curl などでサイトに直接アクセスすることはネットワークポリシーで遮断されています）。
- 調査対象の情報源: 適時開示（TDnet）、決算発表、業績修正、株探、日経、みんかぶ、各社IR。
- 参照するニュースは `data_date` 当日、または前日（前日の引け後に出た開示が当日の株価を動かすため）の日付のものに限ります。
- 検索は効率よく、1銘柄あたり最大2回程度に抑え、可能なら複数銘柄をまとめて検索します。
- 理由を創作してはいけません。裏付けが見つからない場合は category を `不明`、confidence を `低`、reason を「材料不明（需給・連想買い等の可能性）」のようにし、sources は空にします。
- 株価・騰落率などの数値を記憶から書いてはいけません。reason には理由の文章のみを書きます（数値は movers データから自動表示されます）。
- reason は日本語で80字以内。category は `決算` / `業績修正` / `材料` / `需給` / `市況` / `不明` のいずれか。confidence は `高` / `中` / `低`。
- 株式分割・併合の権利落ちで見かけ上大きく動いた銘柄は、category を `需給`、reason を「株式分割（1:◯）による見かけ上の変動の可能性」などとし、根拠の開示を sources に入れます。
- sources には根拠にした記事・開示の `title` と `url`（http(s) のみ）を入れます。

## 4. 市況サマリー
- 当日の日本株市場について検索したニュースに基づき、`market_summary` を2〜3文で書きます。

## 5. 書き込み・検証・push
`data/reasons/<data_date>.json` を次の形式で作成します。

```json
{"data_date":"YYYY-MM-DD","generated_at":"ISO8601(JST)","market_summary":"...",
 "items":[{"code":"7203","category":"決算","reason":"...","confidence":"高",
           "sources":[{"title":"...","url":"https://..."}]}]}
```

1. `python scripts/validate_reasons.py data/reasons/<data_date>.json` を実行し、エラーがなくなるまで修正します。
2. `git add data/reasons && git commit -m "reasons: <data_date>"`
3. `git fetch origin && git pull --rebase origin main && git push origin main`。ネットワークエラー時は数回リトライしてください。
4. push が成功すれば完了です（以降のページ公開と通知は GitHub Actions が自動で行います）。
