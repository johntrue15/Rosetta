#!/usr/bin/env python3
"""
skyscan_to_json.py

Parses Bruker SkyScan reconstruction .log files (INI-like) into
normalised JSON matching the Rosetta COLUMN_ORDER schema.

SkyScan log files contain sections: [System], [Acquisition],
[Reconstruction], and [File name convention].
"""

import argparse
import configparser
import hashlib
import json
import re
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any, Dict, Optional


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


def _init_record(fp: Path) -> Dict[str, Any]:
    return {k: 'N/A' for k in COLUMN_ORDER} | {
        'file_name': fp.name,
        'file_hyperlink': f'file:///{fp.resolve()}'.replace("\\", "/"),
        'start_time': datetime.fromtimestamp(fp.stat().st_mtime).isoformat(),
        'end_time': datetime.now().isoformat(),
        'file_path': str(fp.resolve()),
        'acquisition_successful': 'Yes',
    }


def _safe(cfg: configparser.RawConfigParser, section: str, key: str) -> Optional[str]:
    if cfg.has_section(section) and cfg.has_option(section, key):
        val = cfg.get(section, key).strip()
        return val if val else None
    return None


def _num(val: Optional[str]) -> Optional[str]:
    """Strip whitespace and return the numeric string, or None."""
    if val is None:
        return None
    val = val.strip()
    try:
        float(val)
        return val
    except ValueError:
        return None


def _parse_skyscan_duration(raw: str) -> Optional[str]:
    """Parse SkyScan duration strings like '0h:18m:3s' or '00h:45min'."""
    m = re.match(r'(\d+)h:(\d+)m(?:in)?:?(\d+)?s?', raw.strip())
    if m:
        h, mins, s = int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)
        total = h * 3600 + mins * 60 + s
        return str(total)
    return raw.strip()


def _parse_averaging(raw: str) -> Optional[str]:
    """Extract count from 'ON (2)' or 'OFF (10)' style values."""
    m = re.search(r'\((\d+)\)', raw)
    if m:
        return m.group(1)
    if raw.strip().upper() in ('ON', 'OFF'):
        return raw.strip()
    return raw.strip()


def _parse_study_datetime(raw: str) -> Optional[str]:
    """Parse 'Dec 06, 2018  13:31:56' into ISO-8601."""
    cleaned = re.sub(r'\s+', ' ', raw.strip())
    for fmt in ('%b %d, %Y %H:%M:%S', '%b %d, %Y %H:%M'):
        try:
            return datetime.strptime(cleaned, fmt).isoformat()
        except ValueError:
            continue
    return raw.strip()


