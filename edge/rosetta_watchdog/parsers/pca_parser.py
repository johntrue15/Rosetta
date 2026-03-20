"""PCA parser for Phoenix / Waygate .pca (INI-like) metadata files.

Ported from scripts/pca_to_json.py for use in the edge watchdog.
"""

from __future__ import annotations

import configparser
import logging
import ntpath
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from .base import BaseParser, init_rosetta_record

logger = logging.getLogger(__name__)


def _safe_get(cfg: configparser.RawConfigParser, section: str, option: str) -> Optional[str]:
    return cfg.get(section, option) if cfg.has_section(section) and cfg.has_option(section, option) else None


def _is_meaningful(s: Optional[str]) -> bool:
    return bool(s) and s.strip().upper() != "N/A"


class PcaParser(BaseParser):
    """Parses Phoenix .pca files into Rosetta-compatible metadata dicts."""

    def parse(self, file_path: str) -> Optional[Dict[str, Any]]:
        try:
            return self._do_parse(file_path)
        except Exception:
            logger.exception("Failed to parse PCA file: %s", file_path)
            return None

    def _do_parse(self, file_path: str) -> Dict[str, Any]:
        fp = Path(file_path)
        rec = init_rosetta_record(file_path)
        rec["ct_objective"] = "DXR-250"

        cfg = configparser.RawConfigParser()
        cfg.optionxform = str
        try:
            with fp.open("r", encoding="utf-8") as f:
                cfg.read_file(f)
        except UnicodeDecodeError:
            with fp.open("r", encoding="latin-1") as f:
                cfg.read_file(f)

        # Geometry
        vsx = _safe_get(cfg, "Geometry", "VoxelSizeX")
        if _is_meaningful(vsx):
            try:
                rec["ct_voxel_size_um"] = str(float(vsx) * 1000.0)
            except Exception:
                rec["ct_voxel_size_um"] = vsx
        for k_src, k_dst in [("Magnification", "Geometric_magnificiation"),
                              ("FDD", "Source_detector_distance"),
                              ("FOD", "Source_sample_distance")]:
            v = _safe_get(cfg, "Geometry", k_src)
            if _is_meaningful(v):
                rec[k_dst] = v

        # CT
        v = _safe_get(cfg, "CT", "NumberImages")
        if _is_meaningful(v):
            rec["ct_number_images"] = v
        v = _safe_get(cfg, "CT", "ScanTimeCmpl")
        if _is_meaningful(v):
            rec["scan_time"] = v

        # X-ray
        xid = _safe_get(cfg, "Xray", "Name")
        if _is_meaningful(xid):
            rec["xray_tube_ID"] = xid
        xkv = _safe_get(cfg, "Xray", "Voltage")
        xua = _safe_get(cfg, "Xray", "Current")
        if _is_meaningful(xkv):
            rec["xray_tube_voltage"] = xkv
        if _is_meaningful(xua):
            rec["xray_tube_current"] = xua
        try:
            if _is_meaningful(xkv) and _is_meaningful(xua):
                rec["xray_tube_power"] = str((float(xkv) * float(xua)) / 1000.0)
        except Exception:
            pass
        xf = _safe_get(cfg, "Xray", "Filter")
        if _is_meaningful(xf):
            rec["xray_filter"] = xf

        # Detector
        binning = _safe_get(cfg, "Detector", "Binning")
        if _is_meaningful(binning):
            try:
                b = int(binning)
                rec["detector_binning"] = "1x1" if b == 0 else f"{2**b}x{2**b}"
            except Exception:
                rec["detector_binning"] = binning
        for sec, key in [("Detector", "TimingVal"),
                          ("Detector", "Avg"),
                          ("Detector", "Skip")]:
            v = _safe_get(cfg, sec, key)
            dst = {"TimingVal": "detector_capture_time",
                   "Avg": "detector_averaging",
                   "Skip": "detector_skip"}[key]
            if _is_meaningful(v):
                rec[dst] = v

        # Image
        dimx = _safe_get(cfg, "Image", "DimX")
        dimy = _safe_get(cfg, "Image", "DimY")
        if _is_meaningful(dimx):
            rec["image_width_pixels"] = dimx
        if _is_meaningful(dimy):
            rec["image_height_pixels"] = dimy
        try:
            if _is_meaningful(dimx) and rec["ct_voxel_size_um"] != "N/A":
                rec["image_width_real"] = str(float(dimx) * float(rec["ct_voxel_size_um"]) / 1000.0)
            if _is_meaningful(dimy) and rec["ct_voxel_size_um"] != "N/A":
                rec["image_height_real"] = str(float(dimy) * float(rec["ct_voxel_size_um"]) / 1000.0)
        except Exception:
            pass

        # CNC axes
        for axis, dsts in [("CNC_0", ("sample_x_start", "sample_x_end")),
                            ("CNC_1", ("sample_y_start", "sample_y_end")),
                            ("CNC_2", ("sample_z_start", "sample_z_end"))]:
            lp = _safe_get(cfg, axis, "LoadPos")
            ap = _safe_get(cfg, axis, "AcqPos")
            if _is_meaningful(lp):
                rec[dsts[0]] = lp
            if _is_meaningful(ap):
                rec[dsts[1]] = ap
        v = _safe_get(cfg, "CNC_3", "AcqPos")
        if _is_meaningful(v):
            rec["sample_theta_start"] = v
        try:
            if rec["sample_x_start"] != "N/A" and rec["sample_x_end"] != "N/A":
                rec["sample_x_range"] = str(abs(float(rec["sample_x_end"]) - float(rec["sample_x_start"])))
            if rec["sample_y_start"] != "N/A" and rec["sample_y_end"] != "N/A":
                rec["sample_y_range"] = str(abs(float(rec["sample_y_end"]) - float(rec["sample_y_start"])))
            if rec["sample_z_start"] != "N/A" and rec["sample_z_end"] != "N/A":
                rec["sample_z_range"] = str(abs(float(rec["sample_z_end"]) - float(rec["sample_z_start"])))
        except Exception:
            pass

        # Calibration images
        calib = {}
        for key in ("MGainPoints", "Avg", "Skip", "EnableAutoAcq", "MGainVoltage",
                     "MGainCurrent", "MGainFilter", "GainImg", "MGainImg", "OffsetImg", "DefPixelImg"):
            val = _safe_get(cfg, "CalibImages", key)
            if _is_meaningful(val):
                calib[key] = val
        candidate = None
        for k in ("MGainImg", "GainImg", "OffsetImg", "DefPixelImg"):
            if _is_meaningful(calib.get(k)):
                candidate = calib[k].strip()
                break
        if _is_meaningful(candidate):
            folder = ntpath.dirname(candidate)
            if _is_meaningful(folder):
                calib["calib_folder_path"] = folder
                rec["file_path"] = folder

        if calib:
            rec["calib_images"] = calib

        return rec
