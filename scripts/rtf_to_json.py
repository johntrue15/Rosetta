#!/usr/bin/env python3
"""
rtf_to_json.py

- Converts RTF → plain text
- Extracts simple "Key: Value" pairs where possible
- Writes a single JSON object with:
  - basic file metadata
  - content_text (plain)
  - parsed_fields (best-effort dict of key/value lines)

CLI:
  python scripts/rtf_to_json.py <input.rtf> <output.json> [--pretty]
"""

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict

from striprtf.striprtf import rtf_to_text


def extract_kv_lines(text: str) -> Dict[str, str]:
    fields = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        # Allow keys like "Gain map 0", "# Projections"
        m = re.match(r"^\s*([A-Za-z0-9# /()\-\[\]_.]+)\s*:\s*(.+?)\s*$", line)
        if m:
            k, v = m.group(1).strip(), m.group(2).strip()
            fields[k] = v
    return fields


def parse_rtf_file(input_path: Path, output_path: Path, pretty: bool = False) -> None:
    raw = input_path.read_text(encoding="utf-8", errors="ignore")
    text = rtf_to_text(raw)

    obj = {
        "source_path": str(input_path),
        "filename": input_path.name,
        "extension": input_path.suffix.lstrip("."),
        "size_bytes": input_path.stat().st_size,
        "sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
        "content_text": text,
        "parsed_fields": extract_kv_lines(text),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2 if pretty else None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=str)
    ap.add_argument("output", type=str)
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()
    parse_rtf_file(Path(args.input), Path(args.output), pretty=args.pretty)


if __name__ == "__main__":
    main()
