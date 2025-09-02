#!/usr/bin/env python3
"""
rtf_to_json.py

Parses X-ray/CT RTF logs that use "|"-delimited fields:

- Section headers look like:   Section Name:||
- Key/value lines look like:   Key:|Value|

We convert to a normalized record compatible with the rest of the pipeline
and also return a 'sections' dict with all parsed fields preserved.
"""

import argparse
import hashlib
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Tuple, Optional

try:
    from striprtf.striprtf import rtf_to_text
except Exception:
    rtf_to_text = None

COLUMN_ORDER = [
    'file_name', 'file_hyperlink', 'ct_voxel_size_um', 'ct_objective',
    'ct_number_images', 'Geometric_magnificiation', 'Source_detector_distance',
    'Source_sample_distance', 'ct_optical_magnification', 'xray_tube_ID',
    'xray_tube_voltage', 'xray_tube_power', 'xray_tube_current', 'xray_filter',
    'detector_binning', 'detector_capture_time', 'detector_averaging',
    'detector_skip', 'image_width_pixels', 'image_height_pixels',
    'image_width_real', 'image_height_real', 'scan_time', 'start_time',
    'end_time', 'txrm_file_path', 'file_path', 'acquisition_successful',
    'sample_x_start', 'sample_x_end', 'sample_x_range', 'sample_y_start',
    'sample_y_end', 'sample_y_range', 'sample_z_start', 'sample_z_end',
    'sample_z_range', 'sample_theta_start'
]

SECTION_ALIASES = {
    "xray source": "Xray Source",
    "x-ray source": "Xray Source",
    "detector": "Detector",
    "distances": "Distances",
    "setup": "Setup",
    "ct scan": "CT Scan",
    "geometric unsharpness custom formula": "Geometric Unsharpness Custom Formula",
    "motion positions": "Motion Positions",
}

KV_LINE = re.compile(r'^\s*([^:|]+):\|(.*?)\|\s*$')
SEC_LINE = re.compile(r'^\s*([^:|]+):\|\|\s*$')

NUM_F = re.compile(r'[-+]?\d*\.?\d+')
ROI_RE = re.compile(r'^\s*(\d+)\s*x\s*(\d+)', re.IGNORECASE)

def clean_key(s: str) -> str:
    return re.sub(r'\s+', ' ', s.strip())

def clean_val(s: str) -> str:
    return s.strip()

def first_float(s: str) -> Optional[float]:
    if not isinstance(s, str):
        return None
    m = NUM_F.search(s.replace('µ', 'u'))
    if not m:
        return None
    try:
        return float(m.group(0))
    except Exception:
        return None

def parse_roi(s: str) -> Tuple[Optional[int], Optional[int]]:
    if not isinstance(s, str):
        return None, None
    m = ROI_RE.search(s)
    if not m:
        return None, None
    try:
        return int(m.group(1)), int(m.group(2))
    except Exception:
        return None, None

def guess_binning(s: str) -> str:
    if not isinstance(s, str) or not s.strip():
        return "N/A"
    t = s.strip().lower()
    if t in ("none", "no", "off", "n/a"):
        return "1x1"
    # common representations like "2x2", "4x4" or "2", "4"
    m = re.search(r'(\d+)\s*x\s*(\d+)', t)
    if m:
        return f"{m.group(1)}x{m.group(2)}"
    m2 = re.search(r'(\d+)', t)
    if m2:
        n = int(m2.group(1))
        return f"{n}x{n}"
    return s

def normalize_section_name(s: str) -> str:
    base = clean_key(s).lower()
    return SECTION_ALIASES.get(base, clean_key(s))

def load_text(path: Path) -> str:
    raw = path.read_bytes()
    # try rtf → text first
    if rtf_to_text is not None:
        try:
            return rtf_to_text(raw.decode("latin-1", errors="ignore"))
        except Exception:
            pass
    # fallback: assume already text
    try:
        return raw.decode("utf-8")
    except Exception:
        return raw.decode("latin-1", errors="ignore")

def tokenize(text: str) -> Dict[str, Dict[str, str]]:
    """
    Returns a dict: { section_name : { key: value, ... }, ... }
    Lines outside any section are collected under section "_root".
    """
    sections: Dict[str, Dict[str, str]] = {}
    cur_sec = "_root"
    sections[cur_sec] = {}

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        # section header?
        ms = SEC_LINE.match(line)
        if ms:
            cur_sec = normalize_section_name(ms.group(1))
            sections.setdefault(cur_sec, {})
            continue
        # key/value?
        mkv = KV_LINE.match(line)
        if mkv:
            k = clean_key(mkv.group(1))
            v = clean_val(mkv.group(2))
            # keep last value if repeated key
            sections.setdefault(cur_sec, {})
            sections[cur_sec][k] = v
            continue
        # otherwise ignore (decoration or "||")
    return sections

def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()

