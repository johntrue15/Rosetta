#!/usr/bin/env python3
"""
parse_any.py

Dispatcher that:
- Chooses the correct parser based on file extension (.rtf, .pca, .xtekct)
- Writes parsed JSON to <output_dir>/<original-filename>.<ext>.json
- Moves successfully parsed originals to a completed directory
- Provides a generic fallback for unknown types (text or base64)

Usage:
  python scripts/parse_any.py <input-file> -o data/parsed --completed-dir data/completed --pretty
"""

import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Optional

# --- import guard so 'from scripts.*' works when run as a script (.py) ---
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
# ------------------------------------------------------------------------

from scripts.rtf_to_json import parse_rtf_file
from scripts.pca_to_json import parse_pca_file
from scripts.xtekct_to_json import parse_xtekct_file


def generic_to_json(input_path: Path, output_path: Path, pretty: bool = False) -> None:
    """Fallback: store text if decodable, else base64; include basic metadata."""
    import base64
    obj = {
        "source_path": str(input_path),
        "filename": input_path.name,
        "extension": input_path.suffix.lstrip("."),
        "size_bytes": input_path.stat().st_size,
        "sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
    }
    try:
        txt = input_path.read_text(encoding="utf-8")
        obj["content_text"] = txt
        obj["encoding"] = "utf-8"
    except Exception:
        raw = input_path.read_bytes()
        obj["content_base64"] = base64.b64encode(raw).decode("ascii")
        obj["encoding"] = "base64"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2 if pretty else None)


def compute_output_path(out_dir: Path, input_path: Path) -> Path:
    """
    Output file name is the original file name with '.json' appended.
    e.g., 'Technique.rtf' -> 'Technique.rtf.json'
    """
    return out_dir / f"{input_path.name}.json"


def move_to_completed(input_path: Path, completed_dir: Path) -> Optional[Path]:
    """
    Move input file to completed_dir, preserving the relative path under 'data/'
    if present; otherwise, place directly under completed_dir.
    """
    completed_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Try to preserve relative tree under 'data/' root if exists
        parts = input_path.resolve().parts
        if "data" in parts:
            idx = parts.index("data")
            rel = Path(*parts[idx + 1 :])  # path under data/
            dest = completed_dir / rel
        else:
            dest = completed_dir / input_path.name

        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(input_path), str(dest))
        return dest
    except Exception:
        # Best-effort fallback
        dest = completed_dir / input_path.name
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(input_path), str(dest))
            return dest
        except Exception:
            return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=str, help="Path to a single source file")
    ap.add_argument("-o", "--output-dir", type=str, default="data/parsed", help="Directory for parsed JSON")
    ap.add_argument("--completed-dir", type=str, default="data/completed", help="Directory to move parsed originals")
    ap.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    args = ap.parse_args()

    input_path = Path(args.input)
    if not input_path.exists() or not input_path.is_file():
        print(f"[parse_any] Input file not found or not a file: {input_path}", file=sys.stderr)
        sys.exit(1)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = compute_output_path(out_dir, input_path)

    ext = input_path.suffix.lower()
    try:
        if ext == ".rtf":
            parse_rtf_file(input_path, output_path, pretty=args.pretty)
        elif ext == ".pca":
            parse_pca_file(input_path, output_path, pretty=args.pretty)
        elif ext == ".xtekct":
            parse_xtekct_file(input_path, output_path, pretty=args.pretty)
        else:
            print(f"[parse_any] Unknown extension '{ext}', using generic fallback.")
            generic_to_json(input_path, output_path, pretty=args.pretty)
    except Exception as e:
        print(f"[parse_any] Parse failed for {input_path}: {e}", file=sys.stderr)
        sys.exit(2)

    # Move original into completed directory (best effort)
    moved = move_to_completed(input_path, Path(args.completed_dir))
    if moved is None:
        print(f"[parse_any] Warning: could not move {input_path} to {args.completed_dir}", file=sys.stderr)


if __name__ == "__main__":
    main()
