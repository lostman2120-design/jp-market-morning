#!/usr/bin/env python3
"""data/ から静的HTMLを生成して site/ に出力する。"""
from __future__ import annotations

import argparse
import html
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.common import DATA_DIR, ROOT, fmt_date_ja, load_json

E = lambda s: html.escape("" if s is None else str(s), quote=True)  # noqa: E731

CSS = """
:root{--bg:#f5f6f8;--card:#fff;--text:#1c1e21;--sub:#6b7280;--line:#e5e7eb;--up:#d32f2f;--down:#1b8a4b;--accent:#2563eb;--badge:#eef2ff;}
@media (prefers-color-scheme: dark){:root{--bg:#111318;--card:#1b1e25;--text:#e8eaed;--sub:#9aa0a6;--line:#2c313a;--up:#ff6b6b;--down:#4cd08a;--accent:#8ab4f8;--badge:#262b3a;}}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--text);font:16px/1.6 -apple-system,BlinkMacSystemFont,"Hiragino Sans","Noto Sans JP",sans-serif;overflow-x:hidden}
main{max-width:640px;margin:0 auto;padding:16px}
h1{font-size:1.4rem;margin:0}
h2{font-size:1.1rem;margin:24px 0 8px}
a{color:var(--accent)}
.date{color:var(--sub);margin:2px 0 12px}
.idx{display:flex;flex-wrap:wrap;gap:8px 16px;font-size:.9rem;margin:0 0 12px;padding:0;list-style:none}
.summary{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px;font-size:.95rem}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px;margin:0 0 10px}
.top{display:flex;justify-content:space-between;align-items:baseline;gap:8px}
.name{font-weight:600;overflow-wrap:anywhere}
.rank{color:var(--sub);margin-right:6px;font-variant-numeric:tabular-nums}
.chg{font-weight:700;font-size:1.15rem;white-space:nowrap;font-variant-numeric:tabular-nums}
.up{color:var(--up)}.down{color:var(--down)}
.meta{color:var(--sub);font-size:.8rem;margin:2px 0}
.nums{font-size:.9rem;display:flex;gap:16px;margin:4px 0}
.reason{border-top:1px solid var(--line);margin-top:8px;padding-top:8px;font-size:.92rem;overflow-wrap:anywhere}
.badge{display:inline-block;background:var(--badge);border-radius:6px;padding:0 6px;font-size:.78rem;margin-right:6px}
.conf{color:var(--sub);font-size:.8rem;margin-left:4px}
.src{display:block;font-size:.8rem;margin-top:2px}
.pending{color:var(--sub)}
footer{color:var(--sub);font-size:.8rem;margin:24px 0 8px}
ul.arch{padding-left:20px}
"""


def safe_url(u) -> str | None:
    if isinstance(u, str) and u.strip().lower().startswith(("http://", "https://")):
        return u.strip()
    return None


def fmt_pct(x) -> str:
    if x is None:
        return "-"
    return f"{x:+.2f}%"


def fmt_index(ix: dict) -> str:
    c = ix.get("close")
    if c is None:
        return f"<li>{E(ix.get('name'))} -</li>"
    pct = ix.get("change_pct")
    cls = "" if pct is None else ("up" if pct > 0 else "down" if pct < 0 else "")
    arrow = "" if pct is None else ("▲" if pct > 0 else "▼" if pct < 0 else "")
    pct_s = "" if pct is None else f' <span class="{cls}">{arrow}{pct:+.2f}%</span>'
    return f"<li>{E(ix.get('name'))} {c:,.2f}{pct_s}</li>"


def reason_html(item, reasons_exist: bool) -> str:
    if not reasons_exist:
        return '<div class="reason pending">理由：準備中（7:30時点で未取得の場合はランキングのみ）</div>'
    if not item or item.get("category") == "不明":
        extra = ""
        if item and item.get("reason"):
            extra = f" {E(item['reason'])}"
        return f'<div class="reason pending">材料不明{extra}</div>'
    srcs = []
    for s in item.get("sources") or []:
        url = safe_url(s.get("url") if isinstance(s, dict) else None)
        if not url:
            continue
        title = str(s.get("title") or url)
        if len(title) > 24:
            title = title[:24] + "…"
        srcs.append(f'<a class="src" href="{E(url)}" rel="noopener noreferrer nofollow" target="_blank">{E(title)}</a>')
    return (
        f'<div class="reason"><span class="badge">{E(item.get("category"))}</span>'
        f'{E(item.get("reason"))}<span class="conf">確度：{E(item.get("confidence"))}</span>'
        f'{"".join(srcs)}</div>'
    )


