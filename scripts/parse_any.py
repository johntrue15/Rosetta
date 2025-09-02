#!/usr/bin/env python3
"""
parse_any.py

Dispatch parser for metadata files. Chooses the correct specialized parser
based on extension and ensures the original file is MOVED to --completed-dir
after a successful parse.

Usage:
  python scripts/parse_any.py <input_path> -o <out_dir> [--completed-dir <dir>] [--pretty]
"""

from __future__ import annotations
import argparse
import sys
import shutil
from pathlib import Path

# Local imports (scripts live alongside this file)
from rtf_to_json import parse_rtf_file
from pca_to_json import parse_pca_file
from xtekct_to_json import parse_xtekct_file


def decide_output_path(out_dir: Path, source: Path) -> Path:
    """
    Output filename = original filename with .json appended:
      e.g., "myfile.rtf" -> "myfile.rtf.json"
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / f"{source.name}.json"


def move_to_completed(source: Path, completed_dir: Path) -> Path:
    """
    Move the original file into completed_dir with its same basename.
    If a file with the same name already exists, append a numeric suffix.
    Returns the destination path.
    """
    completed_dir.mkdir(parents=True, exist_ok=True)
    dest = completed_dir / source.name
    if dest.exists():
        stem = source.stem
        suf = source.suffix
        i = 1
        while True:
            candidate = completed_dir / f"{stem}__moved_{i}{suf}"
            if not candidate.exists():
                dest = candidate
                break
            i += 1
    # shutil.move works across filesystems; os.replace would not.
    shutil.move(str(source), str(dest))
    return dest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=str, help="Path to a single file to parse")
    ap.add_argument("-o", "--out-dir", required=True, type=str, help="Directory to write parsed JSON")
    ap.add_argument("--completed-dir", type=str, default="data/completed", help="Where to move originals after parse")
    ap.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    args = ap.parse_args()

    src = Path(args.input)
    out_dir = Path(args.out_dir)
    completed_dir = Path(args.completed_dir)
    pretty = args.pretty

    if not src.exists() or not src.is_file():
        print(f"[parse_any] Not a file or missing: {src}", file=sys.stderr)
        sys.exit(1)

    out_path = decide_output_path(out_dir, src)
    ext = src.suffix.lower()

    # Parse by extension
    if ext == ".rtf":
        parse_rtf_file(src, out_path, pretty=pretty)
    elif ext == ".pca":
        parse_pca_file(src, out_path, pretty=pretty)
    elif ext == ".xtekct":
        parse_xtekct_file(src, out_path, pretty=pretty)
    else:
        print(f"[parse_any] Unsupported file extension: {ext} ({src})", file=sys.stderr)
        sys.exit(2)

    # If we get here, parse succeeded -> move source to completed
    try:
        moved = move_to_completed(src, completed_dir)
        print(f"[parse_any] Moved original to: {moved}")
    except Exception as e:
        # Fail the job if we couldn't move — you asked to delete originals once parsed
        print(f"[parse_any] ERROR moving original to completed: {e}", file=sys.stderr)
        sys.exit(3)


if __name__ == "__main__":
    main()
