import json

from scripts import build_page as bp

STOCK = {"rank": 1, "code": "7203", "name": "トヨタ自動車", "market": "プライム",
         "sector": "輸送用機器", "close": 3000.0, "prev_close": 2900.0,
         "change_pct": 3.45, "volume": 1000000, "turnover_approx": 3_000_000_000}
LOSER = dict(STOCK, code="130A", name="ロス", change_pct=-4.2)
MOVERS = {"data_date": "2025-01-10", "min_turnover": 1e9, "universe_count": 3000,
          "filtered_count": 2, "indices": [{"name": "日経平均", "symbol": "^N225", "close": 39000.5, "change_pct": 1.2}],
          "gainers": [STOCK], "losers": [LOSER]}


def setup(tmp_path, reasons=None):
    d = tmp_path / "data"
    (d / "movers").mkdir(parents=True)
    (d / "movers" / "2025-01-10.json").write_text(json.dumps(MOVERS), encoding="utf-8")
    (d / "latest.json").write_text(json.dumps(MOVERS), encoding="utf-8")
    if reasons:
        (d / "reasons").mkdir()
        (d / "reasons" / "2025-01-10.json").write_text(json.dumps(reasons), encoding="utf-8")
    out = tmp_path / "site"
    bp.build(d, out)
    return out


def test_missing_reasons(tmp_path):
    out = setup(tmp_path)
    h = (out / "index.html").read_text(encoding="utf-8")
    assert "準備中" in h and "1月10日（金）大引け時点" in h
    assert "▲+3.45%" in h and "▼-4.20%" in h and "30.0億円" in h
    assert 'name="robots" content="noindex,nofollow"' in h
    assert (out / ".nojekyll").exists()
    assert (out / "archive" / "2025-01-10.html").exists()
    assert (out / "archive" / "index.html").exists()


def test_escape_and_url(tmp_path):
    reasons = {"data_date": "2025-01-10", "market_summary": "<b>x</b>", "items": [
        {"code": "7203", "category": "材料", "reason": "<script>alert(1)</script>", "confidence": "中",
         "sources": [{"title": "<i>t</i>", "url": "javascript:alert(1)"},
                     {"title": "ok", "url": "https://example.com/?a=1&b=2"}]}]}
    out = setup(tmp_path, reasons)
    h = (out / "index.html").read_text(encoding="utf-8")
    assert "<script>" not in h and "&lt;script&gt;" in h
    assert "javascript:" not in h
    assert "&lt;b&gt;x" in h
    assert 'href="https://example.com/?a=1&amp;b=2"' in h
    assert "材料不明" in h  # 130A has no item
