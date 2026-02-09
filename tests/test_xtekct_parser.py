"""
Tests for XTEKCT file parsing (XTek/Nikon format).
"""

import json
import sys
from pathlib import Path

import pytest

# Import the parser
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from xtekct_to_json import parse_xtekct_file


class TestXTEKCTParser:
    """Test suite for XTEKCT file parser."""

    def test_parse_real_xtekct_file(self, sample_xtekct_path, temp_dir):
        """Test parsing a real XTEKCT file from the repo."""
        if not sample_xtekct_path.exists():
            pytest.skip(f"Sample XTEKCT file not found: {sample_xtekct_path}")

        output_path = temp_dir / "output.json"
        parse_xtekct_file(sample_xtekct_path, output_path, pretty=True)

        assert output_path.exists(), "Output JSON file should be created"

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Verify required fields are present
        assert "file_name" in data
        assert data["file_name"].endswith(".xtekct")

        # Verify specific values from the known file
        assert data["xray_tube_voltage"] == "216.000"
        assert data["xray_tube_current"] == "229.000"
        assert data["ct_number_images"] == "2500"
        assert data["xray_filter"] == "1.0 mm Copper"

    def test_parse_mock_xtekct_file(self, temp_dir, mock_xtekct_content):
        """Test parsing a mock XTEKCT file."""
        xtekct_path = temp_dir / "test.xtekct"
        xtekct_path.write_text(mock_xtekct_content, encoding="utf-8")

        output_path = temp_dir / "output.json"
        parse_xtekct_file(xtekct_path, output_path, pretty=True)

        assert output_path.exists()

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Verify extracted values
        assert data["xray_tube_voltage"] == "216.000"
        assert data["xray_tube_current"] == "229.000"
        assert data["ct_number_images"] == "2500"
        assert data["xray_filter"] == "1.0 mm Copper"

    def test_voxel_size_conversion(self, temp_dir, mock_xtekct_content):
        """Test voxel size conversion from mm to µm."""
        xtekct_path = temp_dir / "test.xtekct"
        xtekct_path.write_text(mock_xtekct_content, encoding="utf-8")

        output_path = temp_dir / "output.json"
        parse_xtekct_file(xtekct_path, output_path)

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Voxel size should be converted from mm to µm
        # VoxelSizeX=0.049751 mm = 49.751 µm
        voxel_um = float(data["ct_voxel_size_um"])
        assert abs(voxel_um - 49.751) < 0.1, f"Expected ~49.751 µm, got {voxel_um}"

    def test_geometric_magnification_calculation(self, temp_dir, mock_xtekct_content):
        """Test geometric magnification is calculated correctly."""
        xtekct_path = temp_dir / "test.xtekct"
        xtekct_path.write_text(mock_xtekct_content, encoding="utf-8")

        output_path = temp_dir / "output.json"
        parse_xtekct_file(xtekct_path, output_path)

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Magnification = SrcToDetector / SrcToObject
        # = 735.7075 / 183.012 ≈ 4.02
        mag = float(data["Geometric_magnificiation"])
        expected_mag = 735.7075 / 183.012
        assert abs(mag - expected_mag) < 0.001, f"Expected {expected_mag}, got {mag}"

    def test_power_calculation(self, temp_dir, mock_xtekct_content):
        """Test X-ray power calculation."""
        xtekct_path = temp_dir / "test.xtekct"
        xtekct_path.write_text(mock_xtekct_content, encoding="utf-8")

        output_path = temp_dir / "output.json"
        parse_xtekct_file(xtekct_path, output_path)

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Power = kV * µA * 1e-3 = 216 * 229 * 0.001 = 49.464 W
        power = float(data["xray_tube_power"])
        expected = 216 * 229 * 0.001
        assert abs(power - expected) < 0.01, f"Expected {expected}W, got {power}"

    def test_image_dimensions(self, temp_dir, mock_xtekct_content):
        """Test image dimension extraction."""
        xtekct_path = temp_dir / "test.xtekct"
        xtekct_path.write_text(mock_xtekct_content, encoding="utf-8")

        output_path = temp_dir / "output.json"
        parse_xtekct_file(xtekct_path, output_path)

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["image_width_pixels"] == "1150"
        assert data["image_height_pixels"] == "1939"

    def test_distances_extracted(self, temp_dir, mock_xtekct_content):
        """Test source-to-detector and source-to-object distances."""
        xtekct_path = temp_dir / "test.xtekct"
        xtekct_path.write_text(mock_xtekct_content, encoding="utf-8")

        output_path = temp_dir / "output.json"
        parse_xtekct_file(xtekct_path, output_path)

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        sdd = float(data["Source_detector_distance"])
        sod = float(data["Source_sample_distance"])

        assert abs(sdd - 735.7075) < 0.001
        assert abs(sod - 183.012) < 0.001

    def test_initial_angle(self, temp_dir, mock_xtekct_content):
        """Test initial angle extraction."""
        xtekct_path = temp_dir / "test.xtekct"
        xtekct_path.write_text(mock_xtekct_content, encoding="utf-8")

        output_path = temp_dir / "output.json"
        parse_xtekct_file(xtekct_path, output_path)

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["sample_theta_start"] == "0.0"

    def test_filter_material_and_thickness(self, temp_dir):
        """Test filter extraction with various formats."""
        # Test with both thickness and material
        content = """[XTekCT]
Name=Test

[CTPro]
Filter_ThicknessMM=0.5
Filter_Material=Aluminum
"""
        xtekct_path = temp_dir / "test.xtekct"
        xtekct_path.write_text(content, encoding="utf-8")

        output_path = temp_dir / "output.json"
        parse_xtekct_file(xtekct_path, output_path)

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["xray_filter"] == "0.5 mm Aluminum"

    def test_filter_material_only(self, temp_dir):
        """Test filter extraction with material only."""
        content = """[XTekCT]
Name=Test

[CTPro]
Filter_Material=Copper
"""
        xtekct_path = temp_dir / "test.xtekct"
        xtekct_path.write_text(content, encoding="utf-8")

        output_path = temp_dir / "output.json"
        parse_xtekct_file(xtekct_path, output_path)

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["xray_filter"] == "Copper"

    def test_output_directory_created(self, temp_dir, mock_xtekct_content):
        """Test that output directories are created if they don't exist."""
        xtekct_path = temp_dir / "test.xtekct"
        xtekct_path.write_text(mock_xtekct_content, encoding="utf-8")

        output_path = temp_dir / "nested" / "deep" / "output.json"
        parse_xtekct_file(xtekct_path, output_path)

        assert output_path.exists()
