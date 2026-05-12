#!/usr/bin/env python3
"""
xml_to_json.py

Parse Nikon / XTek CT XML metadata files (*.ctinfo.xml, *.ctprofile.xml)
into the standard Rosetta JSON record format.

These XML files accompany *.xtekct files and contain additional metadata
such as axis positions, exposure settings, detector pixel size, and
volume-of-interest bounds that are not present in the INI-format xtekct
files.
"""

from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


def _text(el: ET.Element | None) -> str | None:
    """Return stripped text of an element, or None."""
    if el is None:
        return None
    return (el.text or "").strip() or None


def _parse_ctprofile(root: ET.Element, rec: Dict[str, Any]) -> None:
    """Extract metadata from a <CTProfile> XML root."""

    # --- X-ray settings ---------------------------------------------------
    xs = root.find("XraySettings")
    if xs is not None:
        kv = _text(xs.find("kV"))
        ua = _text(xs.find("uA"))
        if kv:
            try:
                rec["xray_tube_voltage"] = f"{float(kv):.3f}"
            except ValueError:
                rec["xray_tube_voltage"] = kv
        if ua:
            try:
                rec["xray_tube_current"] = f"{float(ua):.3f}"
            except ValueError:
                rec["xray_tube_current"] = ua
        try:
            rec["xray_tube_power"] = (
                f"{float(rec['xray_tube_voltage']) * float(rec['xray_tube_current']) * 1e-3:.3f}"
            )
        except (ValueError, KeyError):
            pass

    # --- X-ray head / tube ID ---------------------------------------------
    head = _text(root.find("XrayHead"))
    if head:
        rec["xray_tube_ID"] = head

    # --- Projections -------------------------------------------------------
    proj = _text(root.find("Projections"))
    if proj:
        try:
            rec["ct_number_images"] = str(int(float(proj)))
        except ValueError:
            rec["ct_number_images"] = proj

    # --- Detector pixel size -----------------------------------------------
    dps = _text(root.find("DetectorPixelSizeMM"))
    if dps:
        try:
            rec["detector_pixel_size_mm"] = f"{float(dps):.6f}"
        except ValueError:
            pass

    # --- Imaging conditions (exposure, binning) ----------------------------
    for tag in ("ImagingSettings", "ImagingConditions"):
        ic = root.find(f".//{tag}")
        if ic is None:
            ic = root.find(f".//ShadingCorrectionProfile/{tag}")
        if ic is not None:
            exp = ic.get("exposure")
            if exp:
                rec["detector_capture_time"] = exp
            binning = ic.get("binning")
            if binning:
                rec["detector_binning"] = binning
            # image dimensions from child elements
            sx = _text(ic.find("imageSizeX"))
            sy = _text(ic.find("imageSizeY"))
            if sx:
                rec["image_width_pixels"] = str(int(float(sx)))
            if sy:
                rec["image_height_pixels"] = str(int(float(sy)))
            break  # use first match

    # --- Frames per projection → detector averaging -----------------------
    fpp = _text(root.find("FramesPerProjection"))
    if fpp:
        rec["detector_averaging"] = fpp

    # --- Filter (from last GreyLevelTarget with positive kV) ---------------
    for target in root.findall(".//GreyLevelTargets/Target"):
        tkv = _text(target.find("kV"))
        if tkv and float(tkv) > 0:
            mat = _text(target.find("XrayFilterMaterial"))
            thick = _text(target.find("XrayFilterThickness"))
            if thick and mat:
                rec["xray_filter"] = f"{thick} mm {mat}"
            elif mat:
                rec["xray_filter"] = mat

    # --- Manipulator / axis positions --------------------------------------
    mp = root.find("ManipulatorPosition")
    if mp is not None:
        positions = [_text(ap) for ap in mp.findall("AxisPosition")]
        positions = [p for p in positions if p is not None]
        if positions:
            rec["manipulator_positions"] = ", ".join(positions)

    # --- Volume of interest → sample start/end ----------------------------
    voi = root.find("VolumeOfInterest")
    if voi is not None:
        for axis in ("X", "Y", "Z"):
            start_el = _text(voi.find(f"{axis}Start"))
            end_el = _text(voi.find(f"{axis}End"))
            if start_el is not None:
                rec[f"sample_{axis.lower()}_start"] = start_el
            if end_el is not None:
                rec[f"sample_{axis.lower()}_end"] = end_el
            if start_el is not None and end_el is not None:
                try:
                    rec[f"sample_{axis.lower()}_range"] = str(
                        float(end_el) - float(start_el)
                    )
                except ValueError:
                    pass

    # --- Profile / dataset name -------------------------------------------
    for tag in ("ProfileName", "DataSetName"):
        val = _text(root.find(tag))
        if val:
            rec["dataset_name"] = val
            break


