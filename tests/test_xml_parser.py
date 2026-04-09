"""
Tests for XML file parsing (Nikon CT .ctinfo.xml and .ctprofile.xml).
"""

import json
import sys
from pathlib import Path

import pytest

# Import the parser
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from xml_to_json import parse_xml_file


class TestXMLParserCTProfile:
    """Test suite for ctprofile.xml parsing."""

    def test_parse_ctprofile_creates_output(self, temp_dir, mock_ctprofile_xml):
        """Test that parsing a ctprofile.xml creates an output JSON file."""
        xml_path = temp_dir / "sample.ctprofile.xml"
        xml_path.write_text(mock_ctprofile_xml, encoding="utf-8")

        output_path = temp_dir / "output.json"
        parse_xml_file(xml_path, output_path, pretty=True)

        assert output_path.exists(), "Output JSON file should be created"

    def test_xray_settings(self, temp_dir, mock_ctprofile_xml):
        """Test X-ray voltage and current extraction."""
        xml_path = temp_dir / "sample.ctprofile.xml"
        xml_path.write_text(mock_ctprofile_xml, encoding="utf-8")

        output_path = temp_dir / "output.json"
        parse_xml_file(xml_path, output_path, pretty=True)

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["xray_tube_voltage"] == "106.000"
        assert data["xray_tube_current"] == "106.000"

    def test_power_calculation(self, temp_dir, mock_ctprofile_xml):
        """Test X-ray power calculation."""
        xml_path = temp_dir / "sample.ctprofile.xml"
        xml_path.write_text(mock_ctprofile_xml, encoding="utf-8")

        output_path = temp_dir / "output.json"
        parse_xml_file(xml_path, output_path, pretty=True)

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Power = kV * uA * 1e-3 = 106 * 106 * 0.001 = 11.236 W
        power = float(data["xray_tube_power"])
        expected = 106 * 106 * 0.001
        assert abs(power - expected) < 0.01, f"Expected {expected}W, got {power}"

    def test_xray_tube_id(self, temp_dir, mock_ctprofile_xml):
        """Test X-ray head / tube ID extraction."""
        xml_path = temp_dir / "sample.ctprofile.xml"
        xml_path.write_text(mock_ctprofile_xml, encoding="utf-8")

        output_path = temp_dir / "output.json"
        parse_xml_file(xml_path, output_path, pretty=True)

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["xray_tube_ID"] == "Reflection 225"

    def test_projections(self, temp_dir, mock_ctprofile_xml):
        """Test projection count extraction."""
        xml_path = temp_dir / "sample.ctprofile.xml"
        xml_path.write_text(mock_ctprofile_xml, encoding="utf-8")

        output_path = temp_dir / "output.json"
        parse_xml_file(xml_path, output_path, pretty=True)

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["ct_number_images"] == "3142"

    def test_imaging_settings(self, temp_dir, mock_ctprofile_xml):
        """Test imaging settings extraction (exposure, binning, dimensions)."""
        xml_path = temp_dir / "sample.ctprofile.xml"
        xml_path.write_text(mock_ctprofile_xml, encoding="utf-8")

        output_path = temp_dir / "output.json"
        parse_xml_file(xml_path, output_path, pretty=True)

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["detector_capture_time"] == "1000"
        assert data["detector_binning"] == "0"
        assert data["image_width_pixels"] == "2000"
        assert data["image_height_pixels"] == "2000"

    def test_detector_averaging(self, temp_dir, mock_ctprofile_xml):
        """Test frames per projection → detector averaging."""
        xml_path = temp_dir / "sample.ctprofile.xml"
        xml_path.write_text(mock_ctprofile_xml, encoding="utf-8")

        output_path = temp_dir / "output.json"
        parse_xml_file(xml_path, output_path, pretty=True)

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["detector_averaging"] == "2"

    def test_filter_extraction(self, temp_dir, mock_ctprofile_xml):
        """Test X-ray filter extraction from GreyLevelTargets."""
        xml_path = temp_dir / "sample.ctprofile.xml"
        xml_path.write_text(mock_ctprofile_xml, encoding="utf-8")

        output_path = temp_dir / "output.json"
        parse_xml_file(xml_path, output_path, pretty=True)

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["xray_filter"] == "0.125 mm Copper"

    def test_manipulator_positions(self, temp_dir, mock_ctprofile_xml):
        """Test manipulator position extraction."""
        xml_path = temp_dir / "sample.ctprofile.xml"
        xml_path.write_text(mock_ctprofile_xml, encoding="utf-8")

        output_path = temp_dir / "output.json"
        parse_xml_file(xml_path, output_path, pretty=True)

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert "manipulator_positions" in data
        assert "178.7256" in data["manipulator_positions"]

    def test_volume_of_interest(self, temp_dir, mock_ctprofile_xml):
        """Test VolumeOfInterest → sample start/end/range."""
        xml_path = temp_dir / "sample.ctprofile.xml"
        xml_path.write_text(mock_ctprofile_xml, encoding="utf-8")

        output_path = temp_dir / "output.json"
        parse_xml_file(xml_path, output_path, pretty=True)

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["sample_x_start"] == "0"
        assert data["sample_x_end"] == "1999"
        assert data["sample_x_range"] == "1999.0"
        assert data["sample_y_start"] == "0"
        assert data["sample_y_end"] == "1999"
        assert data["sample_z_start"] == "0"
        assert data["sample_z_end"] == "1999"

    def test_dataset_name(self, temp_dir, mock_ctprofile_xml):
        """Test profile/dataset name extraction."""
        xml_path = temp_dir / "sample.ctprofile.xml"
        xml_path.write_text(mock_ctprofile_xml, encoding="utf-8")

        output_path = temp_dir / "output.json"
        parse_xml_file(xml_path, output_path, pretty=True)

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["dataset_name"] == "test_sample"

    def test_file_name_in_output(self, temp_dir, mock_ctprofile_xml):
        """Test that output includes the source file name."""
        xml_path = temp_dir / "sample.ctprofile.xml"
        xml_path.write_text(mock_ctprofile_xml, encoding="utf-8")

        output_path = temp_dir / "output.json"
        parse_xml_file(xml_path, output_path, pretty=True)

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["file_name"] == "sample.ctprofile.xml"


