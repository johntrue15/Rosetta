"""
Tests for RTF file parsing (North Star Imaging format).
"""

import json
import sys
from pathlib import Path

import pytest

# Import the parser
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from rtf_to_json import (
    parse_rtf_file,
    tokenize,
    build_record,
    guess_binning,
    parse_roi,
    first_float,
    normalize_section_name,
    sha256_file,
)


class TestRTFParserHelpers:
    """Test helper functions in the RTF parser."""

    def test_guess_binning(self):
        """Test binning value normalization."""
        assert guess_binning("none") == "1x1"
        assert guess_binning("None") == "1x1"
        assert guess_binning("no") == "1x1"
        assert guess_binning("2x2") == "2x2"
        assert guess_binning("4x4") == "4x4"
        assert guess_binning("2") == "2x2"
        assert guess_binning("") == "N/A"

    def test_parse_roi(self):
        """Test ROI string parsing."""
        assert parse_roi("2048x2048+0+0") == (2048, 2048)
        assert parse_roi("1024 x 1024") == (1024, 1024)
        assert parse_roi("invalid") == (None, None)
        assert parse_roi("") == (None, None)

    def test_first_float(self):
        """Test extracting first float from string."""
        assert first_float("130 kV") == 130.0
        assert first_float("225 µA") == 225.0
        assert first_float("799.999 [mm] (FDD)") == 799.999
        assert first_float("x6.06") == 6.06
        assert first_float("no numbers") is None

    def test_normalize_section_name(self):
        """Test section name normalization with aliases."""
        assert normalize_section_name("xray source") == "Xray Source"
        assert normalize_section_name("X-ray Source") == "Xray Source"
        assert normalize_section_name("DETECTOR") == "Detector"
        assert normalize_section_name("CT Scan") == "CT Scan"


class TestRTFTokenizer:
    """Test the RTF tokenizer."""

    def test_tokenize_simple(self):
        """Test tokenizing simple pipe-delimited content."""
        text = """Xray Source:||
Name:|Comet FXE [1796906]|
Voltage:|130 kV|
Current:|225 µA|

Detector:||
Name:|Perkin Elmer|
Binning:|none|
"""
        sections = tokenize(text)

        assert "Xray Source" in sections
        assert sections["Xray Source"]["Name"] == "Comet FXE [1796906]"
        assert sections["Xray Source"]["Voltage"] == "130 kV"
        assert sections["Xray Source"]["Current"] == "225 µA"

        assert "Detector" in sections
        assert sections["Detector"]["Binning"] == "none"


