#!/usr/bin/env python3
"""
rtf_to_json.py
"""

import argparse
import json
from pathlib import Path
from striprtf.striprtf import rtf_to_text
import re


def _parse_text_to_dict(plain_text: str) -> dict:
    # Use the regex map you already validated in your notebook.
    # (Shortened here for clarity — keep your full patterns.)
    sections = {
        'Machine ID': r"Machine ID:\s*(.+)",
        'Machine Serial': r"Machine Serial:\s*(.+)",
        'Operator ID': r"Operator ID:\s*(.+)",
        'Date/Time': r"Date/Time:\s*(.+)",
        'Xray Source': {
            'Name': r"Name:\s*(.+)",
            'Voltage': r"Voltage:\s*(.+)",
            'Current': r"Current:\s*(.+)",
            'Focal spot size': r"Focal spot size:\s*(.+)",
        },
        # ... keep the rest of your patterns here ...
    }

    parsed = {}
    for key, pattern in sections.items():
        if isinstance(pattern, dict):
            parsed[key] = {}
            for sub_key, sub_pat in pattern.items():
                m = re.search(sub_pat, plain_text, re.MULTILINE | re.DOTALL)
                if m:
                    parsed[key][sub_key] = m.group(1).strip()
        else:
            m = re.search(pattern, plain_text, re.MULTILINE | re.DOTALL)
            if m:
                parsed[key] = m.group(1).strip()
    return parsed


def parse_rtf_file(input_path: Path, output_path: Path, pretty: bool = False) -> None:
    txt = input_path.read_text(encoding="utf-8", errors="ignore")
    plain = rtf_to_text(txt)
    data = _parse_text_to_dict(plain)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2 if pretty else None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=str)
    ap.add_argument("output", type=str)
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()
    parse_rtf_file(Path(args.input), Path(args.output), pretty=args.pretty)


if __name__ == "__main__":
    main()
