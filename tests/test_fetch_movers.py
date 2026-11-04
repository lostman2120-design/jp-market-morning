import numpy as np
import pandas as pd

from scripts import fetch_movers as fm
from scripts.common import save_json


def bars(prev, close, vol, date="2025-01-10", prev_date="2025-01-09"):
    return pd.DataFrame({"Close": [prev, close], "Volume": [vol, vol]},
                        index=pd.to_datetime([prev_date, date]))


UNI = {c: {"name": f"N{c}", "market": "プライム", "sector": "S"} for c in
       ["1001", "1002", "1003", "1004", "1005", "130A"]}


def test_rank_filter_sign():
    frames = {
        "1001.T": bars(100, 110, 20_000_000),   # +10%, turnover 2.2e9
        "1002.T": bars(100, 105, 20_000_000),   # +5%
        "1003.T": bars(100, 90, 20_000_000),    # -10%
        "1004.T": bars(100, 150, 1_000),        # big but low turnover
        "130A.T": bars(100, 95, 30_000_000),    # -5%
        "9999.T": bars(100, 120, 99_999_999),   # not in universe
    }
    r = fm.compute_movers(frames, UNI, min_turnover=1e9)
    assert r["data_date"] == "2025-01-10"
    assert [x["code"] for x in r["gainers"]] == ["1001", "1002"]
    assert [x["code"] for x in r["losers"]] == ["1003", "130A"]
    assert r["gainers"][0]["rank"] == 1 and r["losers"][1]["rank"] == 2
    assert r["gainers"][0]["change_pct"] == 10.0
    assert r["filtered_count"] == 4
    assert all(x["change_pct"] > 0 for x in r["gainers"])
    assert all(x["change_pct"] < 0 for x in r["losers"])


def test_top_n_and_stale_and_nan_volume():
    frames = {f"{1000+i}.T": bars(100, 101 + i, 20_000_000) for i in range(20)}
    uni = {f"{1000+i}": {"name": "x", "market": "グロース", "sector": ""} for i in range(20)}
    frames["1001.T"] = bars(100, 200, np.nan)  # NaN volume -> skipped
    frames["1002.T"] = bars(100, 200, 20_000_000, date="2025-01-09", prev_date="2025-01-08")  # stale
    r = fm.compute_movers(frames, uni)
    assert len(r["gainers"]) == 15
    codes = [g["code"] for g in r["gainers"]]
    assert "1001" not in codes and "1002" not in codes
    assert r["data_date"] == "2025-01-10"


def test_nan_trailing_row_ignored():
    df = bars(100, 110, 20_000_000)
    df.loc[pd.Timestamp("2025-01-11")] = [np.nan, np.nan]
    r = fm.compute_movers({"1001.T": df}, UNI)
    assert r["data_date"] == "2025-01-10"
    assert len(r["gainers"]) == 1


def test_no_data():
    assert fm.compute_movers({}, UNI) is None


def test_holiday_noop(tmp_path):
    p = tmp_path / "latest.json"
    assert fm.is_new_trading_day("2025-01-10", p)
    save_json(p, {"data_date": "2025-01-10"})
    assert not fm.is_new_trading_day("2025-01-10", p)
    assert fm.is_new_trading_day("2025-01-14", p)


def test_parse_universe():
    df = pd.DataFrame({
        "コード": ["7203", "130A", "1305", "2000", "9999", "1234"],
        "銘柄名": ["トヨタ", "X", "ETF", "REIT", "Y", "Z"],
        "市場・商品区分": ["プライム（内国株式）", "グロース(内国株式)", "ETF・ETN",
                     "スタンダード（内国株式）", "プライム（外国株式）", "PRO Market"],
        "33業種区分": ["輸送用機器", "情報", "-", "食料品", "-", "-"],
    })
    u = fm.parse_universe(df)
    assert set(u) == {"7203", "130A", "2000"}
    assert u["130A"]["market"] == "グロース"
    assert u["7203"]["sector"] == "輸送用機器"


def test_find_xls_url():
    html = '<a href="/markets/statistics-equities/misc/tvdivq0000001vg2-att/data_j.xls">x</a>'
    assert fm.find_xls_url(html) == "https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq0000001vg2-att/data_j.xls"


def test_split_batch_frame_multiindex():
    idx = pd.to_datetime(["2025-01-09", "2025-01-10"])
    cols = pd.MultiIndex.from_product([["1001.T", "1002.T"], ["Close", "Volume", "Open"]])
    raw = pd.DataFrame(np.ones((2, 6)), index=idx, columns=cols)
    out = fm.split_batch_frame(raw, ["1001.T", "1002.T", "1003.T"])
    assert set(out) == {"1001.T", "1002.T"}
    assert list(out["1001.T"].columns) == ["Close", "Volume"]


def test_drop_incomplete_today():
    import datetime as dt
    import pandas as pd
    idx = pd.to_datetime(["2026-11-02", "2026-11-04"])
    frames = {"7203.T": pd.DataFrame({"Close": [1.0, 2.0], "Volume": [1, 1]}, index=idx)}
    jst = dt.timezone(dt.timedelta(hours=9))
    morning = dt.datetime(2026, 11, 4, 14, 0, tzinfo=jst)
    assert len(fm.drop_incomplete_today(frames, morning)["7203.T"]) == 1
    evening = dt.datetime(2026, 11, 4, 17, 0, tzinfo=jst)
    assert len(fm.drop_incomplete_today(frames, evening)["7203.T"]) == 2
