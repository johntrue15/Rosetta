"""Base parser interface and common Rosetta JSON schema mapping."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, Optional


def init_rosetta_record(file_path: str) -> Dict[str, Any]:
    """Return a blank Rosetta-compatible metadata record with defaults."""
    fname = os.path.basename(file_path)
    fdir = os.path.dirname(os.path.abspath(file_path))
    abs_path = os.path.abspath(file_path)

    return {
        "file_name": fname,
        "file_hyperlink": "file:///" + abs_path.replace("\\", "/"),
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
        "start_time": "N/A",
        "end_time": "N/A",
        "txrm_file_path": abs_path,
        "file_path": fdir,
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
        "sample_theta_end": "N/A",
        "sample_theta_range": "N/A",
        "acquisition_mode": "N/A",
        "original_file_path": "N/A",
        "sample_name": "N/A",
        "camera_name": "N/A",
    }


def safe_float(val) -> Optional[float]:
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def compute_axis_range(start, end) -> Optional[str]:
    s = safe_float(start)
    e = safe_float(end)
    if s is not None and e is not None:
        return str(abs(e - s))
    return None


class BaseTXRMParser(ABC):
    """Abstract interface for TXRM parsing backends."""

    @abstractmethod
    def parse(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Parse a .txrm file and return a Rosetta-compatible metadata dict.

        Returns None on failure.
        """
