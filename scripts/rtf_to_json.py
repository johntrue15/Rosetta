#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re
from pathlib import Path
from typing import Dict, Any, Optional
from striprtf.striprtf import rtf_to_text

SECTION_HEADERS = {
    "Xray Source","Detector","Distances",
    "Geometric Unsharpness Custom Formula",
    "Motion Positions","Setup","CT Scan",
}

KV_RE = re.compile(r"^\s*([^:]+?):\s*\|?(.*?)\|?\s*$")
SECTION_RE = re.compile(r"^\s*([A-Za-z0-9 \-\(\)\/]+?):\s*(\|\|?)?\s*$")

def _normalize(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip() for line in text.split("\n"))

class _PBIter:
    __slots__ = ("_it","_buf")
    def __init__(self, lines): self._it, self._buf = iter(lines), None
    def __iter__(self): return self
    def __next__(self):
        if self._buf is not None:
            v = self._buf; self._buf = None; return v
        return next(self._it)
    def push(self, v): self._buf = v

def _parse_gucf(lines) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    current = None
    for line in lines:
        if not line or line == "||": continue
        if SECTION_RE.match(line):
            lines.push(line); break
        m = KV_RE.match(line)
        if not m: continue
        k, v = m.group(1).strip(), m.group(2).strip()
        if k.lower() == "name":
            current = v; out.setdefault(current, {})
        elif k.lower() in ("expression","value"):
            out.setdefault(current or "_misc", {})[k] = v
        else:
            out.setdefault(current or "_misc", {})[k] = v
    return out

def _parse_sections(text: str) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    current: Optional[str] = None
    lines = _PBIter(text.split("\n"))
    for raw in lines:
        line = raw.strip()
        if not line or line == "||": continue
        ms = SECTION_RE.match(line)
        if ms:
            sec = ms.group(1).strip()
            if sec in SECTION_HEADERS:
                current = sec
                if sec == "Geometric Unsharpness Custom Formula":
                    data[sec] = _parse_gucf(lines); current = None
                else:
                    data.setdefault(sec, {})
                continue
        m = KV_RE.match(line)
        if m:
            k, v = m.group(1).strip(), m.group(2).strip()
            (data if current is None else data.setdefault(current, {}))[k] = v
    return data

def rtf_to_json_dict(path: Path) -> Dict[str, Any]:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    text = _normalize(rtf_to_text(raw))
    return _parse_sections(text)

def main():
    ap = argparse.ArgumentParser(description="Convert an RTF technique sheet to JSON.")
    ap.add_argument("input")
    ap.add_argument("-o","--output", help="Output JSON path (defaults to <input>.json appended).")
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()

    ip = Path(args.input).resolve()
    if not ip.exists():
        raise SystemExit(f"Input not found: {ip}")

    data = rtf_to_json_dict(ip)

    # APPEND .json to the *full* filename (keeps original extension)
    if args.output:
        op = Path(args.output).resolve()
    else:
        op = Path(str(ip) + ".json")

    js = json.dumps(data, indent=2 if args.pretty else None, ensure_ascii=False)
    op.parent.mkdir(parents=True, exist_ok=True)
    op.write_text(js, encoding="utf-8")
    print(op)

if __name__ == "__main__":
    main()
