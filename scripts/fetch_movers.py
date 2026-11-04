#!/usr/bin/env python3
"""前営業日の値上がり・値下がりランキングを取得して data/ に保存する。"""
from __future__ import annotations

import os
import re
import sys
import time
from collections import Counter
from pathlib import Path
from urllib.parse import urljoin

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from scripts.common import DATA_DIR, load_json, now_jst, save_json

JPX_PAGE = "https://www.jpx.co.jp/markets/statistics-equities/misc/01.html"
MIN_TURNOVER = float(os.environ.get("MIN_TURNOVER", "1e9"))
TOP_N = 15
BATCH_SIZE = 100
MIN_TICKERS_OK = 1000
MARKETS = ("プライム", "スタンダード", "グロース")
INDICES = [
    ("日経平均", "^N225"),
    ("S&P500", "^GSPC"),
    ("ドル円", "USDJPY=X"),
]
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36", "Accept-Language": "ja"}


# ---------------------------------------------------------------- universe
def classify_market(label) -> str | None:
    """'プライム（内国株式）' -> 'プライム'。対象外は None。"""
    if not isinstance(label, str):
        return None
    if "内国株式" not in label:
        return None
    for m in MARKETS:
        if m in label:
            return m
    return None


def parse_universe(df: pd.DataFrame) -> dict[str, dict]:
    """JPX 上場銘柄一覧 DataFrame -> {code: {name, market, sector}}"""
    out: dict[str, dict] = {}
    for _, row in df.iterrows():
        market = classify_market(row.get("市場・商品区分"))
        if not market:
            continue
        code = str(row["コード"]).strip()
        if code.endswith(".0"):  # 数値として読まれた場合の保険
            code = code[:-2]
        if not code:
            continue
        sector = row.get("33業種区分", "")
        out[code] = {
            "name": str(row.get("銘柄名", "")).strip(),
            "market": market,
            "sector": "" if pd.isna(sector) else str(sector).strip(),
        }
    return out


FALLBACK_XLS = "https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq0000001vg2-att/data_j.xls"


def find_xls_url(html: str, base: str = JPX_PAGE) -> str:
    """上場銘柄一覧(data_j.xls / .xlsx)のURLを探す。見つからなければ既知のURL。"""
    hrefs = re.findall(r"""href\s*=\s*["']([^"']+)["']""", html, flags=re.I)
    for pat in (r"data_j\.xlsx?$", r"\.xlsx?$"):
        for h in hrefs:
            if re.search(pat, h, flags=re.I):
                return urljoin(base, h)
    files = [h for h in hrefs if re.search(r"\.(xlsx?|csv|zip)$", h, flags=re.I)]
    print(f"WARN: data_j.xls のリンクが見つかりません。候補={files[:10]} 先頭={html[:300]!r}", file=sys.stderr)
    return FALLBACK_XLS


def read_listing(content: bytes, url: str) -> pd.DataFrame:
    import io

    engine = "openpyxl" if url.lower().endswith(".xlsx") or content[:2] == b"PK" else "xlrd"
    return pd.read_excel(io.BytesIO(content), engine=engine, dtype={"コード": str})


def load_universe() -> dict[str, dict]:
    import requests

    r = requests.get(JPX_PAGE, headers=UA, timeout=30)
    print(f"JPX page: HTTP {r.status_code}, {len(r.content)} bytes, final={r.url}")
    r.raise_for_status()
    r.encoding = r.apparent_encoding or r.encoding
    url = find_xls_url(r.text)
    print(f"listing url: {url}")
    r = requests.get(url, headers=UA, timeout=60)
    r.raise_for_status()
    return parse_universe(read_listing(r.content, url))


# ---------------------------------------------------------------- download
def split_batch_frame(raw: pd.DataFrame, tickers: list[str]) -> dict[str, pd.DataFrame]:
    """yf.download(group_by='ticker') の戻りを {ticker: df(Close, Volume)} に分解。"""
    out: dict[str, pd.DataFrame] = {}
    if raw is None or raw.empty:
        return out
    if isinstance(raw.columns, pd.MultiIndex):
        level0 = set(raw.columns.get_level_values(0))
        level1 = set(raw.columns.get_level_values(1))
        for t in tickers:
            if t in level0:
                sub = raw[t]
            elif t in level1:  # group_by が想定外だった場合の保険
                sub = raw.xs(t, axis=1, level=1)
            else:
                continue
            if {"Close", "Volume"} <= set(sub.columns):
                out[t] = sub[["Close", "Volume"]].copy()
    elif len(tickers) == 1 and {"Close", "Volume"} <= set(raw.columns):
        out[tickers[0]] = raw[["Close", "Volume"]].copy()
    return out


