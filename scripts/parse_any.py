#!/usr/bin/env python3
# scripts/parse_any.py
from __future__ import annotations

import argparse
import base64
import json
import hashlib
import sys
from pathlib import Path
from typing import Dict, Any, Iterable, List, Optional

# --------------------------- helpers ---------------------------

def _is_text(path: Path) -> bool:
    """
    Very light heuristic: try UTF-8, else Latin-1.
    If both fail, treat as binary.
    """
    try:
        path.read_text(encoding="utf-8")
        return True
    except UnicodeDecodeError:
        try:
            path.read_text(encoding="latin-1")
            return True
        except Exception:
            return False
    except Exception:
        return False


def _read_text_best_effort(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")


def file_to_envelope(path: Path) -> Dict[str, Any]:
    """
    Generic wrapper for any file type:
    - Always includes metadata (size, sha256, extension, paths).
    - If text-ish: include content_text; else base64.
    """
    meta: Dict[str, Any] = {
        "source_path": str(path),
        "filename": path.name,
        "extension": path.suffix.lstrip("."),
        "size_bytes": path.stat().st_size if path.exists() else None,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None,
    }
    if _is_text(path):
        meta["content_text"] = _read_text_best_effort(path)
        meta["encoding"] = "utf-8-or-latin1"
    else:
        meta["content_base64"] = base64.b64encode(path.read_bytes()).decode("ascii")
        meta["encoding"] = "base64"
    return meta


def _dest_dir_for(ip: Path, outdir: Path) -> Path:
    """
    Mirror the relative folder under data/, else under repo root,
    else flatten into outdir.
    """
    cwd = Path.cwd().resolve()
    data_root = (cwd / "data").resolve()
    try:
        rel_parent = ip.parent.resolve().relative_to(data_root)
        return (outdir / rel_parent).resolve()
    except Exception:
        try:
            rel_parent = ip.parent.resolve().relative_to(cwd)
            return (outdir / rel_parent).resolve()
        except Exception:
            return outdir.resolve()


# --------------------------- specific parsers ---------------------------

def parse_rtf(ip: Path) -> Dict[str, Any]:
    """
    Preferred: local scripts/rtf_to_json.py exposes rtf_to_json_dict
    Fallback: striprtf -> text, then generic envelope with content_text
    """
    # Try our dedicated converter first
    try:
        from rtf_to_json import rtf_to_json_dict  # local module in scripts/
        return rtf_to_json_dict(ip)
    except Exception as e:
        # Fallback path: just extract text (if library available) and wrap
        try:
            from striprtf.striprtf import rtf_to_text
            text = rtf_to_text(ip.read_text(encoding="utf-8", errors="ignore"))
            env = file_to_envelope(ip)
            env["content_text"] = text
            env["encoding"] = "utf-8"
            env["_parse_note"] = f"Fallback via striprtf (rtf_to_json module unavailable or failed: {e})"
            return env
        except Exception:
            env = file_to_envelope(ip)
            env["_parse_error"] = f"RTF parse failed and striprtf not available: {e}"
            return env


def parse_xml(ip: Path) -> Dict[str, Any]:
    try:
        import xmltodict  # optional dep; installed in workflow by default
        with ip.open("rb") as f:
            return xmltodict.parse(f.read())
    except Exception as e:
        env = file_to_envelope(ip)
        env["_parse_error"] = f"XML parse failed: {e}"
        return env


def parse_pca(ip: Path) -> Dict[str, Any]:
    """
    Preferred: local scripts/pca_to_json.py exposes parse_pca_file
    Fallback: generic envelope
    """
    try:
        from pca_to_json import parse_pca_file  # local module in scripts/
        return parse_pca_file(ip)
    except Exception as e:
        env = file_to_envelope(ip)
        env["_parse_error"] = f"PCA parse failed or parser unavailable: {e}"
        return env


# --------------------------- dispatcher ---------------------------

SUPPORTED_EXTS = {"rtf", "xml", "pca"}

def parse_one_file(ip: Path) -> Dict[str, Any]:
    ext = ip.suffix.lower().lstrip(".")
    if ext == "rtf":
        return parse_rtf(ip)
    if ext == "xml":
        return parse_xml(ip)
    if ext == "pca":
        return parse_pca(ip)
    # Anything else → generic
    return file_to_envelope(ip)


def iter_files(root: Path, allow_all: bool = False) -> Iterable[Path]:
    """
    Yield files:
      - If root is a file: yield it.
      - If root is a dir: recurse. If allow_all=False, only known types.
    """
    if root.is_file():
        yield root
        return
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if allow_all:
            yield p
        else:
            ext = p.suffix.lower().lstrip(".")
            if ext in SUPPORTED_EXTS:
                yield p


# --------------------------- cli ---------------------------

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Parse metadata files to JSON (RTF, XML, PCA, or generic fallback)."
    )
    ap.add_argument("input_path", help="File or directory to parse")
    ap.add_argument(
        "--outdir",
        default="data/parsed",
        help="Directory to write outputs (default: data/parsed)"
    )
    ap.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output"
    )
    ap.add_argument(
        "--all",
        action="store_true",
        help="In directory mode, parse all files (not just known types)"
    )
    args = ap.parse_args()

    ip = Path(args.input_path).resolve()
    outdir = Path(args.outdir).resolve()
    if not ip.exists():
        print(f"Missing input: {ip}", file=sys.stderr)
        sys.exit(1)

    # Directory: iterate multiple inputs. File: single path.
    targets: List[Path] = list(iter_files(ip, allow_all=args.all))

    if not targets:
        print("No files found to parse.", file=sys.stderr)
        sys.exit(0)

    wrote_any = False
    for f in targets:
        try:
            data = parse_one_file(f)
        except Exception as e:
            data = file_to_envelope(f)
            data["_parse_error"] = f"Unhandled exception: {e}"

        dest_dir = _dest_dir_for(f, outdir)
        dest_dir.mkdir(parents=True, exist_ok=True)

        # Append .json to the original filename (keep original extension)
        out_path = dest_dir / f"{f.name}.json"

        js = json.dumps(data, ensure_ascii=False, indent=2 if args.pretty else None)
        out_path.write_text(js, encoding="utf-8")
        print(out_path)
        wrote_any = True

    if not wrote_any:
        sys.exit(1)


if __name__ == "__main__":
    main()
