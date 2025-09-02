#!/usr/bin/env python3
# scripts/pca_to_json.py
from __future__ import annotations

import argparse
import configparser
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd

logger = logging.getLogger("pca_to_json")
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Fields we produce (kept stable for downstream)
COLUMN_ORDER = [
    # core metadata
    "file_name", "file_path", "file_hyperlink",
    # geometry & ct
    "ct_voxel_size_um", "ct_objective", "ct_number_images",
    "Geometric_magnificiation", "Source_detector_distance", "Source_sample_distance",
    # xray
    "xray_tube_ID", "xray_tube_voltage", "xray_tube_current", "xray_tube_power", "xray_filter",
    # detector & image
    "detector_binning", "detector_capture_time", "detector_averaging", "detector_skip",
    "image_width_pixels", "image_height_pixels", "image_width_real", "image_height_real",
    # cnc positions / ranges
    "sample_x_start", "sample_x_end", "sample_x_range",
    "sample_y_start", "sample_y_end", "sample_y_range",
    "sample_z_start", "sample_z_end", "sample_z_range",
    "sample_theta_start",
    # times / success
    "scan_time", "start_time", "end_time", "acquisition_successful",
    # new: calibration images & settings
    "calibration_dir",
    "calib_mgain_points", "calib_avg", "calib_skip", "calib_enable_auto_acq",
    "calib_mgain_voltage_raw", "calib_mgain_voltage_list",
    "calib_mgain_current_raw", "calib_mgain_current_list",
    "calib_mgain_filter_raw",  "calib_mgain_filter_list",
    "calib_gain_img", "calib_mgain_img", "calib_offset_img", "calib_defpixel_img",
]

def _init_record(p: Path) -> Dict[str, Any]:
    d = {k: "N/A" for k in COLUMN_ORDER}
    d["file_name"] = p.name
    d["file_path"] = str(p.resolve())
    d["file_hyperlink"] = f"file:///{p.resolve()}".replace("\\", "/")
    d["acquisition_successful"] = "No"  # set to Yes once parsed
    return d

def _read_cfg(p: Path) -> configparser.RawConfigParser:
    cfg = configparser.RawConfigParser()
    cfg.optionxform = str  # preserve case/keys
    try:
        with p.open("r", encoding="utf-8") as f:
            cfg.read_file(f)
        return cfg
    except UnicodeDecodeError:
        with p.open("r", encoding="latin-1") as f:
            cfg.read_file(f)
        return cfg

def _split_colon_list(raw: str) -> List[str]:
    # Handles trailing colon (e.g., "200:200:200:") and empty tokens
    return [t for t in raw.split(":") if t != ""]

def _as_float(s: str) -> float | None:
    try:
        return float(s)
    except Exception:
        return None

