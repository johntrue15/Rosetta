#!/usr/bin/env python3
"""
Aggregate & de-duplicate JSON records into a cumulative metadata.json.

- Scans JSON files under one or more roots (default: 'data').
- Skips the output file itself to avoid self-ingest.
- Loads existing OUT (if present) and upserts new/changed records.
- Dedup key priority: first present of ['id','uuid','source','source_path','filename'],
  else SHA-256 of canonicalized record.

Usage:
    python scripts/aggregate_json.py \
        [--roots data data/parsed] \
        [--out data/metadata.json]
"""

import argparse
import glob
import hashlib
import json
import os
from typing import Any, Dict, Iterable, List

DEFAULT_OUT = "data/metadata.json"
DEFAULT_ROOTS = ["data"]  # scan everything under data by default


def iter_json_files(roots: Iterable[str], out_path: str) -> Iterable[str]:
    out_abs = os.path.abspath(out_path) if out_path else ""
    for root in roots:
        for path in glob.glob(os.path.join(root, "**", "*.json"), recursive=True):
            if out_abs and os.path.abspath(path) == out_abs:
                continue  # skip the output file itself
            yield path


def load_json_safely(path: str) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def records_from_data(data: Any, source_path: str) -> List[Dict[str, Any]]:
    if data is None:
        return []
    if isinstance(data, list):
        items = data
    else:
        items = [data]
    out = []
    for item in items:
        if not isinstance(item, dict):
            item = {"_raw": item}
        # Preserve where this came from
        item.setdefault("source_path", source_path)
        out.append(item)
    return out


def dedupe_key(item: Dict[str, Any]) -> str:
    for k in ("id", "uuid", "source", "source_path", "filename"):
        v = item.get(k)
        if v is not None:
            return f"{k}:{v}"
    # canonical hash fallback
    payload = json.dumps(item, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--roots",
        nargs="*",
        default=DEFAULT_ROOTS,
        help="Root folders to scan recursively for JSON files (default: data)",
    )
    parser.add_argument(
        "--out",
        default=DEFAULT_OUT,
        help=f"Output metadata JSON path (default: {DEFAULT_OUT})",
    )
    args = parser.parse_args()

    out = (args.out or "").strip()
    if not out:
        out = DEFAULT_OUT

    # Ensure parent directory exists if there is one
    out_dir = os.path.dirname(out)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    # Start with existing metadata if present
    existing: Dict[str, Dict[str, Any]] = {}
    if os.path.exists(out):
        prev = load_json_safely(out)
        if isinstance(prev, list):
            for item in prev:
                if isinstance(item, dict):
                    existing[dedupe_key(item)] = item

    # Collect new/changed records
    merged = dict(existing)  # copy
    for path in iter_json_files(args.roots, out):
        data = load_json_safely(path)
        for rec in records_from_data(data, source_path=path):
            merged[dedupe_key(rec)] = rec  # upsert

    # Write back
    with open(out, "w", encoding="utf-8") as f:
        json.dump(list(merged.values()), f, ensure_ascii=False, indent=2)

    print(f"Wrote {len(merged)} records to {out}")


if __name__ == "__main__":
    main()
