"""
Tests for Bruker SkyScan .log file parsing.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from skyscan_to_json import parse_skyscan_file


class TestSkyScanParser:
    """Test suite for Bruker SkyScan log file parser."""

    def test_parse_real_skyscan_file(self, sample_skyscan_path, temp_dir):
        """Test parsing the real SkyScan log file from the repo."""
        if not sample_skyscan_path.exists():
            pytest.skip(f"Sample SkyScan file not found: {sample_skyscan_path}")

        output_path = temp_dir / "output.json"
        parse_skyscan_file(sample_skyscan_path, output_path, pretty=True)

        assert output_path.exists(), "Output JSON file should be created"

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert "file_name" in data
        assert data["file_name"].endswith(".log")
        assert data["ct_objective"] == "SkyScan2211"
        assert data["xray_tube_voltage"] == "70"
        assert data["xray_tube_current"] == "450"
        assert data["ct_voxel_size_um"] == "40.00"
        assert data["xray_filter"] == "0.5 mm Al"

    def test_parse_mock_skyscan_file(self, temp_dir, mock_skyscan_content):
        """Test parsing a mock SkyScan log file."""
        log_path = temp_dir / "test.log"
        log_path.write_text(mock_skyscan_content, encoding="utf-8")

        output_path = temp_dir / "output.json"
        parse_skyscan_file(log_path, output_path, pretty=True)

        assert output_path.exists()

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["ct_objective"] == "SkyScan2211"
        assert data["xray_tube_voltage"] == "70"
        assert data["xray_tube_current"] == "450"
        assert data["ct_voxel_size_um"] == "40.00"
        assert data["xray_filter"] == "0.5 mm Al"
        assert data["ct_number_images"] == "601"

    def test_voltage_and_current(self, temp_dir, mock_skyscan_content):
        """Test X-ray voltage and current extraction."""
        log_path = temp_dir / "test.log"
        log_path.write_text(mock_skyscan_content, encoding="utf-8")

        output_path = temp_dir / "output.json"
        parse_skyscan_file(log_path, output_path)

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["xray_tube_voltage"] == "70"
        assert data["xray_tube_current"] == "450"

    def test_power_calculation(self, temp_dir, mock_skyscan_content):
        """Test X-ray power = kV * uA / 1000."""
        log_path = temp_dir / "test.log"
        log_path.write_text(mock_skyscan_content, encoding="utf-8")

        output_path = temp_dir / "output.json"
        parse_skyscan_file(log_path, output_path)

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        power = float(data["xray_tube_power"])
        expected = 70 * 450 / 1000.0  # 31.5 W
        assert abs(power - expected) < 0.01, f"Expected {expected}W, got {power}"

    def test_geometric_magnification(self, temp_dir, mock_skyscan_content):
        """Test geometric magnification = Camera-to-Source / Object-to-Source."""
        log_path = temp_dir / "test.log"
        log_path.write_text(mock_skyscan_content, encoding="utf-8")

        output_path = temp_dir / "output.json"
        parse_skyscan_file(log_path, output_path)

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        mag = float(data["Geometric_magnificiation"])
        expected = 282.376 / 151.006
        assert abs(mag - expected) < 0.001, f"Expected {expected}, got {mag}"

    def test_distances(self, temp_dir, mock_skyscan_content):
        """Test source-to-object and source-to-detector distances."""
        log_path = temp_dir / "test.log"
        log_path.write_text(mock_skyscan_content, encoding="utf-8")

        output_path = temp_dir / "output.json"
        parse_skyscan_file(log_path, output_path)

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert abs(float(data["Source_sample_distance"]) - 151.006) < 0.001
        assert abs(float(data["Source_detector_distance"]) - 282.376) < 0.001

    def test_image_dimensions(self, temp_dir, mock_skyscan_content):
        """Test image width/height extraction."""
        log_path = temp_dir / "test.log"
        log_path.write_text(mock_skyscan_content, encoding="utf-8")

        output_path = temp_dir / "output.json"
        parse_skyscan_file(log_path, output_path)

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["image_width_pixels"] == "3776"
        assert data["image_height_pixels"] == "1536"

    def test_image_real_dimensions(self, temp_dir, mock_skyscan_content):
        """Test computed real image dimensions (pixels * voxel / 1000)."""
        log_path = temp_dir / "test.log"
        log_path.write_text(mock_skyscan_content, encoding="utf-8")

        output_path = temp_dir / "output.json"
        parse_skyscan_file(log_path, output_path)

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        width_real = float(data["image_width_real"])
        expected_w = 3776 * 40.0 / 1000.0  # 151.04 mm
        assert abs(width_real - expected_w) < 0.01

    def test_voxel_size(self, temp_dir, mock_skyscan_content):
        """Test voxel size extraction (already in µm)."""
        log_path = temp_dir / "test.log"
        log_path.write_text(mock_skyscan_content, encoding="utf-8")

        output_path = temp_dir / "output.json"
        parse_skyscan_file(log_path, output_path)

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert abs(float(data["ct_voxel_size_um"]) - 40.0) < 0.01

    def test_detector_binning(self, temp_dir, mock_skyscan_content):
        """Test camera binning extraction."""
        log_path = temp_dir / "test.log"
        log_path.write_text(mock_skyscan_content, encoding="utf-8")

        output_path = temp_dir / "output.json"
        parse_skyscan_file(log_path, output_path)

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["detector_binning"] == "1x1"

    def test_exposure_time(self, temp_dir, mock_skyscan_content):
        """Test exposure / capture time extraction."""
        log_path = temp_dir / "test.log"
        log_path.write_text(mock_skyscan_content, encoding="utf-8")

        output_path = temp_dir / "output.json"
        parse_skyscan_file(log_path, output_path)

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["detector_capture_time"] == "111"

    def test_frame_averaging(self, temp_dir, mock_skyscan_content):
        """Test frame averaging extraction from 'ON (2)' format."""
        log_path = temp_dir / "test.log"
        log_path.write_text(mock_skyscan_content, encoding="utf-8")

        output_path = temp_dir / "output.json"
        parse_skyscan_file(log_path, output_path)

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["detector_averaging"] == "2"

    def test_scan_duration_parsing(self, temp_dir, mock_skyscan_content):
        """Test scan duration conversion to seconds."""
        log_path = temp_dir / "test.log"
        log_path.write_text(mock_skyscan_content, encoding="utf-8")

        output_path = temp_dir / "output.json"
        parse_skyscan_file(log_path, output_path)

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 0h:18m:3s = 1083 seconds
        assert data["scan_time"] == "1083"

    def test_study_datetime_parsing(self, temp_dir, mock_skyscan_content):
        """Test study date/time is parsed to ISO-8601."""
        log_path = temp_dir / "test.log"
        log_path.write_text(mock_skyscan_content, encoding="utf-8")

        output_path = temp_dir / "output.json"
        parse_skyscan_file(log_path, output_path)

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["start_time"] == "2018-12-06T13:31:56"
        assert data["end_time"] == "2018-12-14T16:03:20"

    def test_file_path_from_data_directory(self, temp_dir, mock_skyscan_content):
        """Test file_path is set from the Data directory field."""
        log_path = temp_dir / "test.log"
        log_path.write_text(mock_skyscan_content, encoding="utf-8")

        output_path = temp_dir / "output.json"
        parse_skyscan_file(log_path, output_path)

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["file_path"] == "D:\\Data\\tanjid\\cisco\\cisco_sample_1"

    def test_xray_tube_id(self, temp_dir, mock_skyscan_content):
        """Test X-ray tube ID is built from source type and target."""
        log_path = temp_dir / "test.log"
        log_path.write_text(mock_skyscan_content, encoding="utf-8")

        output_path = temp_dir / "output.json"
        parse_skyscan_file(log_path, output_path)

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert "Xray-Worx" in data["xray_tube_ID"]
        assert "Tungsten" in data["xray_tube_ID"]

    def test_reconstruction_extras(self, temp_dir, mock_skyscan_content):
        """Test that reconstruction metadata is preserved."""
        log_path = temp_dir / "test.log"
        log_path.write_text(mock_skyscan_content, encoding="utf-8")

        output_path = temp_dir / "output.json"
        parse_skyscan_file(log_path, output_path)

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        recon = data["reconstruction"]
        assert recon["program"] == "NRecon"
        assert recon["engine"] == "InstaRecon"
        assert recon["ring_artifact_correction"] == "14"
        assert recon["beam_hardening_pct"] == "51"

    def test_acquisition_extras(self, temp_dir, mock_skyscan_content):
        """Test that extra acquisition metadata is preserved."""
        log_path = temp_dir / "test.log"
        log_path.write_text(mock_skyscan_content, encoding="utf-8")

        output_path = temp_dir / "output.json"
        parse_skyscan_file(log_path, output_path)

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        acq = data["acquisition_extra"]
        assert acq["rotation_step_deg"] == "0.600"
        assert acq["use_360_rotation"] == "YES"
        assert acq["scanning_trajectory"] == "ROUND"
        assert acq["type_of_motion"] == "STEP AND SHOOT"

    def test_sha256_present(self, temp_dir, mock_skyscan_content):
        """Test that SHA-256 hash is computed."""
        log_path = temp_dir / "test.log"
        log_path.write_text(mock_skyscan_content, encoding="utf-8")

        output_path = temp_dir / "output.json"
        parse_skyscan_file(log_path, output_path)

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert "sha256" in data
        assert len(data["sha256"]) == 64

    def test_output_directory_created(self, temp_dir, mock_skyscan_content):
        """Test that nested output directories are created."""
        log_path = temp_dir / "test.log"
        log_path.write_text(mock_skyscan_content, encoding="utf-8")

        output_path = temp_dir / "nested" / "deep" / "output.json"
        parse_skyscan_file(log_path, output_path)

        assert output_path.exists()

    def test_vertical_position_as_z_start(self, temp_dir, mock_skyscan_content):
        """Test vertical object position maps to sample_z_start."""
        log_path = temp_dir / "test.log"
        log_path.write_text(mock_skyscan_content, encoding="utf-8")

        output_path = temp_dir / "output.json"
        parse_skyscan_file(log_path, output_path)

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert abs(float(data["sample_z_start"]) - 64.0) < 0.01

    def test_theta_start_from_image_rotation(self, temp_dir, mock_skyscan_content):
        """Test image rotation maps to sample_theta_start."""
        log_path = temp_dir / "test.log"
        log_path.write_text(mock_skyscan_content, encoding="utf-8")

        output_path = temp_dir / "output.json"
        parse_skyscan_file(log_path, output_path)

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["sample_theta_start"] == "-0.3610"
