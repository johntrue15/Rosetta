"""Olefile-based TXRM parser — works without proprietary Zeiss libraries.

Adapted from the AMNH fork of xrmreader (UChicago Argonne / dxchange, BSD-3).
"""

from __future__ import annotations

import logging
import struct
from datetime import datetime
from typing import Any, Dict, List, Optional

import olefile

from .base import BaseTXRMParser, init_rosetta_record, safe_float

logger = logging.getLogger(__name__)


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
    return result[0] if result is not None else None


def _ole_string(ole: olefile.OleFileIO, label: str, max_len: int = 260) -> Optional[str]:
    raw = _ole_value(ole, label, f"<{max_len}s")
    if raw is None:
        return None
    if isinstance(raw, bytes):
        try:
            raw = raw.decode("utf-8")
        except UnicodeDecodeError:
            raw = raw.decode("latin-1")
    return raw.split("\x00", 1)[0].strip() or None


def _ole_float_array(ole: olefile.OleFileIO, label: str) -> Optional[List[float]]:
    """Read an array of little-endian floats from an OLE stream."""
    if not ole.exists(label):
        return None
    data = ole.openstream(label).read()
    count = len(data) // 4
    if count == 0:
        return None
    try:
        return list(struct.unpack(f"<{count}f", data[: count * 4]))
    except struct.error:
        return None


def _ole_date_array(
    ole: olefile.OleFileIO, label: str, num_entries: int
) -> Optional[List[str]]:
    """Read an array of fixed-width date strings from an OLE stream."""
    if not ole.exists(label) or num_entries <= 0:
        return None
    data = ole.openstream(label).read()
    entry_size = len(data) // num_entries
    if entry_size == 0:
        return None
    dates: List[str] = []
    for i in range(num_entries):
        raw = data[i * entry_size : (i + 1) * entry_size]
        try:
            s = raw.decode("latin-1").split("\x00", 1)[0].strip()
        except Exception:
            s = ""
        dates.append(s)
    return dates if dates else None


def _parse_txrm_date(date_str: str) -> Optional[datetime]:
    """Parse a TXRM date string like ``MM/DD/YYYY HH:MM:SS.fff``."""
    if not date_str:
        return None
    try:
        base = date_str.split(".")[0]
        return datetime.strptime(base, "%m/%d/%Y %H:%M:%S")
    except (ValueError, IndexError):
        return None


