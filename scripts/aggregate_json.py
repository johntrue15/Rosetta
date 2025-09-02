#!/usr/bin/env python3
"""
aggregate_json.py

Collects all JSON files under data/parsed/** (single-record JSONs or arrays)
and writes/updates a cumulative data/metadata.json without losing prior entries.
De-duplicates by a stable key (id/uuid/source_path/filename/sha256) or by content hash.
"""

from __future__ import annotations
import json, glob, hashlib, os, sys
from typing import Dict, Any, Iterable


def _iter_records() -> Iterable[Dict[str, Any]]:
    for path in glob.glob('data/parsed/**/*.json', recursive=True):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if not isinstance(item, dict):
                item = {"_raw": data, "source_path": path}
            if "source_path" not in item:
                item["source_path"] = path
            yield item


def _load_existing(out_path: str) -> Dict[str, Dict[str, Any]]:
    if not os.path.exists(out_path):
        return {}
    try:
        with open(out_path, 'r', encoding='utf-8') as f:
            arr = json.load(f)
    except Exception:
        return {}
    if not isinstance(arr, list):
        return {}
    records: Dict[str, Dict[str, Any]] = {}
    for item in arr:
        if not isinstance(item, dict):
            continue
        key = _make_key(item)
        records[key] = item
    return records


def _make_key(item: Dict[str, Any]) -> str:
    for k in ('id','uuid','source','source_path','filename','sha256'):
        if k in item and item[k]:
            return f"{k}:{item[k]}"
    # fallback to content hash
    return hashlib.sha256(json.dumps(item, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else 'data/metadata.json'
    records: Dict[str, Dict[str, Any]] = _load_existing(out)

    for item in _iter_records():
        key = _make_key(item)
        records[key] = item

    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(list(records.values()), f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
