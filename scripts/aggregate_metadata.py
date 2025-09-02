#!/usr/bin/env python3
"""
aggregate_metadata.py

- Reads existing data/metadata.json if present
- Scans data/parsed/**/*.json and merges with existing records
- De-duplicates using stable keys (id/uuid/source/source_path/filename) or sha256 of canonical JSON
- Writes back to data/metadata.json
"""

import argparse
import glob
import hashlib
import json
import os
from pathlib import Path
from typing import Dict, List, Any


def canonical_hash(obj: Any) -> str:
    try:
        return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    except Exception:
        return hashlib.sha256(repr(obj).encode("utf-8")).hexdigest()


def load_json(path: Path):
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def normalize_items(blob) -> List[Dict[str, Any]]:
    if isinstance(blob, list):
        return [x if isinstance(x, dict) else {"_raw": x} for x in blob]
    elif isinstance(blob, dict):
        return [blob]
    else:
        return [{"_raw": blob}]


def key_for(item: Dict[str, Any]) -> str:
    for k in ("id", "uuid", "source", "source_path", "filename"):
        if k in item and item[k] not in (None, ""):
            return f"{k}:{item[k]}"
    return canonical_hash(item)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=str, default="data/metadata.json")
    args = ap.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing metadata (cumulative behavior)
    existing: Dict[str, Dict[str, Any]] = {}
    if out_path.exists():
        old = load_json(out_path)
        if old is not None:
            for it in normalize_items(old):
                existing[key_for(it)] = it

    # Scan new parsed JSONs
    parsed_files = glob.glob("data/parsed/**/*.json", recursive=True)
    for p in parsed_files:
        if os.path.normpath(p) == os.path.normpath(str(out_path)):
            continue
        blob = load_json(Path(p))
        if blob is None:
            continue
        for item in normalize_items(blob):
            # ensure provenance
            item.setdefault("source_path", p)
            existing[key_for(item)] = item

    # Write merged list
    merged = list(existing.values())
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    print(f"[aggregate] Wrote {len(merged)} records to {out_path}")


if __name__ == "__main__":
    main()
