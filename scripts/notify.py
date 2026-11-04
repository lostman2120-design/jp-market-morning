#!/usr/bin/env python3
"""ntfy 通知。--mode full|fallback"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.common import DATA_DIR, fmt_date_ja, load_json, save_json

MAX_BYTES = 3000


def state_path(data_dir: Path, date: str) -> Path:
    return Path(data_dir) / "notified" / f"{date}.json"


def load_state(data_dir: Path, date: str) -> dict:
    p = state_path(data_dir, date)
    if p.exists():
        try:
            s = load_json(p)
            return {"full": bool(s.get("full")), "fallback": bool(s.get("fallback"))}
        except Exception:  # noqa: BLE001
            pass
    return {"full": False, "fallback": False}


def decide(mode: str, state: dict) -> str | None:
    """送るべきなら title を返し、不要なら None。"""
    if mode == "full":
        if state["full"]:
            return None
        return "理由を追記しました" if state["fallback"] else "朝の日本株チェック（理由付き）"
    if mode == "fallback":
        if state["full"] or state["fallback"]:
            return None
        return "朝の日本株チェック（ランキングのみ）"
    raise ValueError(mode)


def build_message(movers: dict) -> str:
    lines = [f"{fmt_date_ja(movers['data_date'])}大引け"]
    idx = []
    for i in movers.get("indices") or []:
        if i.get("close") is None:
            continue
        pct = f" {i['change_pct']:+.2f}%" if i.get("change_pct") is not None else ""
        idx.append(f"{i['name']} {i['close']:,.2f}{pct}")
    if idx:
        lines.append(" / ".join(idx))
    for label, key in (("値上がり", "gainers"), ("値下がり", "losers")):
        lines.append(f"【{label}】")
        for s in movers.get(key, [])[:3]:
            lines.append(f"{s['name']} {s['change_pct']:+.1f}%")
    msg = "\n".join(lines)
    while len(msg.encode("utf-8")) > MAX_BYTES:
        msg = msg[:-1]
    return msg


def send(server: str, topic: str, title: str, message: str, click: str | None) -> None:
    import requests

    payload = {"topic": topic, "title": title, "message": message,
               "tags": ["chart_with_upwards_trend"]}
    if click:
        payload["click"] = click
    r = requests.post(server.rstrip("/") + "/", json=payload, timeout=20)
    r.raise_for_status()


def run(mode: str, data_dir: Path, env=os.environ, sender=send) -> int:
    topic = env.get("NTFY_TOPIC")
    if not topic:
        print("WARN: NTFY_TOPIC が未設定のため通知をスキップします")
        return 0
    latest = Path(data_dir) / "latest.json"
    if not latest.exists():
        print("WARN: data/latest.json がありません")
        return 0
    movers = load_json(latest)
    date = movers["data_date"]
    state = load_state(data_dir, date)
    title = decide(mode, state)
    if title is None:
        print(f"skip: already notified ({mode}, {date})")
        return 0
    sender(env.get("NTFY_SERVER") or "https://ntfy.sh", topic, title,
           build_message(movers), env.get("PAGE_URL") or None)
    state["full" if mode == "full" else "fallback"] = True
    save_json(state_path(data_dir, date), state)
    print(f"sent: {title} ({date})")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["full", "fallback"], required=True)
    ap.add_argument("--data-dir", default=str(DATA_DIR))
    a = ap.parse_args()
    return run(a.mode, Path(a.data_dir))


if __name__ == "__main__":
    sys.exit(main())
