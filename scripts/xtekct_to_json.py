#!/usr/bin/env python3
"""
xtekct_to_json.py

- Parses Nikon .xtekct (INI-like) files
- Fills normalized keys you specified
- Writes a single JSON dict per input

CLI:
  python scripts/xtekct_to_json.py <input.xtekct> <output.json> [--pretty]
"""

import argparse
import configparser
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any


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


def init_record(fp: Path) -> Dict[str, Any]:
    return {
        'file_name': fp.name,
        'file_hyperlink': f'file:///{fp.resolve()}'.replace("\\","/"),
        'ct_voxel_size_um': 'N/A',
        'ct_objective': 'N/A',
        'ct_number_images': 'N/A',
        'Geometric_magnificiation': 'N/A',
        'Source_detector_distance': 'N/A',
        'Source_sample_distance': 'N/A',
        'ct_optical_magnification': 'N/A',
        'xray_tube_ID': 'N/A',
        'xray_tube_voltage': 'N/A',
        'xray_tube_power': 'N/A',
        'xray_tube_current': 'N/A',
        'xray_filter': 'N/A',
        'detector_binning': 'N/A',
        'detector_capture_time': 'N/A',
        'detector_averaging': 'N/A',
        'detector_skip': 'N/A',
        'image_width_pixels': 'N/A',
        'image_height_pixels': 'N/A',
        'image_width_real': 'N/A',
        'image_height_real': 'N/A',
        'scan_time': 'N/A',
        'start_time': datetime.fromtimestamp(fp.stat().st_mtime).isoformat(),
        'end_time': datetime.now().isoformat(),
        'txrm_file_path': 'N/A',
        'file_path': str(fp.resolve()),
        'acquisition_successful': 'Yes',
        'sample_x_start': 'N/A',
        'sample_x_end': 'N/A',
        'sample_x_range': 'N/A',
        'sample_y_start': 'N/A',
        'sample_y_end': 'N/A',
        'sample_y_range': 'N/A',
        'sample_z_start': 'N/A',
        'sample_z_end': 'N/A',
        'sample_z_range': 'N/A',
        'sample_theta_start': 'N/A'
    }


def is_textual_id(s: str) -> bool:
    return bool(re.search(r"[A-Za-z]", s or ""))


def parse_xtekct_file(input_path: Path, output_path: Path, pretty: bool = False) -> None:
    cfg = configparser.RawConfigParser()
    cfg.optionxform = str

    # robust read
    txt = input_path.read_text(encoding="utf-8", errors="ignore")
    from io import StringIO
    cfg.read_file(StringIO(txt))

    rec = init_record(input_path)

    # [Xrays]
    if cfg.has_section("Xrays"):
        kv = cfg.get("Xrays", "XraykV", fallback=None)
        ua = cfg.get("Xrays", "XrayuA", fallback=None)
        if kv is not None:
            try: rec['xray_tube_voltage'] = f"{float(kv):.3f}"
            except: rec['xray_tube_voltage'] = kv
        if ua is not None:
            try: rec['xray_tube_current'] = f"{float(ua):.3f}"
            except: rec['xray_tube_current'] = ua
        try:
            pw = float(rec['xray_tube_voltage']) * float(rec['xray_tube_current']) * 1e-3
            rec['xray_tube_power'] = f"{pw:.3f}"
        except Exception:
            pass

    # [CTPro] filter
    if cfg.has_section("CTPro"):
        thick = cfg.get("CTPro", "Filter_ThicknessMM", fallback=None)
        material = cfg.get("CTPro", "Filter_Material", fallback=None)
        if thick and material:
            rec['xray_filter'] = f"{thick} mm {material}"
        elif material:
            rec['xray_filter'] = material

    # [XTekCT]
    if cfg.has_section("XTekCT"):
        g = lambda k: cfg.get("XTekCT", k, fallback=None)
        vx, vy = g("VoxelsX"), g("VoxelsY")
        vsx, vsy = g("VoxelSizeX"), g("VoxelSizeY")
        if vx:
            try: rec['image_width_pixels'] = str(int(float(vx)))
            except: rec['image_width_pixels'] = vx
        if vy:
            try: rec['image_height_pixels'] = str(int(float(vy)))
            except: rec['image_height_pixels'] = vy
        if vsx:
            try: rec['ct_voxel_size_um'] = f"{float(vsx)*1000.0:.6f}"
            except: rec['ct_voxel_size_um'] = vsx
        try:
            if vx and vsx:
                rec['image_width_real']  = f"{float(vx)*float(vsx):.6f}"
            if vy and vsy:
                rec['image_height_real'] = f"{float(vy)*float(vsy):.6f}"
        except Exception:
            pass

        proj = g("Projections")
        if proj:
            try: rec['ct_number_images'] = str(int(float(proj)))
            except: rec['ct_number_images'] = proj

        sod = g("SrcToObject")
        sdd = g("SrcToDetector")
        if sdd:
            try: rec['Source_detector_distance'] = f"{float(sdd):.6f}"
            except: rec['Source_detector_distance'] = sdd
        if sod:
            try: rec['Source_sample_distance'] = f"{float(sod):.6f}"
            except: rec['Source_sample_distance'] = sod
        try:
            if sod and sdd and float(sod) != 0:
                rec['Geometric_magnificiation'] = f"{float(sdd)/float(sod):.6f}"
        except Exception:
            pass

        ini = g("InitialAngle")
        if ini is not None:
            rec['sample_theta_start'] = ini

        for k in ("SystemName","SourceName","XraySourceID","XraySourceName","TubeID"):
            v = g(k)
            if v and is_textual_id(v):
                rec['xray_tube_ID'] = v
                break

    # Add file hash
    rec['sha256'] = hashlib.sha256(input_path.read_bytes()).hexdigest()

    # Write JSON
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=2 if pretty else None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=str)
    ap.add_argument("output", type=str)
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()
    parse_xtekct_file(Path(args.input), Path(args.output), pretty=args.pretty)


if __name__ == "__main__":
    main()
