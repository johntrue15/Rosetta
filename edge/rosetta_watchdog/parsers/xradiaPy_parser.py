"""XradiaPy-based TXRM parser — requires the proprietary Zeiss Xradia Software Suite.

Adapted from the X-radia-metadata-fork MetadataExtractor, modernised to Python 3.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from XradiaPy import Data  # type: ignore[import-untyped]

from .base import BaseTXRMParser, compute_axis_range, init_rosetta_record, safe_float

logger = logging.getLogger(__name__)


class XradiaPyParser(BaseTXRMParser):
    """Parse .txrm files using the Zeiss XradiaPy API for full per-projection data."""

    def parse(self, file_path: str) -> Optional[Dict[str, Any]]:
        rec = init_rosetta_record(file_path)
        dataset = Data.XRMData.XrmBasicDataSet()

        try:
            dataset.ReadFile(str(file_path).replace("\\", "/"))
        except Exception:
            logger.exception("XradiaPy failed to read %s", file_path)
            return None

        if not dataset.IsInitializedCorrectly():
            logger.error("File not initialised correctly: %s", file_path)
            rec["acquisition_successful"] = "No"
            return rec

        try:
            self._extract(dataset, rec)
        except Exception:
            logger.exception("Error extracting metadata via XradiaPy for %s", file_path)
            rec["acquisition_successful"] = "No"

        return rec

    def _extract(self, ds, rec: Dict[str, Any]) -> None:
        rec["ct_objective"] = str(ds.GetObjective()) if ds.GetObjective() else "N/A"
        pixel_size = safe_float(ds.GetPixelSize())
        if pixel_size is not None and pixel_size > 0:
            rec["ct_voxel_size_um"] = str(pixel_size)

        voltage = safe_float(ds.GetVoltage())
        power = safe_float(ds.GetPower())
        if voltage is not None:
            rec["xray_tube_voltage"] = str(voltage)
        if power is not None and power > 0:
            rec["xray_tube_power"] = str(power)
            if voltage and voltage > 0:
                rec["xray_tube_current"] = str(round((power / voltage) * 1e6, 2))

        filt = ds.GetFilter()
        if filt:
            rec["xray_filter"] = str(filt)

        binning = ds.GetBinning()
        if binning is not None:
            rec["detector_binning"] = str(binning)

        width = ds.GetWidth()
        height = ds.GetHeight()
        if width:
            rec["image_width_pixels"] = str(width)
        if height:
            rec["image_height_pixels"] = str(height)
        if pixel_size and pixel_size > 0:
            if width:
                rec["image_width_real"] = str(round(width * pixel_size, 2))
            if height:
                rec["image_height_real"] = str(round(height * pixel_size, 2))

        obj_str = str(ds.GetObjective()).lower() if ds.GetObjective() else ""
        rec["ct_optical_magnification"] = "yes" if obj_str in ("4x", "20x", "40x") else "no"

        num_projections = ds.GetProjections()
        rec["ct_number_images"] = str(num_projections) if num_projections else "N/A"

        if not num_projections or num_projections <= 0:
            return

        # Per-projection data for first/last to get timing + axis positions
        try:
            first_exposure = safe_float(ds.GetExposure(0))
            if first_exposure is not None:
                rec["detector_capture_time"] = str(first_exposure)
        except Exception:
            pass

        try:
            images_per = ds.GetImagesPerProjection(0)
            if images_per is not None:
                rec["detector_averaging"] = str(images_per)
        except Exception:
            pass

        # Geometry from first projection
        try:
            sto_ra = safe_float(ds.GetSourceToRADistance(0))
            dto_ra = safe_float(ds.GetDetectorToRADistance(0))
            if sto_ra is not None and sto_ra > 0:
                rec["Source_sample_distance"] = str(round(sto_ra, 4))
            if sto_ra is not None and dto_ra is not None and (sto_ra + dto_ra) > 0:
                sdd = sto_ra + dto_ra
                rec["Source_detector_distance"] = str(round(sdd, 4))
                if sto_ra > 0:
                    rec["Geometric_magnificiation"] = str(round(sdd / sto_ra, 6))
        except Exception:
            pass

        # Timing
        try:
            start_date = str(ds.GetDate(0))
            end_date = str(ds.GetDate(num_projections - 1))
            if start_date:
                rec["start_time"] = start_date
            if end_date:
                rec["end_time"] = end_date
        except Exception:
            pass

        # Axis positions from first and last projections
        self._extract_axis_positions(ds, rec, num_projections)

    def _extract_axis_positions(self, ds, rec: Dict[str, Any], num_proj: int) -> None:
        axis_mapping = {
            "Sample X": ("sample_x_start", "sample_x_end", "sample_x_range"),
            "Sample Y": ("sample_y_start", "sample_y_end", "sample_y_range"),
            "Sample Z": ("sample_z_start", "sample_z_end", "sample_z_range"),
            "Sample Theta": ("sample_theta_start", None, None),
        }

        try:
            axis_names = ds.GetAxesNames()
        except Exception:
            return

        for axis in axis_names:
            clean = axis.replace(" ", "_")
            mapped = None
            for key, fields in axis_mapping.items():
                if key.replace(" ", "_") == clean:
                    mapped = fields
                    break

            if mapped is None:
                continue

            start_key, end_key, range_key = mapped

            try:
                start_val = ds.GetAxisPosition(0, axis)
                if start_key and start_val is not None:
                    rec[start_key] = str(start_val)

                if end_key and num_proj > 1:
                    end_val = ds.GetAxisPosition(num_proj - 1, axis)
                    if end_val is not None:
                        rec[end_key] = str(end_val)
                    if range_key:
                        rng = compute_axis_range(start_val, end_val)
                        if rng is not None:
                            rec[range_key] = rng
            except Exception:
                logger.debug("Could not read axis %s", axis, exc_info=True)
