#!/usr/bin/env python3
from __future__ import annotations
import base64, hashlib, json, os, sys
from pathlib import Path
from typing import Dict, Any

def file_to_envelope(path: Path) -> Dict[str, Any]:
    raw = path.read_bytes()
    info = {
        "source_path": str(path),
        "filename": path.name,
        "extension": path.suffix.lstrip("."),
        "size_bytes": path.stat().st_size,
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    try:
        txt = raw.decode("utf-8")
    except UnicodeDecodeError:
        info["encoding"] = "base64"
        info["content_base64"] = base64.b64encode(raw).decode("ascii")
    else:
        info["encoding"] = "utf-8"
        info["content_text"] = txt
    return info

def main():
    if len(sys.argv) < 3:
        print("Usage: generic_wrap.py <input_path> <output_json>", file=sys.stderr)
        sys.exit(2)
    ip = Path(sys.argv[1]).resolve()
    op = Path(sys.argv[2]).resolve()
    op.parent.mkdir(parents=True, exist_ok=True)
    json.dump(file_to_envelope(ip), op.open("w", encoding="utf-8"), ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
