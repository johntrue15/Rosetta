#!/usr/bin/env python3
"""
xtekct_to_json.py
"""

import argparse, configparser, json, re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any


def _is_textual_id(s: str) -> bool:
    return bool(re.search(r"[A-Za-z]", s or ""))


def parse_xtekct_file(input_path: Path, output_path: Path, pretty: bool=False) -> None:
    rec: Dict[str, Any] = {
        'file_name': input_path.name,
        'file_hyperlink': f'file:///{input_path.resolve()}'.replace("\\","/"),
        'ct_voxel_size_um': 'N/A', 'ct_objective': 'N/A',
        'ct_number_images': 'N/A', 'Geometric_magnificiation': 'N/A',
        'Source_detector_distance': 'N/A', 'Source_sample_distance': 'N/A',
        'ct_optical_magnification': 'N/A', 'xray_tube_ID': 'N/A',
        'xray_tube_voltage': 'N/A', 'xray_tube_power': 'N/A', 'xray_tube_current': 'N/A',
        'xray_filter': 'N/A', 'detector_binning': 'N/A',
        'detector_capture_time': 'N/A', 'detector_averaging': 'N/A', 'detector_skip': 'N/A',
        'image_width_pixels': 'N/A', 'image_height_pixels': 'N/A',
        'image_width_real': 'N/A', 'image_height_real': 'N/A',
        'scan_time': 'N/A',
        'start_time': datetime.fromtimestamp(input_path.stat().st_mtime).isoformat(),
        'end_time': datetime.now().isoformat(),
        'txrm_file_path': 'N/A', 'file_path': str(input_path.resolve()),
        'acquisition_successful': 'Yes',
        'sample_x_start': 'N/A', 'sample_x_end': 'N/A', 'sample_x_range': 'N/A',
        'sample_y_start': 'N/A', 'sample_y_end': 'N/A', 'sample_y_range': 'N/A',
        'sample_z_start': 'N/A', 'sample_z_end': 'N/A', 'sample_z_range': 'N/A',
        'sample_theta_start': 'N/A'
    }

    cfg = configparser.RawConfigParser()
    cfg.optionxform = str
    from io import StringIO
    cfg.read_file(StringIO(input_path.read_text(encoding="utf-8", errors="ignore")))

    if cfg.has_section("Xrays"):
        kv = cfg.get("Xrays", "XraykV", fallback=None)
        ua = cfg.get("Xrays", "XrayuA", fallback=None)
        if kv:
            try: rec['xray_tube_voltage'] = f"{float(kv):.3f}"
            except: rec['xray_tube_voltage'] = kv
        if ua:
            try: rec['xray_tube_current'] = f"{float(ua):.3f}"
            except: rec['xray_tube_current'] = ua
        try:
            rec['xray_tube_power'] = f"{float(rec['xray_tube_voltage'])*float(rec['xray_tube_current'])*1e-3:.3f}"
        except: pass

    if cfg.has_section("CTPro"):
        thick = cfg.get("CTPro", "Filter_ThicknessMM", fallback=None)
        mat = cfg.get("CTPro", "Filter_Material", fallback=None)
        if thick and mat: rec['xray_filter'] = f"{thick} mm {mat}"
        elif mat:         rec['xray_filter'] = mat

    if cfg.has_section("XTekCT"):
        get = lambda k: cfg.get("XTekCT", k, fallback=None)
        vx, vy = get("VoxelsX"), get("VoxelsY")
        vsx, vsy = get("VoxelSizeX"), get("VoxelSizeY")
        if vx: rec['image_width_pixels'] = str(int(float(vx)))
        if vy: rec['image_height_pixels'] = str(int(float(vy)))
        if vsx:
            try: rec['ct_voxel_size_um'] = f"{float(vsx)*1000.0:.6f}"
            except: rec['ct_voxel_size_um'] = vsx
        try:
            if vx and vsx: rec['image_width_real'] = f"{float(vx)*float(vsx):.6f}"
            if vy and vsy: rec['image_height_real'] = f"{float(vy)*float(vsy):.6f}"
        except: pass
        proj = get("Projections")
        if proj:
            try: rec['ct_number_images'] = str(int(float(proj)))
            except: rec['ct_number_images'] = proj
        sod = get("SrcToObject"); sdd = get("SrcToDetector")
        if sdd:
            try: rec['Source_detector_distance'] = f"{float(sdd):.6f}"
            except: rec['Source_detector_distance'] = sdd
        if sod:
            try: rec['Source_sample_distance'] = f"{float(sod):.6f}"
            except: rec['Source_sample_distance'] = sod
        try:
            if sod and sdd and float(sod) != 0:
                rec['Geometric_magnificiation'] = f"{float(sdd)/float(sod):.6f}"
        except: pass
        ini = get("InitialAngle")
        if ini is not None:
            rec['sample_theta_start'] = ini
        for k in ("SystemName","SourceName","XraySourceID","XraySourceName","TubeID"):
            val = get(k)
            if val and _is_textual_id(val):
                rec['xray_tube_ID'] = val
                break

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
