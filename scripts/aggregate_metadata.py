#!/usr/bin/env python3
from __future__ import annotations
import glob, json, hashlib, os
from pathlib import Path
from typing import Dict, Any, Iterable

OUT = Path("data/metadata.json")

def iter_items() -> Iterable[Dict[str, Any]]:
    for path in glob.glob("data/**/*.json", recursive=True):
        if os.path.normpath(path) == os.path.normpath(str(OUT)):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            yield item if isinstance(item, dict) else {"_raw": data, "source_path": path}

def main():
    records: Dict[str, Dict[str, Any]] = {}
    for item in iter_items():
        key = None
        for k in ("id", "uuid", "source", "source_path", "filename"):
            if k in item and item[k]:
                key = f"{k}:{item[k]}"; break
        if key is None:
            key = hashlib.sha256(json.dumps(item, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
        records[key] = item

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        json.dump(list(records.values()), f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
