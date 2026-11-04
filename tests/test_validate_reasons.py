import copy

from scripts.validate_reasons import validate

MOVERS = {"data_date": "2025-01-10",
          "gainers": [{"code": "1001"}, {"code": "1002"}],
          "losers": [{"code": "130A"}]}
GOOD = {"data_date": "2025-01-10", "market_summary": "x", "items": [
    {"code": "1001", "category": "決算", "reason": "好決算", "confidence": "高",
     "sources": [{"title": "t", "url": "https://example.com/a"}]},
    {"code": "130A", "category": "不明", "reason": "材料不明", "confidence": "低", "sources": []},
]}


def errs(mutate):
    r = copy.deepcopy(GOOD)
    mutate(r)
    return validate(r, MOVERS)[0]


def test_good_with_warning_for_missing():
    e, w = validate(GOOD, MOVERS)
    assert e == [] and any("1002" in x for x in w)


def test_date_mismatch():
    assert errs(lambda r: r.update(data_date="2025-01-09"))


def test_unknown_code():
    assert errs(lambda r: r["items"][0].update(code="9999"))


def test_duplicate():
    assert errs(lambda r: r["items"][1].update(code="1001"))


def test_bad_category_confidence():
    assert errs(lambda r: r["items"][0].update(category="foo"))
    assert errs(lambda r: r["items"][0].update(confidence="max"))


def test_reason_empty_long():
    assert errs(lambda r: r["items"][0].update(reason=" "))
    assert errs(lambda r: r["items"][0].update(reason="あ" * 121))


def test_sources():
    assert errs(lambda r: r["items"][0].update(sources=[]))
    assert errs(lambda r: r["items"][0].update(sources=[{"title": "t", "url": "javascript:alert(1)"}]))