def build_record(src: Path, sections: Dict[str, Dict[str, str]]) -> Dict[str, Any]:
    rec: Dict[str, Any] = {k: 'N/A' for k in COLUMN_ORDER}
    rec['file_name'] = src.name
    rec['file_hyperlink'] = f"file:///{src.resolve()}".replace("\\", "/")
    rec['file_path'] = str(src.resolve())  # will try to replace from CT Scan → Project folder
    rec['start_time'] = datetime.fromtimestamp(src.stat().st_mtime).isoformat()
    rec['end_time'] = datetime.now().isoformat()
    rec['acquisition_successful'] = 'Yes'

    # --- pull sections safely ---
    root = sections.get("_root", {})
    xray = sections.get("Xray Source", {})
    det  = sections.get("Detector", {})
    dist = sections.get("Distances", {})
    setup = sections.get("Setup", {})
    ct   = sections.get("CT Scan", {})

    # Xray source
    if xray:
        if "Name" in xray:
            rec["xray_tube_ID"] = xray["Name"]
        if "Voltage" in xray:
            v_kv = first_float(xray["Voltage"])
            if v_kv is not None:
                rec["xray_tube_voltage"] = f"{v_kv:.3f}".rstrip('0').rstrip('.')
        if "Current" in xray:
            i_uA = first_float(xray["Current"])
            if i_uA is not None:
                rec["xray_tube_current"] = f"{i_uA:.3f}".rstrip('0').rstrip('.')
        # power: kV * µA * 1e-3 = W
        try:
            v = float(rec["xray_tube_voltage"])
            i = float(rec["xray_tube_current"])
            rec["xray_tube_power"] = f"{v * i * 1e-3:.3f}".rstrip('0').rstrip('.')
        except Exception:
            pass

    # Detector
    if det:
        if "Binning" in det:
            rec["detector_binning"] = guess_binning(det["Binning"])
        if "Framerate" in det:
            rec["detector_capture_time"] = det["Framerate"]  # keep as reported
        if "Gain" in det:
            rec["detector_averaging"] = det["Gain"]  # better than nothing

    # Distances and derived magnification & voxel size
    if dist:
        sdd = first_float(dist.get("Source to detector", ""))
        sod = first_float(dist.get("Source to object", ""))
        if sdd is not None:
            rec["Source_detector_distance"] = f"{sdd:.6f}".rstrip('0').rstrip('.')
        if sod is not None:
            rec["Source_sample_distance"] = f"{sod:.6f}".rstrip('0').rstrip('.')
        try:
            if sdd and sod and float(sod) != 0:
                rec["Geometric_magnificiation"] = f"{float(sdd)/float(sod):.6f}".rstrip('0').rstrip('.')
        except Exception:
            pass
        # Effective pixel pitch → voxel size (mm → µm)
        eff_pp_mm = first_float(dist.get("Effective pixel pitch", ""))
        if eff_pp_mm is not None:
            rec["ct_voxel_size_um"] = f"{eff_pp_mm*1000.0:.6f}".rstrip('0').rstrip('.')

        # Optional zoom factor
        z = dist.get("Zoom factor", "")
        zf = first_float(z)
        if not rec.get("Geometric_magnificiation") and zf is not None:
            rec["Geometric_magnificiation"] = f"{zf:.6f}".rstrip('0').rstrip('.')

    # Setup → filter (verbatim)
    if setup:
        if "Filter" in setup:
            rec["xray_filter"] = setup["Filter"]

    # CT Scan
    if ct:
        if "# Projections" in ct:
            proj = first_float(ct["# Projections"])
            if proj is not None:
                rec["ct_number_images"] = f"{int(proj)}"
        if "Start" in ct:
            rec["start_time"] = _to_iso(ct["Start"], fallback=rec["start_time"])
        if "End" in ct:
            rec["end_time"] = _to_iso(ct["End"], fallback=rec["end_time"])
        if "Duration" in ct:
            rec["scan_time"] = ct["Duration"]
        if "Project folder" in ct:
            pf = ct["Project folder"].strip()
            # normalize to Windows-style backslashes if it looks like a Windows path
            rec["file_path"] = pf

    # ROI → image dims + physical size (needs voxel size)
    # ROI can be under _root or detector section depending on export; try both
    roi_str = root.get("ROI") or det.get("ROI")
    if roi_str:
        w, h = parse_roi(roi_str)
        if w: rec["image_width_pixels"] = str(w)
        if h: rec["image_height_pixels"] = str(h)
        try:
            vox_um = float(rec["ct_voxel_size_um"])
            if vox_um and w:
                rec["image_width_real"]  = f"{(w * vox_um) / 1000.0:.6f}".rstrip('0').rstrip('.')
            if vox_um and h:
                rec["image_height_real"] = f"{(h * vox_um) / 1000.0:.6f}".rstrip('0').rstrip('.')
        except Exception:
            pass

    # not available in these logs (leave N/A)
    # ct_objective, txrm_file_path, sample_* fields …

    rec["sha256"] = sha256_file(src)
    return rec

def _to_iso(s: str, fallback: str) -> str:
    s = s.strip()
    # typical format: 6/13/2024 12:01:16 PM
    for fmt in ("%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).isoformat()
        except Exception:
            pass
    return fallback

def main():
    ap = argparse.ArgumentParser(description="Parse RTF metadata into normalized JSON")
    ap.add_argument("input", help="Input .rtf file")
    ap.add_argument("-o", "--output", help="Output .json file (if omitted, prints to stdout)")
    ap.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    args = ap.parse_args()

    in_path = Path(args.input)
    if not in_path.exists():
        raise FileNotFoundError(in_path)

    text = load_text(in_path)
    # normalize newlines and bars that sometimes get doubled-up
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    sections = tokenize(text)
    rec = build_record(in_path, sections)
    out = {
        **{k: rec.get(k, 'N/A') for k in COLUMN_ORDER},
        "sections": sections  # keep the parsed raw content for auditing
    }

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=(2 if args.pretty else None))
    else:
        print(json.dumps(out, ensure_ascii=False, indent=(2 if args.pretty else None)))

if __name__ == "__main__":
    main()
