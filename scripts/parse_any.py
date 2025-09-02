#!/usr/bin/env python3
# scripts/parse_any.py
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Parsers
from scripts.rtf_to_json import parse_rtf_file        # must exist
from scripts.pca_to_json import parse_pca_file        # must exist
from scripts.xtekct_to_json import parse_xtekct_file  # NEW

# Optional XML helper (if you have one)
def parse_xml_file(p: Path) -> Dict[str, Any]:
    # lightweight generic: read as text if possible; else base64
    info: Dict[str, Any] = {
        "source_path": str(p),
        "filename": p.name,
        "extension": p.suffix.lstrip("."),
        "size_bytes": p.stat().st_size,
        "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
    }
    try:
        txt = p.read_text(encoding="utf-8")
        info["content_text"] = txt
        info["encoding"] = "utf-8"
    except Exception:
        raw = p.read_bytes()
        info["content_base64"] = base64.b64encode(raw).decode("ascii")
        info["encoding"] = "base64"
    return info

def parse_generic_file(p: Path) -> Dict[str, Any]:
    info: Dict[str, Any] = {
        "source_path": str(p),
        "filename": p.name,
        "extension": p.suffix.lstrip("."),
        "size_bytes": p.stat().st_size,
        "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
    }
    try:
        txt = p.read_text(encoding="utf-8")
        info["content_text"] = txt
        info["encoding"] = "utf-8"
    except Exception:
        raw = p.read_bytes()
        info["content_base64"] = base64.b64encode(raw).decode("ascii")
        info["encoding"] = "base64"
    return info

def decide_parser(p: Path):
    ext = p.suffix.lower().lstrip(".")
    if ext == "rtf":
        return parse_rtf_file
    if ext == "pca":
        return parse_pca_file
    if ext == "xtekct":
        return parse_xtekct_file            # NEW
    if ext == "xml":
        return parse_xml_file
    return parse_generic_file

def ensure_dirs(*dirs: Path) -> None:
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)

def main():
    ap = argparse.ArgumentParser(description="Parse ANY metadata file → JSON")
    ap.add_argument("input", help="File or directory (under data/**)")
    ap.add_argument("-o", "--outdir", default="data/parsed", help="Where to write JSON (default: data/parsed)")
    ap.add_argument("--completed-dir", default="data/completed", help="Where to move originals after success")
    ap.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    args = ap.parse_args()

    src = Path(args.input)
    outdir = Path(args.outdir)
    completed = Path(args.completed_dir)
    ensure_dirs(outdir, completed)

    files: List[Path]
    if src.is_dir():
        files = [p for p in src.rglob("*") if p.is_file()]
    else:
        files = [src]

    wrote = 0
    for p in files:
        if p.suffix.lower() == ".json":
            continue  # never parse JSON
        parser = decide_parser(p)
        try:
            record = parser(p)
            # output name: original filename + ".json" (keep original extension)
            out_path = outdir / f"{p.name}.json"
            with out_path.open("w", encoding="utf-8") as f:
                json.dump(record, f, ensure_ascii=False, indent=2 if args.pretty else None)
            wrote += 1
            # move original to completed/* (preserve subdir structure relative to data/)
            try:
                # If file path contains 'data/', keep the relative tail under completed/
                p_abs = p.resolve()
                data_root = (Path("data")).resolve()
                if str(p_abs).startswith(str(data_root)):
                    rel = p_abs.relative_to(data_root)
                    dest = (completed / rel).with_suffix(p.suffix)  # same name
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(p), str(dest))
                else:
                    # Else just drop it into completed root
                    shutil.move(str(p), str(completed / p.name))
            except Exception as e:
                # Don't fail the job just because the move failed
                print(f"[warn] failed moving original {p} → completed/: {e}")
        except Exception as e:
            print(f"[error] failed parsing {p}: {e}")

    print(f"Parsed {wrote} file(s) → {outdir}")

if __name__ == "__main__":
    main()
