"""
Tests for PCA file parsing (Phoenix/Waygate format).
"""

import json
import sys
from pathlib import Path

import pytest

# Import the parser
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from pca_to_json import parse_pca_file, init_record, safe_get


class TestPCAParser:
    """Test suite for PCA file parser."""

    def test_parse_real_pca_file(self, sample_pca_path, temp_dir):
        """Test parsing a real PCA file from the repo."""
        if not sample_pca_path.exists():
            pytest.skip(f"Sample PCA file not found: {sample_pca_path}")

        output_path = temp_dir / "output.json"
        parse_pca_file(sample_pca_path, output_path, pretty=True)

        assert output_path.exists(), "Output JSON file should be created"

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Verify required fields are present
        assert "file_name" in data
        assert "ct_voxel_size_um" in data
        assert "sha256" in data
        assert "source_path" in data

        # Verify specific values from the known file
        assert data["file_name"] == "Amazon echo 40 micron.pca"
        assert data["ct_number_images"] == "1800"
        assert data["xray_tube_voltage"] == "200"
        assert data["xray_tube_current"] == "200"
        assert data["xray_filter"] == "0.1Cu"
        assert data["detector_binning"] == "1x1"  # Binning=0 -> 1x1

    def test_parse_mock_pca_file(self, temp_dir, mock_pca_content):
        """Test parsing a mock PCA file."""
        # Create mock PCA file
        pca_path = temp_dir / "test.pca"
        pca_path.write_text(mock_pca_content, encoding="utf-8")

        output_path = temp_dir / "output.json"
        parse_pca_file(pca_path, output_path, pretty=True)

        assert output_path.exists()

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Verify extracted values
        assert data["ct_number_images"] == "1800"
        assert data["xray_tube_voltage"] == "200"
        assert data["xray_tube_current"] == "200"
        assert data["xray_filter"] == "0.1Cu"
        assert data["detector_binning"] == "1x1"
        assert data["image_width_pixels"] == "2024"
        assert data["image_height_pixels"] == "2024"

        # Verify voxel size conversion (mm to µm)
        voxel_um = float(data["ct_voxel_size_um"])
        assert 40.0 < voxel_um < 41.0, f"Expected ~40.65 µm, got {voxel_um}"

        # Verify power calculation (kV * µA / 1000)
        power = float(data["xray_tube_power"])
        assert power == 40.0, f"Expected 40W, got {power}"

        # Verify calibration path extraction
        assert "calib_images" in data
        assert data["calib_images"]["MGainImg"] == "S:\\CT_DATA\\FICS\\test\\calibration.tif"
        assert data["file_path"] == "S:\\CT_DATA\\FICS\\test"

    def test_geometric_magnification(self, temp_dir, mock_pca_content):
        """Test that geometric magnification is correctly extracted."""
        pca_path = temp_dir / "test.pca"
        pca_path.write_text(mock_pca_content, encoding="utf-8")

        output_path = temp_dir / "output.json"
        parse_pca_file(pca_path, output_path)

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["Geometric_magnificiation"] == "4.91919266"
        assert data["Source_detector_distance"] == "802.77534791"
        assert data["Source_sample_distance"] == "163.19250000"

    def test_cnc_positions(self, temp_dir, mock_pca_content):
        """Test that CNC positions are correctly extracted."""
        pca_path = temp_dir / "test.pca"
        pca_path.write_text(mock_pca_content, encoding="utf-8")

        output_path = temp_dir / "output.json"
        parse_pca_file(pca_path, output_path)

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["sample_x_start"] == "-149.993687"
        assert data["sample_x_end"] == "0.000000"
        assert data["sample_theta_start"] == "0.000000"

    def test_sha256_hash_generated(self, temp_dir, mock_pca_content):
        """Test that SHA256 hash is generated for deduplication."""
        pca_path = temp_dir / "test.pca"
        pca_path.write_text(mock_pca_content, encoding="utf-8")

        output_path = temp_dir / "output.json"
        parse_pca_file(pca_path, output_path)

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert "sha256" in data
        assert len(data["sha256"]) == 64  # SHA256 hex digest length

    def test_output_directory_created(self, temp_dir, mock_pca_content):
        """Test that output directories are created if they don't exist."""
        pca_path = temp_dir / "test.pca"
        pca_path.write_text(mock_pca_content, encoding="utf-8")

        # Nested output path that doesn't exist
        output_path = temp_dir / "nested" / "deep" / "output.json"
        parse_pca_file(pca_path, output_path)

        assert output_path.exists()

    def test_binning_conversion(self, temp_dir):
        """Test different binning value conversions."""
        for binning_val, expected in [("0", "1x1"), ("1", "2x2"), ("2", "4x4")]:
            content = f"""[General]
Version=2.8.2

[Detector]
Binning={binning_val}
"""
            pca_path = temp_dir / f"test_binning_{binning_val}.pca"
            pca_path.write_text(content, encoding="utf-8")

            output_path = temp_dir / f"output_{binning_val}.json"
            parse_pca_file(pca_path, output_path)

            with open(output_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            assert data["detector_binning"] == expected, f"Binning {binning_val} should be {expected}"
