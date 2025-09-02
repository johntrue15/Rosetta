#!/usr/bin/env python3
"""
pca_to_json.py

- Parses phoenix .pca (INI-like) files
- Fills normalized fields (geometry, CT, xray, detector, image, CNC axes)
- Captures [CalibImages] fields and the calibration folder path
- Sets `file_path` to the calibration folder path (e.g. 'S:\\CT_DATA\\...') when available
  from CalibImages entries (preferring MGainImg, then GainImg, then OffsetImg, then DefPixelImg).
  Falls back to the local repo file path only if no calibration path is found.
- Writes a single JSON dict per input .pca

CLI:
  python scripts/pca_to_json.py <input.pca> <output.json> [--pretty]
"""

import argparse
import configparser
import hashlib
import json
import os
import ntpath
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional


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
        'file_hyperlink': f'file:///{fp.resolve()}'.replace("\\", "/"),
        'ct_voxel_size_um': 'N/A',
        'ct_objective': 'DXR-250',  # per your original script
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
        # NOTE: this will be overwritten with the calibration folder path if found
        'file_path': str(fp.resolve()),
        'txrm_file_path': 'N/A',
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
        'sample_theta_start': 'N/A',
        # Calibration info bucket
        'calib_images': {
            'MGainPoints': 'N/A',
            'Avg': 'N/A',
            'Skip': 'N/A',
            'EnableAutoAcq': 'N/A',
            'MGainVoltage': 'N/A',
            'MGainCurrent': 'N/A',
            'MGainFilter': 'N/A',
            'GainImg': 'N/A',
            'MGainImg': 'N/A',
            'OffsetImg': 'N/A',
            'DefPixelImg': 'N/A',
            'calib_folder_path': 'N/A'
        }
    }


def safe_get(cfg: configparser.RawConfigParser, section: str, option: str) -> Optional[str]:
    if cfg.has_section(section) and cfg.has_option(section, option):
        return cfg.get(section, option)
    return None


def _is_meaningful(value: Optional[str]) -> bool:
    if value is None:
        return False
    v = value.strip()
    if not v or v.upper() == 'N/A':
        return False
    return True


def _windows_dirname(path_str: str) -> str:
    """
    Return the directory component of a Windows-style path string.
    Uses ntpath to correctly handle backslashes and drive letters on any OS.
    """
    return ntpath.dirname(path_str)


