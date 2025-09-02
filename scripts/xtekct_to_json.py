#!/usr/bin/env python3
# scripts/xtekct_to_json.py
from __future__ import annotations

import argparse
import configparser
import json
import logging
import re
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any, Dict, List, Tuple

logger = logging.getLogger("xtekct_to_json")
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Keep these keys aligned with the rest of your flow
COLUMN_ORDER = [
    # core
    "file_name", "file_path", "file_hyperlink",
    # geometry & ct
    "ct_voxel_size_um", "ct_objective", "ct_number_images",
    "Geometric_magnificiation", "Source_detector_distance", "Source_sample_distance",
    "ct_optical_magnification",
    # xray
    "xray_tube_ID", "xray_tube_voltage", "xray_tube_power", "xray_tube_current", "xray_filter",
    # detector & image
    "detector_binning", "detector_capture_time", "detector_averaging", "detector_skip",
    "image_width_pixels", "image_height_pixels", "image_width_real", "image_height_real",
    # times / success
    "scan_time", "start_time", "end_time", "txrm_file_path", "acquisition_successful",
    # cnc / angles
    "sample_x_start", "sample_x_end", "sample_x_range",
    "sample_y_start", "sample_y_end", "sample_y_range",
    "sample_z_start", "sample_z_end", "sample_z_range",
    "sample_theta_start",
]

def _init_record(p: Path) -> Dict[str, Any]:
    d = {k: "N/A" for k in COLUMN_ORDER}
    d["file_name"] = p.name
    d["file_path"] = str(p.resolve())
    d["file_hyperlink"] = f"file:///{p.resolve()}".replace("\\", "/")
    d["start_time"] = datetime.fromtimestamp(p.stat().st_mtime).isoformat()
    d["end_time"] = datetime.now().isoformat()
    d["acquisition_successful"] = "Yes"
    return d

def _read_ini(fp: Path) -> configparser.RawConfigParser:
    # xtekct is ini-like, sometimes with odd encodings; ignore errors
    txt = fp.read_text(encoding="utf-8", errors="ignore")
    cfg = configparser.RawConfigParser()
    cfg.optionxform = str
    cfg.read_file(StringIO(txt))
    return cfg

def _has_letters(s: str | None) -> bool:
    return bool(re.search(r"[A-Za-z]", s or ""))