class TestXMLParserCTInfo:
    """Test suite for ctinfo.xml parsing."""

    def test_parse_ctinfo_creates_output(self, temp_dir, mock_ctinfo_xml):
        """Test that parsing a ctinfo.xml creates an output JSON file."""
        xml_path = temp_dir / "sample.ctinfo.xml"
        xml_path.write_text(mock_ctinfo_xml, encoding="utf-8")

        output_path = temp_dir / "output.json"
        parse_xml_file(xml_path, output_path, pretty=True)

        assert output_path.exists()

    def test_identifier_extracted(self, temp_dir, mock_ctinfo_xml):
        """Test Identifier → dataset_name."""
        xml_path = temp_dir / "sample.ctinfo.xml"
        xml_path.write_text(mock_ctinfo_xml, encoding="utf-8")

        output_path = temp_dir / "output.json"
        parse_xml_file(xml_path, output_path, pretty=True)

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["dataset_name"] == "test_sample_hand"

    def test_elements_extracted(self, temp_dir, mock_ctinfo_xml):
        """Test Elements key-value extraction."""
        xml_path = temp_dir / "sample.ctinfo.xml"
        xml_path.write_text(mock_ctinfo_xml, encoding="utf-8")

        output_path = temp_dir / "output.json"
        parse_xml_file(xml_path, output_path, pretty=True)

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["ctinfo_dataset_name"] == "test_sample_hand"

    def test_file_name_in_output(self, temp_dir, mock_ctinfo_xml):
        """Test that output includes the source file name."""
        xml_path = temp_dir / "sample.ctinfo.xml"
        xml_path.write_text(mock_ctinfo_xml, encoding="utf-8")

        output_path = temp_dir / "output.json"
        parse_xml_file(xml_path, output_path, pretty=True)

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["file_name"] == "sample.ctinfo.xml"

    def test_na_defaults(self, temp_dir, mock_ctinfo_xml):
        """Test that non-present fields default to N/A."""
        xml_path = temp_dir / "sample.ctinfo.xml"
        xml_path.write_text(mock_ctinfo_xml, encoding="utf-8")

        output_path = temp_dir / "output.json"
        parse_xml_file(xml_path, output_path, pretty=True)

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # ctinfo.xml does not contain xray settings
        assert data["xray_tube_voltage"] == "N/A"
        assert data["xray_tube_current"] == "N/A"
        assert data["ct_number_images"] == "N/A"


class TestXMLParserEdgeCases:
    """Test edge cases for XML parsing."""

    def test_output_directory_created(self, temp_dir, mock_ctprofile_xml):
        """Test that output directories are created if they don't exist."""
        xml_path = temp_dir / "sample.ctprofile.xml"
        xml_path.write_text(mock_ctprofile_xml, encoding="utf-8")

        output_path = temp_dir / "nested" / "deep" / "output.json"
        parse_xml_file(xml_path, output_path)

        assert output_path.exists()

    def test_ctprofile_no_filter(self, temp_dir):
        """Test ctprofile with no filter info."""
        content = """<?xml version="1.0" encoding="utf-8"?>
<CTProfile xmlns:xsi="none">
  <XraySettings>
    <kV>80</kV>
    <uA>200</uA>
  </XraySettings>
  <Projections>1000</Projections>
</CTProfile>
"""
        xml_path = temp_dir / "test.ctprofile.xml"
        xml_path.write_text(content, encoding="utf-8")

        output_path = temp_dir / "output.json"
        parse_xml_file(xml_path, output_path, pretty=True)

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["xray_tube_voltage"] == "80.000"
        assert data["xray_tube_current"] == "200.000"
        assert data["ct_number_images"] == "1000"
        assert data["xray_filter"] == "N/A"

    def test_empty_ctinfo(self, temp_dir):
        """Test minimal ctinfo.xml with no elements."""
        content = """<?xml version="1.0" encoding="utf-8"?>
<Information xmlns:xsi="none">
</Information>
"""
        xml_path = temp_dir / "test.ctinfo.xml"
        xml_path.write_text(content, encoding="utf-8")

        output_path = temp_dir / "output.json"
        parse_xml_file(xml_path, output_path, pretty=True)

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["file_name"] == "test.ctinfo.xml"
        assert data["xray_tube_voltage"] == "N/A"
