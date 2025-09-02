#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

def parse_rtf(ip: Path) -> dict:
    from rtf_to_json import rtf_to_json_dict
    return rtf_to_json_dict(ip)

def parse_xml(ip: Path) -> dict:
    try:
        import xmltodict
    except Exception as e:
        raise RuntimeError("xmltodict not installed") from e
    with ip.open("rb") as f:
        return xmltodict.parse(f.read())

def generic(ip: Path) -> dict:
    from generic_wrap import file_to_envelope
    return file_to_envelope(ip)

def _dest_dir_for(ip: Path, outdir: Path) -> Path:
    """Mirror the relative folder under data/, else under repo root."""
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

def main():
    ap = argparse.ArgumentParser(description="Parse any metadata file to JSON.")
    ap.add_argument("input_path")
    ap.add_argument("--outdir", default="data/parsed")
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()

    ip = Path(args.input_path).resolve()
    if not ip.exists():
        print(f"Missing input: {ip}", file=sys.stderr)
        sys.exit(1)

    ext = ip.suffix.lower().lstrip(".")
    try:
        if ext == "rtf":
            data = parse_rtf(ip)
        elif ext == "xml":
            try:
                data = parse_xml(ip)
            except Exception:
                data = ge