def parse_xtekct_file(fp: Path) -> Dict[str, Any]:
    """Parse a single .xtekct file → dict (one record)."""
    rec = _init_record(fp)
    try:
        cfg = _read_ini(fp)

        # ---- [Xrays] ----
        if cfg.has_section("Xrays"):
            kv = cfg.get("Xrays", "XraykV", fallback=None)
            ua = cfg.get("Xrays", "XrayuA", fallback=None)
            if kv is not None:
                try: rec["xray_tube_voltage"] = f"{float(kv):.6f}"
                except: rec["xray_tube_voltage"] = kv
            if ua is not None:
                try: rec["xray_tube_current"] = f"{float(ua):.6f}"
                except: rec["xray_tube_current"] = ua
            try:
                rec["xray_tube_power"] = f"{float(rec['xray_tube_voltage']) * float(rec['xray_tube_current']) * 1e-3:.6f}"
            except Exception:
                pass

        # ---- [CTPro] (filter) ----
        if cfg.has_section("CTPro"):
            thick = cfg.get("CTPro", "Filter_ThicknessMM", fallback=None)
            material = cfg.get("CTPro", "Filter_Material", fallback=None)
            if thick and material:
                rec["xray_filter"] = f"{thick} mm {material}"
            elif material:
                rec["xray_filter"] = material

        # ---- [XTekCT] (geometry, voxel, dims, projections, distances) ----
        if cfg.has_section("XTekCT"):
            g = lambda k: cfg.get("XTekCT", k, fallback=None)

            # dimensions
            vx, vy = g("VoxelsX"), g("VoxelsY")
            if vx:
                try: rec["image_width_pixels"] = str(int(float(vx)))
                except: rec["image_width_pixels"] = vx
            if vy:
                try: rec["image_height_pixels"] = str(int(float(vy)))
                except: rec["image_height_pixels"] = vy

            # voxel sizes (mm); we publish ct_voxel_size_um from VoxelSizeX
            vsx, vsy = g("VoxelSizeX"), g("VoxelSizeY")
            if vsx:
                try: rec["ct_voxel_size_um"] = f"{float(vsx) * 1000.0:.6f}"
                except: rec["ct_voxel_size_um"] = vsx

            # physical size (mm)
            try:
                if vx and vsx:
                    rec["image_width_real"] = f"{float(vx) * float(vsx):.6f}"
                if vy and vsy:
                    rec["image_height_real"] = f"{float(vy) * float(vsy):.6f}"
            except Exception:
                pass

            # projections
            proj = g("Projections")
            if proj:
                try: rec["ct_number_images"] = str(int(float(proj)))
                except: rec["ct_number_images"] = proj

            # distances/magnification (mm)
            sod = g("SrcToObject")
            sdd = g("SrcToDetector")
            if sdd:
                try: rec["Source_detector_distance"] = f"{float(sdd):.6f}"
                except: rec["Source_detector_distance"] = sdd
            if sod:
                try: rec["Source_sample_distance"] = f"{float(sod):.6f}"
                except: rec["Source_sample_distance"] = sod
            try:
                if sod and sdd and float(sod) != 0.0:
                    rec["Geometric_magnificiation"] = f"{float(sdd) / float(sod):.6f}"
            except Exception:
                pass

            # rotation
            ini = g("InitialAngle")
            if ini is not None:
                rec["sample_theta_start"] = ini

            # possible tube/system textual id
            for k in ("SystemName", "SourceName", "XraySourceID", "XraySourceName", "TubeID"):
                val = g(k)
                if val and _has_letters(val):
                    rec["xray_tube_ID"] = val
                    break

        # Objective: keep consistent with PCA mapping if you want a default
        if rec["ct_objective"] == "N/A":
            rec["ct_objective"] = "N/A"

    except Exception as e:
        logger.error("Error parsing %s: %s", fp, e)
        rec["acquisition_successful"] = "No"

    # Return ordered keys + any extras
    ordered = {k: rec.get(k, "N/A") for k in COLUMN_ORDER}
    for k, v in rec.items():
        if k not in ordered:
            ordered[k] = v
    return ordered

# ---------------- Optional CLI (for local runs) ----------------

def _collect(in_path: Path) -> Tuple[List[Path], Path]:
    if not in_path.exists():
        raise FileNotFoundError(in_path)
    if in_path.is_dir():
        files = list(in_path.rglob("*.xtekct")) + list(in_path.rglob("*.XTEKCT"))
        outdir = in_path
    else:
        if in_path.suffix.lower() != ".xtekct":
            raise ValueError(f"Not an .xtekct file: {in_path}")
        files = [in_path]
        outdir = in_path.parent
    return files, outdir

def main():
    ap = argparse.ArgumentParser(description="Parse Nikon .xtekct → one JSON per file")
    ap.add_argument("input", help="Directory OR a single .xtekct file")
    ap.add_argument("-o", "--outdir", default=None, help="Output directory (default: input dir)")
    ap.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    args = ap.parse_args()

    in_path = Path(args.input).resolve()
    files, default_outdir = _collect(in_path)

    outdir = Path(args.outdir).resolve() if args.outdir else default_outdir
    outdir.mkdir(parents=True, exist_ok=True)

    for fp in files:
        rec = parse_xtekct_file(fp)
        # Write with ".json" appended to original filename (keep original extension)
        out_path = outdir / f"{fp.name}.json"
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(rec, f, ensure_ascii=False, indent=2 if args.pretty else None)
        logger.info("Wrote %s", out_path)

if __name__ == "__main__":
    main()
