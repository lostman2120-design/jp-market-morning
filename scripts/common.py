"""共通ユーティリティ / shared helpers."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

JST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
WEEKDAYS_JA = "月火水木金土日"


def now_jst() -> datetime:
    return datetime.now(JST)


def load_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, obj) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")


def fmt_date_ja(date_str: str) -> str:
    """'2025-01-06' -> '1月6日（月）'"""
    d = datetime.strptime(date_str, "%Y-%m-%d")
    return f"{d.month}月{d.day}日（{WEEKDAYS_JA[d.weekday()]}）"
