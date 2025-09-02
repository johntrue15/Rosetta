#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Dict, Any, Optional

try:
    from striprtf.striprtf import rtf_to_text
except Exception as e:  # pragma: no cover
    raise SystemExit(
        "Missing dependency 'striprtf'. Install with: pip install striprtf\n"
        f"Import error: {e}"
    )

# Known section headers to nest as sub-dicts
SECTION_HEADERS = {
    "Xray Source",
    "Detector",
    "Distances",
    "Geometric Unsharpness Custom Formula",
    "Motion Positions",
    "Setup",
    "CT Scan",
}

# "Key:|Value|" or "Key: Value" or "Key:|Value"
KV_RE = re.compile(r"^\s*([^:]+?):\s*\|?(.*?)\|?\s*$")
# "Section:||" or "Section:"
SECTION_RE = re.compile(r"^\s*([A-Za-z0-9 \-\(\)\/]+?):\s*(\|\|?)?\s*$")


def normalize_text(text: str) -> str:
    """Normalize line endings and trim trailing spaces per line."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip() for line in text.split("\n"))


class PushbackIterator:
    """Iterator over lines with a single-item pushback buffer."""
    __slots__ = ("_it", "_buf")

    def __init__(self, lines):
        self._it = iter(lines)
        self._buf = None

    def __iter__(self):
        return self

    def __next__(self):
        if self._buf is not None:
            v = self._buf
            self._buf = None
            return v
        return next(self._it)

    def pushback(self, line):
        self._buf = line


def parse_gucf(lines_iter) -> Dict[str, Any]:
    """
    Parse the 'Geometric Unsharpness Custom Formula' section.
    Groups Name/Expression/Value as:
      { "<Name>": {"Expression": "...", "Value": "..."}, ... }
    """
    out: Dict[str, Any] = {}
    current_name: Optional[str] = None

    for line in lines_iter:
        if not line or line == "||":
            continue

        # Next section? stop and push line back
        if SECTION_RE.match(line):
            lines_iter.pushback(line)
            break

        mkv = KV_RE.match(line)
        if not mkv:
            continue

        key, val = mkv.group(1).strip(), mkv.group(2).strip()

        if key.lower() == "name":
            current_name = val
            out.setdefault(current_name, {})
        elif key.lower() in ("expression", "value"):
            if current_name is None:
                out.setdefault("_misc", {}).setdefault(key, []).append(val)
            else:
                out[current_name][key] = val
        else:
            if current_name is None:
                out.setdefault("_misc", {})[key] = val
            else:
                out[current_name][key] = val

    return out


def parse_sections(plain_text: str) -> Dict[str, Any]:
    """
    Parse normalized plain text into structured JSON:
    - Top-level KVs → root
    - Known section headers → nested dicts
    - GUCF gets grouped via parse_gucf
    """
    data: Dict[str, Any] = {}
    current_section: Optional[str] = None

    lines = PushbackIterator(plain_text.split("\n"))

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line == "||":
            continue

        # Section header?
        msec = SECTION_RE.match(line)
        if msec:
            sec = msec.group(1).strip()
            if sec in SECTION_HEADERS:
                current_section = sec
                if sec == "Geometric Unsharpness Custom Formula":
                    data[sec] = parse_gucf(lines)
                    current_section = None
                else:
                    data.setdefault(sec, {})
                continue
            # fall through if unknown

        # Regular key/value
        mkv = KV_RE.match(line)
        if mkv:
            key = mkv.group(1).strip()
            val = mkv.group(2).strip()
            if current_section is None:
                data[key] = val
            else:
                data[current_section][key] = val
            continue

        # Non-matching lines are ignored gracefully

    return data


def rtf_to_json_dict(path: Path) -> Dict[str, Any]:
    """Convert an RTF file to a structured JSON dict."""
    raw = path.read_text(encoding="utf-8", errors="ignore")
    text = rtf_to_text(raw)
    text = normalize_text(text)
    return parse_sections(text)


def main():
    ap = argparse.ArgumentParser(description="Convert an RTF technique sheet to JSON.")
    ap.add_argument("input", help="Path to input .rtf file")
    ap.add_argument(
        "-o", "--output",
        help="Path to output .json file (default: <input basename>.json)"
    )
    ap.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    args = ap.parse_args()

    in_path = Path(args.input).expanduser().resolve()
    if not in_path.exists():
        raise SystemExit(f"Input not found: {in_path}")

    data = rtf_to_json_dict(in_path)
    out_path = Path(args.output).expanduser().resolve() if args.output else in_path.with_suffix(".json")

    js = json.dumps(data, indent=2 if args.pretty else None, ensure_ascii=False)
    out_path.write_text(js, encoding="utf-8")
    # Print path so CI can capture/parse easily
    print(str(out_path))


if __name__ == "__main__":
    main()