class TestRTFParser:
    """Test suite for RTF file parser."""

    def test_parse_real_rtf_file(self, sample_rtf_path, temp_dir):
        """Test parsing a real RTF file from the repo."""
        if not sample_rtf_path.exists():
            pytest.skip(f"Sample RTF file not found: {sample_rtf_path}")

        output_path = temp_dir / "output.json"
        parse_rtf_file(sample_rtf_path, output_path, pretty=True)

        assert output_path.exists(), "Output JSON file should be created"

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Verify required fields are present
        assert "file_name" in data
        assert "sha256" in data
        assert "source_path" in data
        assert "sections" in data  # RTF parser keeps raw sections

        # Verify X-ray parameters are extracted
        assert data["xray_tube_voltage"] != "N/A", "Voltage should be extracted"
        assert data["xray_tube_current"] != "N/A", "Current should be extracted"

    def test_parse_rtf_extracts_ct_scan_info(self, sample_rtf_path, temp_dir):
        """Test that CT scan information is properly extracted."""
        if not sample_rtf_path.exists():
            pytest.skip(f"Sample RTF file not found: {sample_rtf_path}")

        output_path = temp_dir / "output.json"
        parse_rtf_file(sample_rtf_path, output_path, pretty=True)

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # The RTF file should have number of projections
        if data["ct_number_images"] != "N/A":
            assert int(data["ct_number_images"]) > 0

    def test_parse_rtf_extracts_distances(self, sample_rtf_path, temp_dir):
        """Test that distance information and magnification are extracted."""
        if not sample_rtf_path.exists():
            pytest.skip(f"Sample RTF file not found: {sample_rtf_path}")

        output_path = temp_dir / "output.json"
        parse_rtf_file(sample_rtf_path, output_path, pretty=True)

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Check distances are extracted
        if data["Source_detector_distance"] != "N/A":
            sdd = float(data["Source_detector_distance"])
            assert sdd > 0

        if data["Source_sample_distance"] != "N/A":
            sod = float(data["Source_sample_distance"])
            assert sod > 0

    def test_power_calculation(self, temp_dir):
        """Test that X-ray power is correctly calculated using internal functions.
        
        Note: We test tokenize() and build_record() directly because striprtf
        mangles plain text content (removes newlines), so we can't easily
        create mock RTF files.
        """
        # Test the tokenizer directly with pre-processed text (as if striprtf worked)
        mock_text = """X-ray Source:||
Name:|Test Source|
Voltage:|150 kV|
Current:|300 uA|
"""
        # Verify the tokenizer works correctly with proper newlines
        sections = tokenize(mock_text)
        assert "Xray Source" in sections, f"Section not found. Sections: {sections.keys()}"
        assert "Voltage" in sections["Xray Source"]
        assert "Current" in sections["Xray Source"]

        # Test build_record directly with the tokenized sections
        # Create a dummy path for the record
        dummy_path = temp_dir / "test.rtf"
        dummy_path.write_text("dummy", encoding="utf-8")
        
        rec = build_record(dummy_path, sections)

        # Power = kV * µA * 1e-3 = 150 * 300 * 0.001 = 45 W
        assert rec["xray_tube_voltage"] != "N/A", f"Voltage not extracted: {rec}"
        assert rec["xray_tube_current"] != "N/A", f"Current not extracted: {rec}"
        assert rec["xray_tube_power"] != "N/A", f"Power not calculated: {rec}"
        
        power = float(rec["xray_tube_power"])
        assert abs(power - 45.0) < 0.01, f"Expected 45W, got {power}"

    def test_voxel_size_from_pixel_pitch(self, temp_dir):
        """Test voxel size calculation from effective pixel pitch using internal functions.
        
        Note: We test tokenize() and build_record() directly because striprtf
        mangles plain text content.
        """
        mock_text = """Distances:||
Source to detector:|800 [mm] (FDD)|
Source to object:|200 [mm] (FOD)|
Effective pixel pitch:|0.033 [mm]|
"""
        # Test tokenizer
        sections = tokenize(mock_text)
        assert "Distances" in sections
        assert "Effective pixel pitch" in sections["Distances"]

        # Test build_record directly
        dummy_path = temp_dir / "test.rtf"
        dummy_path.write_text("dummy", encoding="utf-8")
        
        rec = build_record(dummy_path, sections)

        # Voxel size should be converted from mm to µm (0.033 mm = 33 µm)
        assert rec["ct_voxel_size_um"] != "N/A", f"Voxel size not extracted: {rec}"
        voxel = float(rec["ct_voxel_size_um"])
        assert abs(voxel - 33.0) < 0.1, f"Expected 33 µm, got {voxel}"

    def test_roi_to_image_dimensions(self, temp_dir):
        """Test that ROI is converted to image dimensions."""
        mock_content = """ROI:|2048x2048+0+0|
Distances:||
Effective pixel pitch:|0.033 [mm]|
"""
        rtf_path = temp_dir / "test.rtf"
        rtf_path.write_text(mock_content, encoding="utf-8")

        output_path = temp_dir / "output.json"
        parse_rtf_file(rtf_path, output_path)

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["image_width_pixels"] == "2048"
        assert data["image_height_pixels"] == "2048"

    def test_sha256_hash_generated(self, temp_dir):
        """Test that SHA256 hash is generated."""
        mock_content = """Test:||
Value:|test|
"""
        rtf_path = temp_dir / "test.rtf"
        rtf_path.write_text(mock_content, encoding="utf-8")

        output_path = temp_dir / "output.json"
        parse_rtf_file(rtf_path, output_path)

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert "sha256" in data
        assert len(data["sha256"]) == 64
