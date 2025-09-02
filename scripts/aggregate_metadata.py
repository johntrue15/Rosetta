#!/usr/bin/env python3
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List

# ---- Keying logic for de-duplication ---------------------------------
PRIORITY_KEYS = ("id", "uuid", "source", "source_path", "filename")

def record_key(item: Dict[str, Any]) -> str:
    """
    Compute a stable key for a record to prevent duplicates across runs.
    Prefer semantic identifiers; otherwise hash the canonical JSON.
    """
    for k in PRIORITY_KEYS:
        v = item.get(k)
        if v not in (None, ""):
            return f"{k}:{v}"
    # canonical hash fallback
    blob = json.dumps(item, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()

# ---- Loading helpers ---------------------------------------------------

def load_existing(out_path: Path) -> List[Dict[str, Any]]:
    if not out_path.exists():
        return []
    try:
        with out_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        # If somehow it's a dict, wrap it
        return [data]
    except Exception:
        return []

def iter_parsed_json(parsed_dir: Path) -> Iterable[Path]:
    # Consider only files written by the parser, not metadata.json
    for p in parsed_dir.rglob("*.json"):
        if p.name == "metadata.json":
            continue
        yield p

def load_items_from_file(path: Path) -> List[Dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []
    if isinstance(data, list):
        # Ensure dicts only
        return [x if isinstance(x, dict) else {"_raw": x, "source_path": str(path)} for x in data]
    if isinstance(data, dict):
        return [data]
    return [{"_raw": data, "source_path": str(path)}]

# ---- Main --------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Append new parsed items into a cumulative metadata.json")
    ap.add_argument("--parsed-dir", default="data/parsed", help="Directory containing parsed JSON files")
    ap.add_argument("--out", default="data/metadata.json", help="Cumulative JSON output file")
    args = ap.parse_args()

    parsed_dir = Path(args.parsed_dir).resolve()
    out_path = Path(args.out).resolve()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    parsed_dir.mkdir(parents=True, exist_ok=True)

    # Load existing cumulative records
    cumulative: List[Dict[str, Any]] = load_existing(out_path)
    seen = {record_key(x) for x in cumulative}

    # Append new items from parsed files
    new_count = 0
    for jf in iter_parsed_json(parsed_dir):
        items = load_items_from_file(jf)
        for it in items:
            k = record_key(it)
            if k in seen:
                continue
            cumulative.append(it)
            seen.add(k)
            new_count += 1

    # Write back the cumulative JSON (append semantics via merge)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(cumulative, f, ensure_ascii=False, indent=2)

    print(f"Appended {new_count} new record(s) into {out_path}")

if __name__ == "__main__":
    main()
