#!/usr/bin/env python3
"""
pca_to_json.py

- Parses phoenix .pca (INI-like) files
- Sets `file_path` to calibration folder from [CalibImages] (e.g. 'S:\\CT_DATA\\...')
  when available (prefers MGainImg, then GainImg, OffsetImg, DefPixelImg),
  else falls back to repository file path.
"""

import argparse
import configparser
import hashlib
import json
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
        'ct_objective': 'DXR-250',
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
        'sample_theta_start': 'N/A',
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
    return cfg.get(section, option) if cfg.has_section(section) and cfg.has_option(section, option) else None


def _is_meaningful(s: Optional[str]) -> bool:
    return bool(s) and s.strip().upper() != "N/A"


def _win_dirname(p: str) -> str:
    return ntpath.dirname(p)


def parse_pca_file(input_path: Path, output_path: Path, pretty: bool = False) -> None:
    rec = init_record(input_path)

    cfg = configparser.RawConfigParser()
    cfg.optionxform = str
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
    for k_src, k_dst in [('Magnification', 'Geometric_magnificiation'),
                         ('FDD', 'Source_detector_distance'),
                         ('FOD', 'Source_sample_distance')]:
        v = safe_get(cfg, 'Geometry', k_src)
        if _is_meaningful(v):
            rec[k_dst] = v

    # CT
    v = safe_get(cfg, 'CT', 'NumberImages')
    if _is_meaningful(v):
        rec['ct_number_images'] = v
    v = safe_get(cfg, 'CT', 'ScanTimeCmpl')
    if _is_meaningful(v):
        rec['scan_time'] = v

    # Xray
    xid = safe_get(cfg, 'Xray', 'Name')
    if _is_meaningful(xid):
        rec['xray_tube_ID'] = xid
    xkv = safe_get(cfg, 'Xray', 'Voltage')
    xua = safe_get(cfg, 'Xray', 'Current')
    if _is_meaningful(xkv):
        rec['xray_tube_voltage'] = xkv
    if _is_meaningful(xua):
        rec['xray_tube_current'] = xua
    try:
        if _is_meaningful(xkv) and _is_meaningful(xua):
            rec['xray_tube_power'] = str((float(xkv) * float(xua)) / 1000.0)
    except Exception:
        pass
    xf = safe_get(cfg, 'Xray', 'Filter')
    if _is_meaningful(xf):
        rec['xray_filter'] = xf

    # Detector
    binning = safe_get(cfg, 'Detector', 'Binning')
    if _is_meaningful(binning):
        try:
            b = int(binning)
            rec['detector_binning'] = '1x1' if b == 0 else f'{2**b}x{2**b}'
        except Exception:
            rec['detector_binning'] = binning
    for sec, key in [('Detector', 'TimingVal'),
                     ('Detector', 'Avg'),
                     ('Detector', 'Skip')]:
        v = safe_get(cfg, sec, key)
        dst = {'TimingVal': 'detector_capture_time',
               'Avg': 'detector_averaging',
               'Skip': 'detector_skip'}[key]
        if _is_meaningful(v):
            rec[dst] = v

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

    # CNC
    for axis, dsts in [('CNC_0', ('sample_x_start', 'sample_x_end')),
                       ('CNC_1', ('sample_y_start', 'sample_y_end')),
                       ('CNC_2', ('sample_z_start', 'sample_z_end'))]:
        lp = safe_get(cfg, axis, 'LoadPos')
        ap = safe_get(cfg, axis, 'AcqPos')
        if _is_meaningful(lp):
            rec[dsts[0]] = lp
        if _is_meaningful(ap):
            rec[dsts[1]] = ap
    v = safe_get(cfg, 'CNC_3', 'AcqPos')
    if _is_meaningful(v):
        rec['sample_theta_start'] = v
    try:
        if rec['sample_x_start'] != 'N/A' and rec['sample_x_end'] != 'N/A':
            rec['sample_x_range'] = str(abs(float(rec['sample_x_end']) - float(rec['sample_x_start'])))
        if rec['sample_y_start'] != 'N/A' and rec['sample_y_end'] != 'N/A':
            rec['sample_y_range'] = str(abs(float(rec['sample_y_end']) - float(rec['sample_y_start'])))
        if rec['sample_z_start'] != 'N/A' and rec['sample_z_end'] != 'N/A':
            rec['sample_z_range'] = str(abs(float(rec['sample_z_end']) - float(rec['sample_z_start'])))
    except Exception:
        pass

    # Calibration images & folder
    calib = rec['calib_images']
    for key in ('MGainPoints','Avg','Skip','EnableAutoAcq','MGainVoltage',
                'MGainCurrent','MGainFilter','GainImg','MGainImg','OffsetImg','DefPixelImg'):
        val = safe_get(cfg, 'CalibImages', key)
        if _is_meaningful(val):
            calib[key] = val
    candidate = None
    for k in ('MGainImg', 'GainImg', 'OffsetImg', 'DefPixelImg'):
        if _is_meaningful(calib.get(k)):
            candidate = calib[k].strip()
            break
    if _is_meaningful(candidate):
        folder = _win_dirname(candidate)
        if _is_meaningful(folder):
            calib['calib_folder_path'] = folder
            rec['file_path'] = folder

    rec['sha256'] = hashlib.sha256(input_path.read_bytes()).hexdigest()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump({k: rec.get(k, 'N/A') for k in COLUMN_ORDER} | {
            # keep calib and hashes alongside normalized fields
            'calib_images': calib,
            'sha256': rec['sha256'],
            'source_path': str(output_path)  # where this JSON lives
        }, f, ensure_ascii=False, indent=2 if pretty else None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=str)
    ap.add_argument("output", type=str)
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()
    parse_pca_file(Path(args.input), Path(args.output), pretty=args.pretty)


if __name__ == "__main__":
    main()