def download_frames(tickers: list[str]) -> dict[str, pd.DataFrame]:
    import yfinance as yf

    frames: dict[str, pd.DataFrame] = {}
    for i in range(0, len(tickers), BATCH_SIZE):
        batch = tickers[i : i + BATCH_SIZE]
        for attempt in range(3):
            try:
                raw = yf.download(
                    batch, period="7d", interval="1d", group_by="ticker",
                    auto_adjust=False, threads=True, progress=False,
                )
                frames.update(split_batch_frame(raw, batch))
                break
            except Exception as e:  # noqa: BLE001
                wait = 2 ** (attempt + 1)
                print(f"batch {i} failed ({e!r}); retry in {wait}s", file=sys.stderr)
                time.sleep(wait)
        time.sleep(1.5)
        if (i // BATCH_SIZE) % 10 == 0:
            print(f"downloaded {min(i + BATCH_SIZE, len(tickers))}/{len(tickers)}", flush=True)
    return frames


def fetch_indices() -> list[dict]:
    import yfinance as yf

    out = []
    for name, sym in INDICES:
        item = {"name": name, "symbol": sym, "close": None, "change_pct": None}
        try:
            h = yf.Ticker(sym).history(period="7d", interval="1d", auto_adjust=False)
            if sym.startswith("^N") and now_jst().hour < 16:  # 日本の指数は場中の当日足を除外
                h = h[[pd.Timestamp(x).date() < now_jst().date() for x in h.index]]
            c = h["Close"].dropna()
            if len(c) >= 2:
                item["close"] = round(float(c.iloc[-1]), 2)
                item["change_pct"] = round((float(c.iloc[-1]) / float(c.iloc[-2]) - 1) * 100, 2)
        except Exception as e:  # noqa: BLE001
            print(f"index {sym} failed: {e!r}", file=sys.stderr)
        out.append(item)
    return out


# ---------------------------------------------------------------- compute
def compute_movers(
    frames: dict[str, pd.DataFrame],
    universe: dict[str, dict],
    min_turnover: float = MIN_TURNOVER,
    top_n: int = TOP_N,
) -> dict | None:
    """純粋計算。frames は {ticker("7203.T"): DataFrame(index=日付, Close, Volume)}。

    データが一件もなければ None。indices/generated_at は呼び出し側で付与する。
    """
    cleaned: dict[str, pd.DataFrame] = {}
    for t, df in frames.items():
        if df is None or df.empty or "Close" not in df:
            continue
        d = df.dropna(subset=["Close"])
        if not d.empty:
            cleaned[t] = d
    if not cleaned:
        return None

    last_dates = Counter(pd.Timestamp(d.index[-1]).date() for d in cleaned.values())
    data_date = last_dates.most_common(1)[0][0]

    rows = []
    for t, d in cleaned.items():
        code = t[:-2] if t.endswith(".T") else t
        meta = universe.get(code)
        if meta is None:
            continue
        idx = [pd.Timestamp(x).date() for x in d.index]
        if idx[-1] != data_date or len(d) < 2:
            continue
        close = float(d["Close"].iloc[-1])
        prev = float(d["Close"].iloc[-2])
        vol = d["Volume"].iloc[-1] if "Volume" in d else float("nan")
        if pd.isna(vol) or vol <= 0 or prev <= 0:
            continue
        vol = float(vol)
        rows.append({
            "code": code, "name": meta["name"], "market": meta["market"],
            "sector": meta["sector"], "close": round(close, 2),
            "prev_close": round(prev, 2),
            "change_pct": round((close / prev - 1) * 100, 2),
            "volume": int(vol), "turnover_approx": round(close * vol),
        })

    filtered = [r for r in rows if r["turnover_approx"] >= min_turnover]
    gainers = sorted((r for r in filtered if r["change_pct"] > 0),
                     key=lambda r: r["change_pct"], reverse=True)[:top_n]
    losers = sorted((r for r in filtered if r["change_pct"] < 0),
                    key=lambda r: r["change_pct"])[:top_n]
    for lst in (gainers, losers):
        for i, r in enumerate(lst, 1):
            r["rank"] = i
    order = ["rank", "code", "name", "market", "sector", "close", "prev_close",
             "change_pct", "volume", "turnover_approx"]
    return {
        "data_date": data_date.isoformat(),
        "min_turnover": min_turnover,
        "universe_count": len(cleaned),
        "filtered_count": len(filtered),
        "gainers": [{k: r[k] for k in order} for r in gainers],
        "losers": [{k: r[k] for k in order} for r in losers],
    }


def drop_incomplete_today(frames: dict[str, pd.DataFrame], now) -> dict[str, pd.DataFrame]:
    """16時(JST)より前の実行では当日の足（場中の途中値）を除外する。"""
    if now.hour >= 16:
        return frames
    today = now.date()
    out = {}
    for t, df in frames.items():
        keep = [pd.Timestamp(x).date() < today for x in df.index]
        out[t] = df[keep]
    return out


def is_new_trading_day(data_date: str, latest_path: Path) -> bool:
    """latest.json と同じ data_date なら False（休場日などで更新なし）。"""
    latest_path = Path(latest_path)
    if not latest_path.exists():
        return True
    try:
        return load_json(latest_path).get("data_date") != data_date
    except Exception:  # noqa: BLE001
        return True


def assemble(result: dict, indices: list[dict]) -> dict:
    return {
        "data_date": result["data_date"],
        "generated_at": now_jst().isoformat(timespec="seconds"),
        "min_turnover": result["min_turnover"],
        "universe_count": result["universe_count"],
        "filtered_count": result["filtered_count"],
        "indices": indices,
        "gainers": result["gainers"],
        "losers": result["losers"],
    }


def main() -> int:
    universe = load_universe()
    print(f"universe: {len(universe)} stocks")
    tickers = [c + ".T" for c in sorted(universe)]
    frames = download_frames(tickers)
    got = sum(1 for d in frames.values() if d is not None and not d.dropna(how="all").empty)
    print(f"tickers with data: {got}")
    if got < MIN_TICKERS_OK:
        print(f"ERROR: データ取得が {got} 銘柄のみ（<{MIN_TICKERS_OK}）。データソース異常の可能性。", file=sys.stderr)
        return 1
    frames = drop_incomplete_today(frames, now_jst())
    result = compute_movers(frames, universe)
    if result is None:
        print("ERROR: no usable data", file=sys.stderr)
        return 1
    latest = DATA_DIR / "latest.json"
    if not is_new_trading_day(result["data_date"], latest):
        print("no new trading day")
        return 0
    doc = assemble(result, fetch_indices())
    save_json(DATA_DIR / "movers" / f"{doc['data_date']}.json", doc)
    save_json(latest, doc)
    print(f"wrote data for {doc['data_date']}: gainers={len(doc['gainers'])} losers={len(doc['losers'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
