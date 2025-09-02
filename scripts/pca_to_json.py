#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import configparser
import json
import logging
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("pca_json_parser")

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

def init_record(filepath: Path) -> Dict[str, str]:
    return {k: 'N/A' for k in COLUMN_ORDER}

def _safe_read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")
    except Exception:
        # As last resort return base64 so caller can still inspect
        raw = path.read_bytes()
        return base64.b64encode(raw).decode("ascii")

def parse_pca_file(filepath: Path) -> Dict[str, str]:
    """
    Parse a single .pca file into a normalized dict (keys in COLUMN_ORDER).
    This is the function parse_any.py will import and call.
    """
    data = init_record(filepath)
    try:
        cfg = configparser.RawConfigParser()
        cfg.optionxform = str  # preserve case

        txt = _safe_read_text(filepath)
        from io import StringIO
        cfg.read_file(StringIO(txt))

        # File metadata
        data['file_name'] = filepath.name
        data['file_path'] = str(filepath.resolve())
        data['file_hyperlink'] = f'file:///{filepath.resolve()}'.replace("\\", "/")

        # Geometry
        if cfg.has_section('Geometry'):
            if cfg.has_option('Geometry', 'VoxelSizeX'):
                try:
                    voxel_mm = float(cfg.get('Geometry', 'VoxelSizeX'))  # mm
                    data['ct_voxel_size_um'] = str(voxel_mm * 1000.0)    # μm
                except Exception:
                    pass
            if cfg.has_option('Geometry', 'Magnification'):
                data['Geometric_magnificiation'] = cfg.get('Geometry', 'Magnification')
            if cfg.has_option('Geometry', 'FDD'):
                data['Source_detector_distance'] = cfg.get('Geometry', 'FDD')
            if cfg.has_option('Geometry', 'FOD'):
                data['Source_sample_distance'] = cfg.get('Geometry', 'FOD')

        # Objective (per original script)
        data['ct_objective'] = 'DXR-250'

        # CT
        if cfg.has_section('CT'):
            if cfg.has_option('CT', 'NumberImages'):
                data['ct_number_images'] = cfg.get('CT', 'NumberImages')
            if cfg.has_option('CT', 'ScanTimeCmpl'):
                data['scan_time'] = cfg.get('CT', 'ScanTimeCmpl')

        # Xray
        if cfg.has_section('Xray'):
            if cfg.has_option('Xray', 'Name'):
                data['xray_tube_ID'] = cfg.get('Xray', 'Name')
            if cfg.has_option('Xray', 'Voltage'):
                data['xray_tube_voltage'] = cfg.get('Xray', 'Voltage')
            if cfg.has_option('Xray', 'Current'):
                data['xray_tube_current'] = cfg.get('Xray', 'Current')
            # simple power calc if both parsable
            try:
                v = float(cfg.get('Xray', 'Voltage')) if cfg.has_option('Xray', 'Voltage') else None
                i = float(cfg.get('Xray', 'Current')) if cfg.has_option('Xray', 'Current') else None
                if v is not None and i is not None:
                    data['xray_tube_power'] = str((v * i) / 1000.0)  # W
            except Exception:
                pass
            if cfg.has_option('Xray', 'Filter'):
                data['xray_filter'] = cfg.get('Xray', 'Filter')

        # Detector
        if cfg.has_section('Detector'):
            if cfg.has_option('Detector', 'Binning'):
                try:
                    b_int = int(cfg.get('Detector', 'Binning'))
                    data['detector_binning'] = '1x1' if b_int == 0 else f'{2**b_int}x{2**b_int}'
                except Exception:
                    data['detector_binning'] = cfg.get('Detector', 'Binning')
            if cfg.has_option('Detector', 'TimingVal'):
                data['detector_capture_time'] = cfg.get('Detector', 'TimingVal')
            if cfg.has_option('Detector', 'Avg'):
                data['detector_averaging'] = cfg.get('Detector', 'Avg')
            if cfg.has_option('Detector', 'Skip'):
                data['detector_skip'] = cfg.get('Detector', 'Skip')

        # Image
        if cfg.has_section('Image'):
            if cfg.has_option('Image', 'DimX'):
                data['image_width_pixels'] = cfg.get('Image', 'DimX')
            if cfg.has_option('Image', 'DimY'):
                data['image_height_pixels'] = cfg.get('Image', 'DimY')
            try:
                if cfg.has_option('Image', 'DimX') and data['ct_voxel_size_um'] != 'N/A':
                    data['image_width_real'] = str(float(cfg.get('Image', 'DimX')) * float(data['ct_voxel_size_um']) / 1000.0)
                if cfg.has_option('Image', 'DimY') and data['ct_voxel_size_um'] != 'N/A':
                    data['image_height_real'] = str(float(cfg.get('Image', 'DimY')) * float(data['ct_voxel_size_um']) / 1000.0)
            except Exception:
                pass

        # CNC axes
        if cfg.has_section('CNC_0'):
            if cfg.has_option('CNC_0', 'LoadPos'):
                data['sample_x_start'] = cfg.get('CNC_0', 'LoadPos')
            if cfg.has_option('CNC_0', 'AcqPos'):
                data['sample_x_end'] = cfg.get('CNC_0', 'AcqPos')
        if cfg.has_section('CNC_1'):
            if cfg.has_option('CNC_1', 'LoadPos'):
                data['sample_y_start'] = cfg.get('CNC_1', 'LoadPos')
            if cfg.has_option('CNC_1', 'AcqPos'):
                data['sample_y_end'] = cfg.get('CNC_1', 'AcqPos')
        if cfg.has_section('CNC_2'):
            if cfg.has_option('CNC_2', 'LoadPos'):
                data['sample_z_start'] = cfg.get('CNC_2', 'LoadPos')
            if cfg.has_option('CNC_2', 'AcqPos'):
                data['sample_z_end'] = cfg.get('CNC_2', 'AcqPos')
        if cfg.has_section('CNC_3'):
            if cfg.has_option('CNC_3', 'AcqPos'):
                data['sample_theta_start'] = cfg.get('CNC_3', 'AcqPos')

        # Ranges
        try:
            if data['sample_x_start'] != 'N/A' and data['sample_x_end'] != 'N/A':
                data['sample_x_range'] = str(abs(float(data['sample_x_end']) - float(data['sample_x_start'])))
            if data['sample_y_start'] != 'N/A' and data['sample_y_end'] != 'N/A':
                data['sample_y_range'] = str(abs(float(data['sample_y_end']) - float(data['sample_y_start'])))
            if data['sample_z_start'] != 'N/A' and data['sample_z_end'] != 'N/A':
                data['sample_z_range'] = str(abs(float(data['sample_z_end']) - float(data['sample_z_start'])))
        except Exception:
            pass

        # Times
        try:
            data['start_time'] = datetime.fromtimestamp(filepath.stat().st_mtime).isoformat()
        except Exception:
            data['start_time'] = datetime.now().isoformat()
        data['end_time'] = datetime.now().isoformat()

        data['acquisition_successful'] = 'Yes'
    except Exception as e:
        logger.error(f"Error reading {filepath}: {e}")
        data['acquisition_successful'] = 'No'
        data['file_name'] = filepath.name
        data['file_path'] = str(filepath.resolve())
    # Ensure only ordered keys
    return {k: data.get(k, 'N/A') for k in COLUMN_ORDER}