def parse_pca_file(input_path: Path, output_path: Path, pretty: bool = False) -> None:
    rec = init_record(input_path)

    cfg = configparser.RawConfigParser()
    cfg.optionxform = str  # preserve case

    # Robust encoding handling
    try:
        with input_path.open('r', encoding='utf-8') as f:
            cfg.read_file(f)
    except UnicodeDecodeError:
        with input_path.open('r', encoding='latin-1') as f:
            cfg.read_file(f)

    # Geometry
    vsx = safe_get(cfg, 'Geometry', 'VoxelSizeX')
    if _is_meaningful(vsx):
        try:
            rec['ct_voxel_size_um'] = str(float(vsx) * 1000.0)
        except Exception:
            rec['ct_voxel_size_um'] = vsx

    val = safe_get(cfg, 'Geometry', 'Magnification')
    if _is_meaningful(val):
        rec['Geometric_magnificiation'] = val
    val = safe_get(cfg, 'Geometry', 'FDD')
    if _is_meaningful(val):
        rec['Source_detector_distance'] = val
    val = safe_get(cfg, 'Geometry', 'FOD')
    if _is_meaningful(val):
        rec['Source_sample_distance'] = val

    # CT
    val = safe_get(cfg, 'CT', 'NumberImages')
    if _is_meaningful(val):
        rec['ct_number_images'] = val
    val = safe_get(cfg, 'CT', 'ScanTimeCmpl')
    if _is_meaningful(val):
        rec['scan_time'] = val

    # Xray
    xkv = safe_get(cfg, 'Xray', 'Voltage')
    xua = safe_get(cfg, 'Xray', 'Current')
    xid = safe_get(cfg, 'Xray', 'Name')
    if _is_meaningful(xid):
        rec['xray_tube_ID'] = xid
    if _is_meaningful(xkv):
        rec['xray_tube_voltage'] = xkv
    if _is_meaningful(xua):
        rec['xray_tube_current'] = xua
    try:
        if _is_meaningful(xkv) and _is_meaningful(xua):
            rec['xray_tube_power'] = str((float(xkv) * float(xua)) / 1000.0)  # W
    except Exception:
        pass
    val = safe_get(cfg, 'Xray', 'Filter')
    if _is_meaningful(val):
        rec['xray_filter'] = val

    # Detector
    binning = safe_get(cfg, 'Detector', 'Binning')
    if _is_meaningful(binning):
        try:
            b_int = int(binning)
            rec['detector_binning'] = '1x1' if b_int == 0 else f'{2**b_int}x{2**b_int}'
        except Exception:
            rec['detector_binning'] = binning
    val = safe_get(cfg, 'Detector', 'TimingVal')
    if _is_meaningful(val):
        rec['detector_capture_time'] = val
    val = safe_get(cfg, 'Detector', 'Avg')
    if _is_meaningful(val):
        rec['detector_averaging'] = val
    val = safe_get(cfg, 'Detector', 'Skip')
    if _is_meaningful(val):
        rec['detector_skip'] = val

    # Image
    dimx = safe_get(cfg, 'Image', 'DimX')
    dimy = safe_get(cfg, 'Image', 'DimY')
    if _is_meaningful(dimx):
        rec['image_width_pixels'] = dimx
    if _is_meaningful(dimy):
        rec['image_height_pixels'] = dimy
    try:
        if _is_meaningful(dimx) and rec['ct_voxel_size_um'] != 'N/A':
            rec['image_width_real'] = str(float(dimx) * float(rec['ct_voxel_size_um']) / 1000.0)
        if _is_meaningful(dimy) and rec['ct_voxel_size_um'] != 'N/A':
            rec['image_height_real'] = str(float(dimy) * float(rec['ct_voxel_size_um']) / 1000.0)
    except Exception:
        pass

    # CNC axes
    val = safe_get(cfg, 'CNC_0', 'LoadPos')
    if _is_meaningful(val):
        rec['sample_x_start'] = val
    val = safe_get(cfg, 'CNC_0', 'AcqPos')
    if _is_meaningful(val):
        rec['sample_x_end'] = val
    val = safe_get(cfg, 'CNC_1', 'LoadPos')
    if _is_meaningful(val):
        rec['sample_y_start'] = val
    val = safe_get(cfg, 'CNC_1', 'AcqPos')
    if _is_meaningful(val):
        rec['sample_y_end'] = val
    val = safe_get(cfg, 'CNC_2', 'LoadPos')
    if _is_meaningful(val):
        rec['sample_z_start'] = val
    val = safe_get(cfg, 'CNC_2', 'AcqPos')
    if _is_meaningful(val):
        rec['sample_z_end'] = val
    val = safe_get(cfg, 'CNC_3', 'AcqPos')
    if _is_meaningful(val):
        rec['sample_theta_start'] = val

    # Ranges
    try:
        if rec['sample_x_start'] != 'N/A' and rec['sample_x_end'] != 'N/A':
            rec['sample_x_range'] = str(abs(float(rec['sample_x_end']) - float(rec['sample_x_start'])))
        if rec['sample_y_start'] != 'N/A' and rec['sample_y_end'] != 'N/A':
            rec['sample_y_range'] = str(abs(float(rec['sample_y_end']) - float(rec['sample_y_start'])))
        if rec['sample_z_start'] != 'N/A' and rec['sample_z_end'] != 'N/A':
            rec['sample_z_range'] = str(abs(float(rec['sample_z_end']) - float(rec['sample_z_start'])))
    except Exception:
        pass

    # -------- Calibration images --------
    calib = rec['calib_images']
    for key in (
        'MGainPoints', 'Avg', 'Skip', 'EnableAutoAcq',
        'MGainVoltage', 'MGainCurrent', 'MGainFilter',
        'GainImg', 'MGainImg', 'OffsetImg', 'DefPixelImg'
    ):
        val = safe_get(cfg, 'CalibImages', key)
        if _is_meaningful(val):
            calib[key] = val

    # Prefer a Windows-style path from CalibImages to derive folder
    candidate = None
    for k in ('MGainImg', 'GainImg', 'OffsetImg', 'DefPixelImg'):
        if _is_meaningful(calib.get(k)):
            candidate = calib[k].strip()
            break

    if _is_meaningful(candidate):
        folder = _windows_dirname(candidate)
        if _is_meaningful(folder):
            calib['calib_folder_path'] = folder
            # << IMPORTANT: set file_path to this calibration folder path >>
            rec['file_path'] = folder

    # Add file hash
    rec['sha256'] = hashlib.sha256(input_path.read_bytes()).hexdigest()

    # Write final single-record JSON
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=2 if pretty else None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=str)
    ap.add_argument("output", type=str)
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()
    parse_pca_file(Path(args.input), Path(args.output), pretty=args.pretty)


if __name__ == "__main__":
    main()
