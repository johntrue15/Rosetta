#!/usr/bin/env python3
"""
txrm_to_json.py

Parses Zeiss Xradia .txrm / .xrm files (OLE compound documents) and outputs
Rosetta-compatible JSON metadata.  Uses the open-source ``olefile`` library
so it can run headlessly in CI — no proprietary Zeiss libraries required.

OLE stream layout knowledge is adapted from the AMNH fork of xrmreader
(UChicago Argonne / dxchange, BSD-3).
"""

import argparse
import hashlib
import json
import struct
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import olefile

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
    'sample_z_range', 'sample_theta_start',
]


# ---------------------------------------------------------------------------
#  Low-level OLE helpers (ported from xrmreader)
# ---------------------------------------------------------------------------

def _ole_read_struct(ole: olefile.OleFileIO, label: str, fmt: str):
    if ole.exists(label):
        data = ole.openstream(label).read()
        try:
            return struct.unpack(fmt, data)
        except struct.error:
            return None
    return None


def _ole_value(ole: olefile.OleFileIO, label: str, fmt: str):
    result = _ole_read_struct(ole, label, fmt)
    if result is not None:
        return result[0]
    return None


def _ole_string(ole: olefile.OleFileIO, label: str, max_len: int = 260) -> Optional[str]:
    """Read a null-terminated string from an OLE stream."""
    raw = _ole_value(ole, label, f'<{max_len}s')
    if raw is None:
        return None
    if isinstance(raw, bytes):
        try:
            raw = raw.decode('utf-8')
        except UnicodeDecodeError:
            raw = raw.decode('latin-1')
    return raw.split('\x00', 1)[0].strip() or None


# ---------------------------------------------------------------------------
#  Record initialisation (mirrors pca_to_json.init_record)
# ---------------------------------------------------------------------------

def _init_record(fp: Path) -> Dict[str, Any]:
    return {
        'file_name': fp.name,
        'file_hyperlink': f'file:///{fp.resolve()}'.replace("\\", "/"),
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
        'txrm_file_path': str(fp.resolve()),
        'file_path': str(fp.resolve().parent),
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
    }


def _safe_float(val) -> Optional[float]:
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
#  Main parser
# ---------------------------------------------------------------------------

def parse_txrm_file(input_path: Path, output_path: Path, pretty: bool = False) -> None:
    """Parse a .txrm / .xrm OLE file and write Rosetta-standard JSON."""
    rec = _init_record(input_path)

    ole = olefile.OleFileIO(str(input_path))
    try:
        _extract_metadata(ole, rec)
    finally:
        ole.close()

    rec['sha256'] = hashlib.sha256(input_path.read_bytes()).hexdigest()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    out = {k: rec.get(k, 'N/A') for k in COLUMN_ORDER}
    out['sha256'] = rec['sha256']
    out['source_path'] = str(output_path)

    with output_path.open('w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2 if pretty else None)


def _extract_metadata(ole: olefile.OleFileIO, rec: Dict[str, Any]) -> None:
    num_images = _ole_value(ole, 'ImageInfo/NoOfImages', '<I')
    if num_images is not None:
        rec['ct_number_images'] = str(num_images)

    # --- Image dimensions ---
    width = _ole_value(ole, 'ImageInfo/ImageWidth', '<I')
    height = _ole_value(ole, 'ImageInfo/ImageHeight', '<I')
    if width is not None:
        rec['image_width_pixels'] = str(width)
    if height is not None:
        rec['image_height_pixels'] = str(height)

    # --- Pixel / voxel size ---
    pixel_size = _ole_value(ole, 'ImageInfo/pixelsize', '<f')
    if pixel_size is not None and pixel_size > 0:
        rec['ct_voxel_size_um'] = str(pixel_size)
        if width is not None:
            rec['image_width_real'] = str(round(width * pixel_size, 4))
        if height is not None:
            rec['image_height_real'] = str(round(height * pixel_size, 4))

    # --- Objective ---
    obj_mag = _ole_value(ole, 'AcquisitionSettings/ObjectiveMag', '<f')
    obj_id = _ole_value(ole, 'AcquisitionSettings/ObjectiveID', '<I')
    if obj_mag is not None and obj_mag > 0:
        rec['ct_objective'] = f'{obj_mag:.1f}x'
        if str(obj_mag).rstrip('0').rstrip('.') in ('4', '20', '40'):
            rec['ct_optical_magnification'] = 'yes'
        else:
            rec['ct_optical_magnification'] = 'no'
    elif obj_id is not None:
        rec['ct_objective'] = f'ObjectiveID-{obj_id}'

    # --- Geometry (source / detector distances) ---
    sto_ra = _safe_float(_ole_value(ole, 'ImageInfo/StoRADistance', '<f'))
    dto_ra = _safe_float(_ole_value(ole, 'ImageInfo/DtoRADistance', '<f'))

    if sto_ra is not None and sto_ra > 0:
        rec['Source_sample_distance'] = str(round(sto_ra, 4))
    if sto_ra is not None and dto_ra is not None and (sto_ra + dto_ra) > 0:
        sdd = sto_ra + dto_ra
        rec['Source_detector_distance'] = str(round(sdd, 4))
        if sto_ra > 0:
            rec['Geometric_magnificiation'] = str(round(sdd / sto_ra, 6))

    # --- X-ray source ---
    voltage = _safe_float(_ole_value(ole, 'ImageInfo/Voltage', '<f'))
    current = _safe_float(_ole_value(ole, 'ImageInfo/Current', '<f'))
    power = _safe_float(_ole_value(ole, 'AcquisitionSettings/SrcPower', '<f'))

    if voltage is not None:
        rec['xray_tube_voltage'] = str(voltage)
    if current is not None:
        rec['xray_tube_current'] = str(current)
    if power is not None and power > 0:
        rec['xray_tube_power'] = str(power)
    elif voltage is not None and current is not None and voltage > 0 and current > 0:
        rec['xray_tube_power'] = str(round(voltage * current / 1e6, 4))

    # --- Filter ---
    filt = _ole_string(ole, 'AcquisitionSettings/SourceFilterName')
    if filt:
        rec['xray_filter'] = filt

    # --- Detector ---
    binning = _ole_value(ole, 'AcquisitionSettings/Binning', '<I')
    if binning is not None:
        rec['detector_binning'] = f'{binning}x{binning}' if binning > 0 else '1x1'

    exp_time = _safe_float(_ole_value(ole, 'AcquisitionSettings/ExpTime', '<f'))
    if exp_time is not None:
        rec['detector_capture_time'] = str(exp_time)

    # --- Facility as xray_tube_ID ---
    facility = _ole_string(ole, 'SampleInfo/Facility', max_len=50)
    if facility:
        rec['xray_tube_ID'] = facility


def main():
    ap = argparse.ArgumentParser(
        description='Parse Zeiss Xradia .txrm files to Rosetta JSON')
    ap.add_argument('input', type=str, help='Path to .txrm file')
    ap.add_argument('output', type=str, help='Path to output .json file')
    ap.add_argument('--pretty', action='store_true', help='Pretty-print JSON')
    args = ap.parse_args()
    parse_txrm_file(Path(args.input), Path(args.output), pretty=args.pretty)


if __name__ == '__main__':
    main()