def parse_pca_file(p: Path) -> Dict[str, Any]:
    """Parse a single .pca file → one record (dict)."""
    rec = _init_record(p)
    try:
        cfg = _read_cfg(p)

        # ---------- Geometry ----------
        if cfg.has_section("Geometry"):
            v = cfg.get("Geometry", "VoxelSizeX", fallback=None)
            if v is not None:
                vx_mm = _as_float(v)
                if vx_mm is not None:
                    rec["ct_voxel_size_um"] = str(vx_mm * 1000.0)  # mm -> µm
            rec["Geometric_magnificiation"] = cfg.get("Geometry", "Magnification", fallback=rec["Geometric_magnificiation"])
            rec["Source_detector_distance"] = cfg.get("Geometry", "FDD", fallback=rec["Source_detector_distance"])
            rec["Source_sample_distance"] = cfg.get("Geometry", "FOD", fallback=rec["Source_sample_distance"])

        # ---------- Objective (fixed per your earlier mapping) ----------
        rec["ct_objective"] = "DXR-250"

        # ---------- CT ----------
        if cfg.has_section("CT"):
            rec["ct_number_images"] = cfg.get("CT", "NumberImages", fallback=rec["ct_number_images"])
            rec["scan_time"] = cfg.get("CT", "ScanTimeCmpl", fallback=rec["scan_time"])

        # ---------- Xray ----------
        if cfg.has_section("Xray"):
            rec["xray_tube_ID"] = cfg.get("Xray", "Name", fallback=rec["xray_tube_ID"])
            v = cfg.get("Xray", "Voltage", fallback=None)
            i = cfg.get("Xray", "Current", fallback=None)
            if v is not None: rec["xray_tube_voltage"] = v
            if i is not None: rec["xray_tube_current"] = i
            # power = V * I / 1000 (per earlier)
            try:
                if v is not None and i is not None:
                    rec["xray_tube_power"] = str(float(v) * float(i) / 1000.0)
            except Exception:
                pass
            rec["xray_filter"] = cfg.get("Xray", "Filter", fallback=rec["xray_filter"])

        # ---------- Detector ----------
        if cfg.has_section("Detector"):
            # Binning: integer exponent → "1x1", "2x2", "4x4"...
            b = cfg.get("Detector", "Binning", fallback=None)
            if b is not None:
                try:
                    b_int = int(b)
                    rec["detector_binning"] = "1x1" if b_int == 0 else f"{2**b_int}x{2**b_int}"
                except Exception:
                    rec["detector_binning"] = b
            rec["detector_capture_time"] = cfg.get("Detector", "TimingVal", fallback=rec["detector_capture_time"])
            rec["detector_averaging"] = cfg.get("Detector", "Avg", fallback=rec["detector_averaging"])
            rec["detector_skip"] = cfg.get("Detector", "Skip", fallback=rec["detector_skip"])

        # ---------- Image ----------
        if cfg.has_section("Image"):
            rec["image_width_pixels"] = cfg.get("Image", "DimX", fallback=rec["image_width_pixels"])
            rec["image_height_pixels"] = cfg.get("Image", "DimY", fallback=rec["image_height_pixels"])
            try:
                vx_um = float(rec["ct_voxel_size_um"]) if rec["ct_voxel_size_um"] != "N/A" else None
                if vx_um is not None and rec["image_width_pixels"] != "N/A":
                    rec["image_width_real"] = str(float(rec["image_width_pixels"]) * vx_um / 1000.0)
                if vx_um is not None and rec["image_height_pixels"] != "N/A":
                    rec["image_height_real"] = str(float(rec["image_height_pixels"]) * vx_um / 1000.0)
            except Exception:
                pass

        # ---------- CNC axes ----------
        def _cnc_pair(section: str, start_key: str, end_key: str, out_start: str, out_end: str, out_range: str):
            if cfg.has_section(section):
                rec[out_start] = cfg.get(section, start_key, fallback=rec[out_start])
                rec[out_end] = cfg.get(section, end_key, fallback=rec[out_end])
                try:
                    if rec[out_start] != "N/A" and rec[out_end] != "N/A":
                        rec[out_range] = str(abs(float(rec[out_end]) - float(rec[out_start])))
                except Exception:
                    pass

        _cnc_pair("CNC_0", "LoadPos", "AcqPos", "sample_x_start", "sample_x_end", "sample_x_range")
        _cnc_pair("CNC_1", "LoadPos", "AcqPos", "sample_y_start", "sample_y_end", "sample_y_range")
        _cnc_pair("CNC_2", "LoadPos", "AcqPos", "sample_z_start", "sample_z_end", "sample_z_range")
        if cfg.has_section("CNC_3"):
            rec["sample_theta_start"] = cfg.get("CNC_3", "AcqPos", fallback=rec["sample_theta_start"])

        # ---------- CalibImages (NEW) ----------
        if cfg.has_section("CalibImages"):
            section = "CalibImages"
            rec["calib_mgain_points"] = cfg.get(section, "MGainPoints", fallback=rec["calib_mgain_points"])
            rec["calib_avg"] = cfg.get(section, "Avg", fallback=rec["calib_avg"])
            rec["calib_skip"] = cfg.get(section, "Skip", fallback=rec["calib_skip"])
            rec["calib_enable_auto_acq"] = cfg.get(section, "EnableAutoAcq", fallback=rec["calib_enable_auto_acq"])

            # Colon-separated series; keep both raw and parsed lists
            mv_raw = cfg.get(section, "MGainVoltage", fallback="")
            mi_raw = cfg.get(section, "MGainCurrent", fallback="")
            mf_raw = cfg.get(section, "MGainFilter",  fallback="")

            rec["calib_mgain_voltage_raw"] = mv_raw
            rec["calib_mgain_voltage_list"] = _split_colon_list(mv_raw)

            rec["calib_mgain_current_raw"] = mi_raw
            rec["calib_mgain_current_list"] = _split_colon_list(mi_raw)

            rec["calib_mgain_filter_raw"] = mf_raw
            rec["calib_mgain_filter_list"] = _split_colon_list(mf_raw)

            # Image paths (keep exactly as written, including backslashes)
            rec["calib_gain_img"]   = cfg.get(section, "GainImg",     fallback=rec["calib_gain_img"])
            rec["calib_mgain_img"]  = cfg.get(section, "MGainImg",    fallback=rec["calib_mgain_img"])
            rec["calib_offset_img"] = cfg.get(section, "OffsetImg",   fallback=rec["calib_offset_img"])
            rec["calib_defpixel_img"] = cfg.get(section, "DefPixelImg", fallback=rec["calib_defpixel_img"])

            # Derive a stable calibration_dir from the first available image path
            def _dir_of(path_str: str) -> str | None:
                if not path_str or path_str == "N/A":
                    return None
                # Do not normalize separators; just split on both kinds
                # to keep Windows drive + backslashes intact in the output.
                # We only need the directory portion as a string.
                for sep in ["\\", "/"]:
                    if sep in path_str:
                        return path_str.rsplit(sep, 1)[0]
                return None

            rec["calibration_dir"] = (
                _dir_of(rec["calib_offset_img"]) or
                _dir_of(rec["calib_mgain_img"]) or
                _dir_of(rec["calib_gain_img"]) or
                _dir_of(rec["calib_defpixel_img"]) or
                rec["calibration_dir"]
            )

        # ---------- Times / success ----------
        try:
            rec["start_time"] = datetime.fromtimestamp(p.stat().st_mtime).isoformat()
        except Exception:
            rec["start_time"] = datetime.now().isoformat()
        rec["end_time"] = datetime.now().isoformat()
        rec["acquisition_successful"] = "Yes"

    except Exception as e:
        logger.error("Error parsing %s: %s", p, e)

    # Ensure only known columns (stable order) + keep any extra fields we added
    ordered = {k: rec.get(k, "N/A") for k in COLUMN_ORDER}
    # Add any extras that slipped in
    for k, v in rec.items():
        if k not in ordered:
            ordered[k] = v
    return ordered