def collect_files(input_path: Path) -> Tuple[List[Path], Path, str]:
    """Return (files_to_process, output_dir, output_basename)."""
    if not input_path.exists():
        raise FileNotFoundError(f"INPUT_PATH not found: {input_path}")

    if input_path.is_dir():
        files = list(input_path.rglob("*.pca")) + list(input_path.rglob("*.PCA"))
        output_dir = input_path
        base = "combined_pca_data"
        logger.info(f"Scanning directory: {input_path}")
    elif input_path.is_file():
        if input_path.suffix.lower() != ".pca":
            raise ValueError(f"INPUT_PATH is a file but not a .pca: {input_path}")
        files = [input_path]
        output_dir = input_path.parent
        base = f"{input_path.stem}_pca"
        logger.info(f"Parsing single file: {input_path.name}")
    else:
        raise ValueError(f"Unsupported path type: {input_path}")

    return files, output_dir, base

def write_json(path: Path, obj, pretty: bool = True):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2 if pretty else None)

def main():
    ap = argparse.ArgumentParser(description="PCA → JSON parser (single file or directory).")
    ap.add_argument("input_path", help="Path to a .pca file OR a directory containing .pca files")
    ap.add_argument("-o", "--output", help="(Single file mode) explicit output JSON path. Default: <file>.pca.json appended")
    ap.add_argument("--outdir", help="(Directory mode) where to write combined outputs. Default: input directory")
    ap.add_argument("--jsonl", action="store_true", help="Also write a JSONL alongside the combined JSON (directory mode)")
    ap.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    args = ap.parse_args()

    ip = Path(args.input_path).resolve()

    files, output_dir, base = collect_files(ip)
    if args.outdir:
        output_dir = Path(args.outdir).resolve()

    if ip.is_file():
        # SINGLE FILE MODE → one JSON dict
        rec = parse_pca_file(ip)
        if args.output:
            out_path = Path(args.output).resolve()
        else:
            # Append .json to the original filename (keep original extension)
            out_path = output_dir / f"{ip.name}.json"
        write_json(out_path, rec, pretty=args.pretty)
        print(out_path)
        return

    # DIRECTORY MODE → combined array + optional JSONL
    records: List[Dict[str, str]] = []
    for fp in files:
        logger.info(f"Parsing: {fp}")
        rec = parse_pca_file(fp)
        records.append(rec)

    # De-dupe by file_path, keep last seen
    dedup = {}
    for r in records:
        dedup[r.get("file_path", "")] = r
    combined = list(dedup.values())
    combined.sort(key=lambda r: r.get("file_name", ""))

    out_json = output_dir / f"{base}.json"
    write_json(out_json, combined, pretty=True if args.pretty else True)

    if args.jsonl:
        out_jsonl = output_dir / f"{base}.jsonl"
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        with out_jsonl.open("w", encoding="utf-8") as f:
            for r in combined:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(out_json)

if __name__ == "__main__":
    main()
