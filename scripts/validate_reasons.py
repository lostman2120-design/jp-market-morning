#!/usr/bin/env python3
"""理由ファイルの検証。使い方: python scripts/validate_reasons.py data/reasons/YYYY-MM-DD.json"""
from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.common import DATA_DIR, load_json

CATEGORIES = {"決算", "業績修正", "材料", "需給", "市況", "不明"}
CONFIDENCE = {"高", "中", "低"}
MAX_REASON = 120


def validate(reasons: dict, movers: dict) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warns: list[str] = []
    if not isinstance(reasons, dict):
        return ["ルートがオブジェクトではありません / root must be an object"], warns
    if reasons.get("data_date") != movers.get("data_date"):
        errors.append(f"data_date が一致しません / data_date mismatch: {reasons.get('data_date')} vs {movers.get('data_date')}")
    codes = {s["code"] for s in movers.get("gainers", []) + movers.get("losers", [])}
    items = reasons.get("items")
    if not isinstance(items, list):
        errors.append("items がリストではありません / items must be a list")
        items = []
    seen: set[str] = set()
    for i, it in enumerate(items):
        p = f"items[{i}]"
        if not isinstance(it, dict):
            errors.append(f"{p}: オブジェクトではありません / not an object")
            continue
        code = it.get("code")
        if code not in codes:
            errors.append(f"{p}: コード {code!r} はランキングに存在しません / code not in movers")
        if code in seen:
            errors.append(f"{p}: コード {code!r} が重複 / duplicate code")
        seen.add(code)
        cat = it.get("category")
        if cat not in CATEGORIES:
            errors.append(f"{p}({code}): category 不正 {cat!r} / invalid category (allowed: {sorted(CATEGORIES)})")
        if it.get("confidence") not in CONFIDENCE:
            errors.append(f"{p}({code}): confidence 不正 {it.get('confidence')!r} / invalid confidence")
        reason = it.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            errors.append(f"{p}({code}): reason が空 / reason is empty")
        elif len(reason) > MAX_REASON:
            errors.append(f"{p}({code}): reason が{len(reason)}字 (>{MAX_REASON}) / reason too long")
        src = it.get("sources")
        if not isinstance(src, list):
            errors.append(f"{p}({code}): sources がリストではありません / sources must be a list")
        else:
            if not src and cat != "不明":
                errors.append(f"{p}({code}): 不明以外は出典が必須 / sources required unless category is 不明")
            for j, s in enumerate(src):
                url = s.get("url") if isinstance(s, dict) else None
                if not isinstance(url, str) or not url.startswith(("http://", "https://")):
                    errors.append(f"{p}({code}).sources[{j}]: URL が http(s) ではありません / url must be http(s)")
                if isinstance(s, dict) and not isinstance(s.get("title"), str):
                    errors.append(f"{p}({code}).sources[{j}]: title がありません / missing title")
    missing = sorted(codes - seen)
    if missing:
        warns.append(f"理由が未記入の銘柄 / codes without reason: {', '.join(missing)}")
    if not isinstance(reasons.get("market_summary"), str) or not reasons.get("market_summary", "").strip():
        warns.append("market_summary が空です / market_summary is empty")
    return errors, warns


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: validate_reasons.py data/reasons/YYYY-MM-DD.json", file=sys.stderr)
        return 2
    path = Path(argv[1])
    try:
        reasons = load_json(path)
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: 読み込み失敗 / cannot load {path}: {e}")
        return 1
    mpath = DATA_DIR / "movers" / f"{path.stem}.json"
    if not mpath.exists():
        print(f"ERROR: {mpath} がありません / movers file not found")
        return 1
    errors, warns = validate(reasons, load_json(mpath))
    for w in warns:
        print(f"WARN: {w}")
    for e in errors:
        print(f"ERROR: {e}")
    if errors:
        print(f"検証失敗 / validation FAILED ({len(errors)} errors)")
        return 1
    print("OK: 検証通過 / validation passed")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