# ---------------- CLI (directory or single file) ----------------

def _collect(input_path: Path) -> Tuple[List[Path], Path, str]:
    if not input_path.exists():
        raise FileNotFoundError(f"INPUT_PATH not found: {input_path}")

    if input_path.is_dir():
        files = list(input_path.rglob("*.pca")) + list(input_path.rglob("*.PCA"))
        output_dir = input_path
        base = "combined_pca_data"
        logger.info("Scanning directory: %s", input_path)
    elif input_path.is_file():
        if input_path.suffix.lower() != ".pca":
            raise ValueError(f"INPUT_PATH is a file but not a .pca: {input_path}")
        files = [input_path]
        output_dir = input_path.parent
        base = f"{input_path.stem}_pca"
        logger.info("Parsing single file: %s", input_path.name)
    else:
        raise ValueError(f"Unsupported path type: {input_path}")
    return files, output_dir, base

def main():
    ap = argparse.ArgumentParser(description="Parse .pca files to JSON/JSONL (captures [CalibImages])")
    ap.add_argument("input", help="Directory or single .pca file")
    ap.add_argument("-o", "--outdir", default=None, help="Output directory (defaults to the input dir)")
    ap.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    args = ap.parse_args()

    in_path = Path(args.input).resolve()
    files, default_outdir, base = _collect(in_path)

    outdir = Path(args.outdir).resolve() if args.outdir else default_outdir
    outdir.mkdir(parents=True, exist_ok=True)

    # Aggregate outputs (still handy in notebooks/CLI)
    out_json = outdir / f"{base}.json"
    out_jsonl = outdir / f"{base}.jsonl"

    records: List[Dict[str, Any]] = []
    for fp in files:
        logger.info("Parsing: %s", fp.name)
        records.append(parse_pca_file(fp))

    df = pd.DataFrame(records)
    if not df.empty:
        if "file_path" in df.columns:
            df = df.drop_duplicates(subset=["file_path"], keep="last")

    with out_json.open("w", encoding="utf-8") as f:
        json.dump(df.to_dict(orient="records"), f, ensure_ascii=False, indent=2 if args.pretty else None)

    with out_jsonl.open("w", encoding="utf-8") as f:
        for _, row in df.iterrows():
            f.write(json.dumps(row.to_dict(), ensure_ascii=False) + "\n")

    logger.info("Wrote %d record(s) → %s and %s", len(df), out_json, out_jsonl)

if __name__ == "__main__":
    main()