class OlefileParser(BaseTXRMParser):
    """Parse .txrm files using the open-source olefile library."""

    def parse(self, file_path: str) -> Optional[Dict[str, Any]]:
        rec = init_rosetta_record(file_path)

        try:
            ole = olefile.OleFileIO(file_path)
        except Exception:
            logger.exception("Failed to open OLE file: %s", file_path)
            return None

        try:
            self._extract(ole, rec)
        except Exception:
            logger.exception("Error extracting metadata from %s", file_path)
            rec["acquisition_successful"] = "No"
        finally:
            ole.close()

        return rec

    def _extract(self, ole: olefile.OleFileIO, rec: Dict[str, Any]) -> None:
        num_images = _ole_value(ole, "ImageInfo/NoOfImages", "<I")
        if num_images is not None:
            rec["ct_number_images"] = str(num_images)

        width = _ole_value(ole, "ImageInfo/ImageWidth", "<I")
        height = _ole_value(ole, "ImageInfo/ImageHeight", "<I")
        if width is not None:
            rec["image_width_pixels"] = str(width)
        if height is not None:
            rec["image_height_pixels"] = str(height)

        pixel_size = _ole_value(ole, "ImageInfo/pixelsize", "<f")
        if pixel_size is not None and pixel_size > 0:
            rec["ct_voxel_size_um"] = str(pixel_size)
            if width is not None:
                rec["image_width_real"] = str(round(width * pixel_size, 4))
            if height is not None:
                rec["image_height_real"] = str(round(height * pixel_size, 4))

        obj_mag = _ole_value(ole, "AcquisitionSettings/ObjectiveMag", "<f")
        obj_id = _ole_value(ole, "AcquisitionSettings/ObjectiveID", "<I")
        if obj_mag is not None and obj_mag > 0:
            rec["ct_objective"] = f"{obj_mag:.1f}x"
            rounded_mag = round(obj_mag)
            rec["ct_optical_magnification"] = (
                "yes" if rounded_mag in (4, 20, 40) else "no"
            )
        elif obj_id is not None:
            rec["ct_objective"] = f"ObjectiveID-{obj_id}"

        sto_arr = _ole_float_array(ole, "ImageInfo/StoRADistance")
        dto_arr = _ole_float_array(ole, "ImageInfo/DtoRADistance")
        sto_ra = abs(sto_arr[0]) if sto_arr else None
        dto_ra = abs(dto_arr[0]) if dto_arr else None
        if sto_ra is not None and sto_ra > 0:
            rec["Source_sample_distance"] = str(round(sto_ra, 4))
        if sto_ra is not None and dto_ra is not None and (sto_ra + dto_ra) > 0:
            sdd = sto_ra + dto_ra
            rec["Source_detector_distance"] = str(round(sdd, 4))
            if sto_ra > 0:
                rec["Geometric_magnificiation"] = str(round(sdd / sto_ra, 6))

        voltage = safe_float(_ole_value(ole, "ImageInfo/Voltage", "<f"))
        current = safe_float(_ole_value(ole, "ImageInfo/Current", "<f"))
        power = safe_float(_ole_value(ole, "AcquisitionSettings/SrcPower", "<f"))
        if voltage is not None:
            rec["xray_tube_voltage"] = str(voltage)
        if current is not None:
            rec["xray_tube_current"] = str(current)
        if power is not None and power > 0:
            rec["xray_tube_power"] = str(power)
        elif voltage and current and voltage > 0 and current > 0:
            rec["xray_tube_power"] = str(round(voltage * current / 1e6, 4))

        filt = _ole_string(ole, "AcquisitionSettings/SourceFilterName")
        if filt:
            rec["xray_filter"] = filt

        binning = _ole_value(ole, "AcquisitionSettings/Binning", "<I")
        if binning is not None:
            rec["detector_binning"] = f"{binning}x{binning}" if binning > 0 else "1x1"

        exp_time = safe_float(_ole_value(ole, "AcquisitionSettings/ExpTime", "<f"))
        if exp_time is not None:
            rec["detector_capture_time"] = str(exp_time)

        avg = _ole_value(ole, "ImageInfo/NoOfImagesAveraged", "<I")
        if avg is not None:
            rec["detector_averaging"] = str(avg)

        frames_per = _ole_value(ole, "AcquisitionSettings/FramesPerImage", "<I")
        if frames_per is not None:
            rec["detector_skip"] = str(frames_per)

        facility = _ole_string(ole, "SampleInfo/Facility", max_len=50)
        if facility:
            rec["xray_tube_ID"] = facility

        camera = _ole_string(ole, "ImageInfo/CameraName", max_len=80)
        if camera:
            rec["camera_name"] = camera

        mode = _ole_string(ole, "AcquisitionSettings/AcqModeString")
        if mode:
            rec["acquisition_mode"] = mode

        orig_path = _ole_string(ole, "AcquisitionSettings/AcqFileName")
        if orig_path:
            rec["original_file_path"] = orig_path

        status = _ole_string(ole, "AcquisitionSettings/StatusString")
        if status:
            for line in status.replace("\t", "").split("\n"):
                line = line.strip()
                if line.lower().startswith("sample:"):
                    name = line.split(":", 1)[1].strip()
                    if name:
                        rec["sample_name"] = name
                    break

        n = int(num_images) if num_images else 0
        dates = _ole_date_array(ole, "ImageInfo/Date", n)
        if dates:
            dt_first = _parse_txrm_date(dates[0])
            dt_last = _parse_txrm_date(dates[-1])
            if dt_first is not None:
                rec["start_time"] = dt_first.isoformat()
            if dt_last is not None:
                rec["end_time"] = dt_last.isoformat()
            if dt_first is not None and dt_last is not None:
                rec["scan_time"] = str(round((dt_last - dt_first).total_seconds(), 2))

        angles = _ole_float_array(ole, "ImageInfo/Angles")
        if angles:
            rec["sample_theta_start"] = str(round(angles[0], 4))
            rec["sample_theta_end"] = str(round(angles[-1], 4))
            rec["sample_theta_range"] = str(round(abs(angles[-1] - angles[0]), 4))

        for axis, prefix in [("X", "sample_x"), ("Y", "sample_y"), ("Z", "sample_z")]:
            positions = _ole_float_array(ole, f"ImageInfo/{axis}Position")
            if positions:
                rec[f"{prefix}_start"] = str(round(positions[0], 4))
                rec[f"{prefix}_end"] = str(round(positions[-1], 4))
                rec[f"{prefix}_range"] = str(round(
                    abs(max(positions) - min(positions)), 4))