def card_html(s: dict, item, reasons_exist: bool) -> str:
    pct = s["change_pct"]
    cls = "up" if pct > 0 else "down"
    arrow = "▲" if pct > 0 else "▼"
    oku = s["turnover_approx"] / 1e8
    code = E(s["code"])
    return (
        f'<div class="card"><div class="top"><div class="name">'
        f'<span class="rank">{E(s["rank"])}</span>'
        f'<a href="https://kabutan.jp/stock/?code={E(s["code"])}" rel="noopener noreferrer" target="_blank">{E(s["name"])}</a> '
        f'<span class="meta">{code}</span></div>'
        f'<div class="chg {cls}">{arrow}{pct:+.2f}%</div></div>'
        f'<div class="meta">{E(s["market"])}・{E(s["sector"])}</div>'
        f'<div class="nums"><span>終値 {s["close"]:,.0f}円</span><span>売買代金 約{oku:,.1f}億円</span></div>'
        f'{reason_html(item, reasons_exist)}</div>'
    )


def page_shell(title: str, body: str) -> str:
    return (
        '<!doctype html><html lang="ja"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="robots" content="noindex,nofollow">'
        f'<title>{E(title)}</title><style>{CSS}</style></head><body><main>{body}</main></body></html>'
    )


def footer(archive_href: str) -> str:
    return (
        '<footer>売買代金は終値×出来高の概算 / データ: Yahoo Finance(yfinance・非公式) / 投資判断はご自身で'
        f'<br><a href="{E(archive_href)}">過去の記録（アーカイブ）</a></footer>'
    )


def render_day(movers: dict, reasons: dict | None, archive_href: str) -> str:
    items = {}
    if reasons:
        items = {i.get("code"): i for i in reasons.get("items", []) if isinstance(i, dict)}
    exist = reasons is not None
    parts = [
        '<h1>朝の日本株チェック</h1>',
        f'<p class="date">{E(fmt_date_ja(movers["data_date"]))}大引け時点</p>',
    ]
    if movers.get("indices"):
        parts.append('<ul class="idx">' + "".join(fmt_index(i) for i in movers["indices"]) + "</ul>")
    if reasons and reasons.get("market_summary"):
        parts.append(f'<div class="summary">{E(reasons["market_summary"])}</div>')
    for title, key in (("値上がり上位15", "gainers"), ("値下がり上位15", "losers")):
        parts.append(f"<h2>{title}</h2>")
        lst = movers.get(key, [])
        if not lst:
            parts.append('<p class="meta">該当なし</p>')
        for s in lst:
            parts.append(card_html(s, items.get(s["code"]), exist))
    parts.append(
        f'<p class="meta">対象: 売買代金(概算) {movers.get("min_turnover", 0)/1e8:,.0f}億円以上 '
        f'{E(movers.get("filtered_count"))}銘柄 / 全{E(movers.get("universe_count"))}銘柄</p>'
    )
    parts.append(footer(archive_href))
    return page_shell(f"朝の日本株チェック {fmt_date_ja(movers['data_date'])}", "".join(parts))


def render_archive_index(dates: list[str]) -> str:
    lis = "".join(f'<li><a href="{E(d)}.html">{E(fmt_date_ja(d))} ({E(d)})</a></li>' for d in dates)
    body = f'<h1>アーカイブ</h1><ul class="arch">{lis}</ul><footer><a href="../index.html">最新へ戻る</a></footer>'
    return page_shell("朝の日本株チェック アーカイブ", body)


def build(data_dir: Path, out_dir: Path, date: str | None = None) -> None:
    movers_dir = data_dir / "movers"
    dates = sorted((p.stem for p in movers_dir.glob("*.json")), reverse=True)
    if not dates:
        raise SystemExit("data/movers にデータがありません")
    if date is None:
        latest = data_dir / "latest.json"
        date = load_json(latest)["data_date"] if latest.exists() else dates[0]
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "archive").mkdir(exist_ok=True)
    (out_dir / ".nojekyll").write_text("")

    def load_reasons(d):
        p = data_dir / "reasons" / f"{d}.json"
        if not p.exists():
            return None
        try:
            return load_json(p)
        except Exception as e:  # noqa: BLE001
            print(f"WARN: reasons {d} 読み込み失敗: {e}", file=sys.stderr)
            return None

    for d in dates:
        m = load_json(movers_dir / f"{d}.json")
        (out_dir / "archive" / f"{d}.html").write_text(
            render_day(m, load_reasons(d), "index.html"), encoding="utf-8")
    m = load_json(movers_dir / f"{date}.json")
    (out_dir / "index.html").write_text(
        render_day(m, load_reasons(date), "archive/index.html"), encoding="utf-8")
    (out_dir / "archive" / "index.html").write_text(render_archive_index(dates), encoding="utf-8")
    print(f"built site for {date} ({len(dates)} archive pages)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date")
    ap.add_argument("--data-dir", default=str(DATA_DIR))
    ap.add_argument("--out", default=str(ROOT / "site"))
    a = ap.parse_args()
    build(Path(a.data_dir), Path(a.out), a.date)
    return 0


if __name__ == "__main__":
    sys.exit(main())