def _parse_ctinfo(root: ET.Element, rec: Dict[str, Any]) -> None:
    """Extract metadata from an <Information> XML root (ctinfo.xml)."""
    ident = _text(root.find("Identifier"))
    if ident:
        rec["dataset_name"] = ident

    for elem in root.findall(".//Elements/Element"):
        tag = _text(elem.find("tag"))
        value = _text(elem.find("value"))
        if tag and value:
            # Store as extra metadata keyed by tag
            rec[f"ctinfo_{tag.replace(' ', '_').lower()}"] = value


def parse_xml_file(
    input_path: Path, output_path: Path, pretty: bool = False
) -> None:
    """
    Parse a Nikon CT XML metadata file and write a JSON record.

    Supports two XML variants:
    - *.ctprofile.xml  (root element <CTProfile>)
    - *.ctinfo.xml     (root element <Information>)
    """
    rec: Dict[str, Any] = {
        "file_name": input_path.name,
        "file_hyperlink": f"file:///{input_path.resolve()}".replace("\\", "/"),
        "ct_voxel_size_um": "N/A",
        "ct_objective": "N/A",
        "ct_number_images": "N/A",
        "Geometric_magnificiation": "N/A",
        "Source_detector_distance": "N/A",
        "Source_sample_distance": "N/A",
        "ct_optical_magnification": "N/A",
        "xray_tube_ID": "N/A",
        "xray_tube_voltage": "N/A",
        "xray_tube_power": "N/A",
        "xray_tube_current": "N/A",
        "xray_filter": "N/A",
        "detector_binning": "N/A",
        "detector_capture_time": "N/A",
        "detector_averaging": "N/A",
        "detector_skip": "N/A",
        "image_width_pixels": "N/A",
        "image_height_pixels": "N/A",
        "image_width_real": "N/A",
        "image_height_real": "N/A",
        "scan_time": "N/A",
        "start_time": datetime.fromtimestamp(input_path.stat().st_mtime).isoformat(),
        "end_time": datetime.now().isoformat(),
        "txrm_file_path": "N/A",
        "file_path": str(input_path.resolve()),
        "acquisition_successful": "Yes",
        "sample_x_start": "N/A",
        "sample_x_end": "N/A",
        "sample_x_range": "N/A",
        "sample_y_start": "N/A",
        "sample_y_end": "N/A",
        "sample_y_range": "N/A",
        "sample_z_start": "N/A",
        "sample_z_end": "N/A",
        "sample_z_range": "N/A",
        "sample_theta_start": "N/A",
    }

    tree = ET.parse(input_path)
    root = tree.getroot()

    # Strip namespace if present (e.g., xmlns:xsi)
    tag = root.tag.split("}")[-1] if "}" in root.tag else root.tag

    if tag == "CTProfile":
        _parse_ctprofile(root, rec)
    elif tag == "Information":
        _parse_ctinfo(root, rec)
    else:
        # Generic fallback: store root tag and try both parsers
        rec["xml_root_element"] = tag
        _parse_ctprofile(root, rec)
        _parse_ctinfo(root, rec)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=2 if pretty else None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=str)
    ap.add_argument("output", type=str)
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()
    parse_xml_file(Path(args.input), Path(args.output), pretty=args.pretty)


if __name__ == "__main__":
    main()
