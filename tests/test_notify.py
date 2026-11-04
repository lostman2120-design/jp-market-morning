import json

from scripts import notify as n

MOVERS = {"data_date": "2025-01-10",
          "indices": [{"name": "日経平均", "close": 39000.0, "change_pct": 1.0}, {"name": "x", "close": None, "change_pct": None}],
          "gainers": [{"name": f"G{i}", "change_pct": 10.0 - i} for i in range(5)],
          "losers": [{"name": f"L{i}", "change_pct": -10.0 + i} for i in range(5)]}


def setup(tmp_path):
    (tmp_path / "latest.json").write_text(json.dumps(MOVERS), encoding="utf-8")
    return tmp_path


def test_decide():
    s = lambda f, b: {"full": f, "fallback": b}  # noqa: E731
    assert n.decide("full", s(False, False)) == "朝の日本株チェック（理由付き）"
    assert n.decide("full", s(False, True)) == "理由を追記しました"
    assert n.decide("full", s(True, False)) is None
    assert n.decide("fallback", s(False, False)) == "朝の日本株チェック（ランキングのみ）"
    assert n.decide("fallback", s(False, True)) is None
    assert n.decide("fallback", s(True, False)) is None


def test_message():
    m = n.build_message(MOVERS)
    assert "G0 +10.0%" in m and "L0 -10.0%" in m and "G3" not in m
    assert len(m.encode()) < 3000


def test_flow(tmp_path):
    d = setup(tmp_path)
    sent = []
    env = {"NTFY_TOPIC": "t", "PAGE_URL": "https://p/"}
    fake = lambda server, topic, title, msg, click: sent.append((server, topic, title, click))  # noqa: E731
    assert n.run("fallback", d, env, fake) == 0
    assert n.run("fallback", d, env, fake) == 0
    assert n.run("full", d, env, fake) == 0
    assert n.run("full", d, env, fake) == 0
    assert [s[2] for s in sent] == ["朝の日本株チェック（ランキングのみ）", "理由を追記しました"]
    assert sent[0][0] == "https://ntfy.sh" and sent[0][3] == "https://p/"
    st = json.loads((d / "notified" / "2025-01-10.json").read_text())
    assert st == {"full": True, "fallback": True}


def test_no_topic(tmp_path):
    d = setup(tmp_path)
    called = []
    assert n.run("full", d, {}, lambda *a: called.append(1)) == 0
    assert not called


def test_send_http(monkeypatch):
    import requests
    calls = {}

    class R:
        def raise_for_status(self): pass

    monkeypatch.setattr(requests, "post", lambda url, json, timeout: calls.update(url=url, json=json) or R())
    n.send("https://ntfy.sh", "t", "タイトル", "msg", "https://p/")
    assert calls["url"] == "https://ntfy.sh/" and calls["json"]["topic"] == "t"
    assert calls["json"]["click"] == "https://p/"