def parse_skyscan_file(input_path: Path, output_path: Path, pretty: bool = False) -> None:
    rec = _init_record(input_path)

    cfg = configparser.RawConfigParser()
    cfg.optionxform = str
    try:
        text = input_path.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        text = input_path.read_text(encoding='latin-1')
    cfg.read_file(StringIO(text))

    # -- [System] --
    scanner = _safe(cfg, 'System', 'Scanner') or _safe(cfg, 'System', 'Scanner type')
    if scanner:
        rec['ct_objective'] = scanner

    source_type = _safe(cfg, 'System', 'Source Type')
    target_type = _safe(cfg, 'Acquisition', 'Source target type')
    xray_id_parts = [p for p in (source_type, target_type) if p]
    if xray_id_parts:
        rec['xray_tube_ID'] = ' / '.join(xray_id_parts)

    # -- [Acquisition] --
    kv = _num(_safe(cfg, 'Acquisition', 'Source Voltage (kV)'))
    ua = _num(_safe(cfg, 'Acquisition', 'Source Current (uA)'))
    if kv:
        rec['xray_tube_voltage'] = kv
    if ua:
        rec['xray_tube_current'] = ua
    if kv and ua:
        try:
            rec['xray_tube_power'] = f"{float(kv) * float(ua) / 1000.0:.3f}"
        except ValueError:
            pass

    filt = _safe(cfg, 'Acquisition', 'Filter')
    if filt and filt.lower() not in ('none', 'no filter'):
        rec['xray_filter'] = filt

    voxel = _num(_safe(cfg, 'Acquisition', 'Image Pixel Size (um)'))
    if voxel:
        rec['ct_voxel_size_um'] = voxel

    n_files = _num(_safe(cfg, 'Acquisition', 'Number of Files'))
    if n_files:
        rec['ct_number_images'] = str(int(float(n_files)))

    cols = _num(_safe(cfg, 'Acquisition', 'Number of Columns'))
    rows = _num(_safe(cfg, 'Acquisition', 'Number of Rows'))
    if cols:
        rec['image_width_pixels'] = str(int(float(cols)))
    if rows:
        rec['image_height_pixels'] = str(int(float(rows)))

    try:
        if cols and voxel:
            rec['image_width_real'] = f"{float(cols) * float(voxel) / 1000.0:.6f}"
        if rows and voxel:
            rec['image_height_real'] = f"{float(rows) * float(voxel) / 1000.0:.6f}"
    except ValueError:
        pass

    sod = _num(_safe(cfg, 'Acquisition', 'Object to Source (mm)'))
    sdd = _num(_safe(cfg, 'Acquisition', 'Camera to Source (mm)'))
    if sod:
        rec['Source_sample_distance'] = sod
    if sdd:
        rec['Source_detector_distance'] = sdd
    if sod and sdd:
        try:
            if float(sod) != 0:
                rec['Geometric_magnificiation'] = f"{float(sdd) / float(sod):.6f}"
        except (ValueError, ZeroDivisionError):
            pass

    binning = _safe(cfg, 'Acquisition', 'Camera binning')
    if binning:
        rec['detector_binning'] = binning

    exposure = _num(_safe(cfg, 'Acquisition', 'Exposure (ms)'))
    if exposure:
        rec['detector_capture_time'] = exposure

    avg_raw = _safe(cfg, 'Acquisition', 'Frame Averaging')
    if avg_raw:
        rec['detector_averaging'] = _parse_averaging(avg_raw)

    scan_dur = _safe(cfg, 'Acquisition', 'Scan duration')
    if scan_dur:
        rec['scan_time'] = _parse_skyscan_duration(scan_dur)

    study_dt = _safe(cfg, 'Acquisition', 'Study Date and Time')
    if study_dt:
        rec['start_time'] = _parse_study_datetime(study_dt)

    recon_dt = _safe(cfg, 'Reconstruction', 'Time and Date')
    if recon_dt:
        rec['end_time'] = _parse_study_datetime(recon_dt)

    rotation_step = _safe(cfg, 'Acquisition', 'Rotation Step (deg)')

    data_dir = _safe(cfg, 'Acquisition', 'Data directory')
    if data_dir:
        rec['file_path'] = data_dir

    vert_pos = _num(_safe(cfg, 'Acquisition', 'Vertical Object Position (mm)'))
    if vert_pos:
        rec['sample_z_start'] = vert_pos

    rotation = _safe(cfg, 'Acquisition', 'Image Rotation')
    if rotation:
        rec['sample_theta_start'] = rotation.strip()

    # -- [Reconstruction] extras (preserved for auditing) --
    recon = {}
    recon_keys = [
        ('Reconstruction Program', 'program'),
        ('Program Version', 'program_version'),
        ('Reconstruction engine', 'engine'),
        ('Engine version', 'engine_version'),
        ('Postalignment', 'postalignment'),
        ('Pixel Size (um)', 'recon_voxel_size_um'),
        ('Result File Type', 'result_file_type'),
        ('Result Image Width (pixels)', 'result_width_pixels'),
        ('Result Image Height (pixels)', 'result_height_pixels'),
        ('Sections Count', 'sections_count'),
        ('Reconstruction Angular Range (deg)', 'angular_range_deg'),
        ('Ring Artifact Correction', 'ring_artifact_correction'),
        ('Beam Hardening Correction (%)', 'beam_hardening_pct'),
        ('Smoothing', 'smoothing'),
        ('Filter type description', 'recon_filter'),
        ('Minimum for CS to Image Conversion', 'cs_min'),
        ('Maximum for CS to Image Conversion', 'cs_max'),
        ('Cone-beam Angle Horiz.(deg)', 'cone_beam_horiz_deg'),
        ('Cone-beam Angle Vert.(deg)', 'cone_beam_vert_deg'),
        ('CS Static Rotation (deg)', 'cs_static_rotation_deg'),
        ('Output Directory', 'output_directory'),
        ('Total reconstruction time (1145 slices) in seconds', 'total_recon_time_s'),
    ]
    for log_key, json_key in recon_keys:
        v = _safe(cfg, 'Reconstruction', log_key)
        if v:
            recon[json_key] = v

    # Also capture any total reconstruction time regardless of slice count
    if 'total_recon_time_s' not in recon and cfg.has_section('Reconstruction'):
        for opt in cfg.options('Reconstruction'):
            if opt.lower().startswith('total reconstruction time'):
                recon['total_recon_time_s'] = cfg.get('Reconstruction', opt).strip()
                break

    # -- [Acquisition] extras --
    acq_extra = {}
    acq_extra_keys = [
        ('Camera Pixel Size (um)', 'camera_pixel_size_um'),
        ('Source focus mode', 'source_focus_mode'),
        ('Rotation Step (deg)', 'rotation_step_deg'),
        ('Use 360 Rotation', 'use_360_rotation'),
        ('Rotation Direction', 'rotation_direction'),
        ('Scanning Trajectory', 'scanning_trajectory'),
        ('Type Of Motion', 'type_of_motion'),
        ('Type Of Scan', 'type_of_scan'),
        ('Flat Field Correction', 'flat_field_correction'),
        ('Random Movement', 'random_movement'),
        ('Number of connected scans', 'connected_scans'),
        ('Optical Axis (line)', 'optical_axis_line'),
        ('Filter assembly', 'filter_assembly'),
        ('External Filter', 'external_filter'),
        ('Image Format', 'image_format'),
        ('Depth (bits)', 'depth_bits'),
        ('Estimated scan time', 'estimated_scan_time'),
    ]
    for log_key, json_key in acq_extra_keys:
        v = _safe(cfg, 'Acquisition', log_key)
        if v:
            acq_extra[json_key] = v

    # -- Build output --
    rec['sha256'] = hashlib.sha256(input_path.read_bytes()).hexdigest()

    out = {k: rec.get(k, 'N/A') for k in COLUMN_ORDER}
    out['reconstruction'] = recon if recon else 'N/A'
    out['acquisition_extra'] = acq_extra if acq_extra else 'N/A'
    out['sha256'] = rec['sha256']
    out['source_path'] = str(output_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2 if pretty else None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=str)
    ap.add_argument("output", type=str)
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()
    parse_skyscan_file(Path(args.input), Path(args.output), pretty=args.pretty)


if __name__ == "__main__":
    main()
