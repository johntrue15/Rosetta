#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os, sys, hashlib
from pathlib import Path

def safe_stem(rel_path: str) -> str:
    """Make a unique stem using basename + short hash of relative path."""
    base = os.path.basename(rel_path)
    stem, _ = os.path.splitext(base)
    h = hashlib.sha1(rel_path.encode("utf-8")).hexdigest()[:8]
    return f"{stem}-{h}"

def parse_rtf(ip: Path) -> dict:
    from rtf_to_json import rtf_to_json_dict  # local file import
    return rtf_to_json_dict(ip)

def parse_xml(ip: Path) -> dict:
    try:
        import xmltodict
    except Exception:
        raise RuntimeError("xmltodict not installed")
    with ip.open("rb") as f:
        data = xmltodict.parse(f.read())
    return data  # dict-like

def generic(ip: Path) -> dict:
    from generic_wrap import file_to_envelope
    return file_to_envelope(ip)

def main():
    ap = argparse.ArgumentParser(description="Parse any metadata file to JSON.")
    ap.add_argument("input_path")
    ap.add_argument("--outdir", default="data/parsed")
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()

    ip = Path(args.input_path).resolve()
    if not ip.exists():
        print(f"Missing input: {ip}", file=sys.stderr); sys.exit(1)

    ext = ip.suffix.lower().lstrip(".")
    rel = os.path.relpath(str(ip), start=os.getcwd())
    outdir = Path(args.outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    op = outdir / f"{safe_stem(rel)}.json"

    try:
        if ext == "rtf":
            data = parse_rtf(ip)
        elif ext == "xml":
            try:
                data = parse_xml(ip)
            except Exception:
                data = generic(ip)
        elif ext == "pca":
            # If you later add a real PCA parser, swap it in here.
            data = generic(ip)
        else:
            data = generic(ip)
    except Exception as e:
        # Absolute last resort: generic envelope with error note
        data = generic(ip)
        data["_parse_error"] = str(e)

    js = json.dumps(data, ensure_ascii=False, indent=2 if args.pretty else None)
    op.write_text(js, encoding="utf-8")
    print(op)

if __name__ == "__main__":
    main()
