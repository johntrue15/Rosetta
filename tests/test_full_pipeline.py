"""
End-to-end tests for the full parsing pipeline.

These tests simulate the GitHub Actions workflow:
1. Upload file to data/
2. Parse with parse_any.py
3. Aggregate with aggregate_json.py
4. Convert to CSV with metadata_to_csv.py
"""

import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"


class TestFullPipeline:
    """End-to-end pipeline tests."""

    def test_pca_file_pipeline(self, temp_dir, sample_pca_path):
        """Test full pipeline with a PCA file."""
        if not sample_pca_path.exists():
            pytest.skip(f"Sample PCA file not found: {sample_pca_path}")

        # Setup directory structure
        data_dir = temp_dir / "data"
        parsed_dir = data_dir / "parsed"
        completed_dir = data_dir / "completed"
        data_dir.mkdir()
        parsed_dir.mkdir()
        completed_dir.mkdir()

        # Copy test file to data/
        test_file = data_dir / sample_pca_path.name
        shutil.copy(sample_pca_path, test_file)

        # Step 1: Parse the file
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / "parse_any.py"),
                str(test_file),
                "-o",
                str(parsed_dir),
                "--completed-dir",
                str(completed_dir),
                "--pretty",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Parsing failed: {result.stderr}"

        # Verify file was parsed and moved
        assert (parsed_dir / f"{sample_pca_path.name}.json").exists()
        assert (completed_dir / sample_pca_path.name).exists()
        assert not test_file.exists()  # Original should be moved

        # Step 2: Aggregate
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / "aggregate_json.py"),
                "--roots",
                str(data_dir),
                "--out",
                str(data_dir / "metadata.json"),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Aggregation failed: {result.stderr}"
        assert (data_dir / "metadata.json").exists()

        # Verify metadata.json content
        with open(data_dir / "metadata.json", "r", encoding="utf-8") as f:
            metadata = json.load(f)

        assert len(metadata) >= 1
        assert metadata[0]["file_name"] == sample_pca_path.name

        # Step 3: Convert to CSV
        users_csv = temp_dir / "users.csv"
        users_csv.write_text("Folder,User name,Email\nFICS,Test User,test@example.com")

        script = """
import sys
sys.path.insert(0, '{scripts_dir}')
import os
os.chdir('{temp_dir}')

import metadata_to_csv
metadata_to_csv.METADATA_JSON = 'data/metadata.json'
metadata_to_csv.USERS_CSV = 'users.csv'
metadata_to_csv.OUTPUT_CSV = 'data/metadata.csv'
metadata_to_csv.main()
""".format(
            scripts_dir=str(SCRIPTS_DIR), temp_dir=str(temp_dir)
        )

        wrapper = temp_dir / "convert.py"
        wrapper.write_text(script)
        result = subprocess.run(
            [sys.executable, str(wrapper)], capture_output=True, text=True
        )
        assert result.returncode == 0, f"CSV conversion failed: {result.stderr}"

        # Verify CSV output
        csv_path = data_dir / "metadata.csv"
        assert csv_path.exists()

        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) >= 1
        assert "file_name" in rows[0]
        assert "X-ray User" in rows[0]

    def test_rtf_file_pipeline(self, temp_dir, sample_rtf_path):
        """Test full pipeline with an RTF file."""
        if not sample_rtf_path.exists():
            pytest.skip(f"Sample RTF file not found: {sample_rtf_path}")

        # Setup directory structure
        data_dir = temp_dir / "data"
        parsed_dir = data_dir / "parsed"
        completed_dir = data_dir / "completed"
        data_dir.mkdir()
        parsed_dir.mkdir()
        completed_dir.mkdir()

        # Copy test file
        test_file = data_dir / sample_rtf_path.name
        shutil.copy(sample_rtf_path, test_file)

        # Parse
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / "parse_any.py"),
                str(test_file),
                "-o",
                str(parsed_dir),
                "--completed-dir",
                str(completed_dir),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"RTF parsing failed: {result.stderr}"

        # Verify parsed JSON
        parsed_json = parsed_dir / f"{sample_rtf_path.name}.json"
        assert parsed_json.exists()

        with open(parsed_json, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert "file_name" in data
        assert "sections" in data  # RTF parser includes raw sections
        assert "sha256" in data

    def test_xtekct_file_pipeline(self, temp_dir, sample_xtekct_path):
        """Test full pipeline with an XTEKCT file."""
        if not sample_xtekct_path.exists():
            pytest.skip(f"Sample XTEKCT file not found: {sample_xtekct_path}")

        # Setup
        data_dir = temp_dir / "data"
        parsed_dir = data_dir / "parsed"
        completed_dir = data_dir / "completed"
        data_dir.mkdir()
        parsed_dir.mkdir()
        completed_dir.mkdir()

        test_file = data_dir / sample_xtekct_path.name
        shutil.copy(sample_xtekct_path, test_file)

        # Parse
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / "parse_any.py"),
                str(test_file),
                "-o",
                str(parsed_dir),
                "--completed-dir",
                str(completed_dir),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"XTEKCT parsing failed: {result.stderr}"

        # Verify
        parsed_json = parsed_dir / f"{sample_xtekct_path.name}.json"
        assert parsed_json.exists()

        with open(parsed_json, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["file_name"] == sample_xtekct_path.name

    def test_multiple_files_pipeline(self, temp_dir, sample_pca_path, sample_rtf_path, sample_xtekct_path):
        """Test pipeline with multiple file types."""
        # Setup
        data_dir = temp_dir / "data"
        parsed_dir = data_dir / "parsed"
        completed_dir = data_dir / "completed"
        data_dir.mkdir()
        parsed_dir.mkdir()
        completed_dir.mkdir()

        files_to_process = []

        # Copy all available sample files
        for path in [sample_pca_path, sample_rtf_path, sample_xtekct_path]:
            if path.exists():
                dest = data_dir / path.name
                shutil.copy(path, dest)
                files_to_process.append(dest)

        if not files_to_process:
            pytest.skip("No sample files available")

        # Parse each file
        for f in files_to_process:
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS_DIR / "parse_any.py"),
                    str(f),
                    "-o",
                    str(parsed_dir),
                    "--completed-dir",
                    str(completed_dir),
                ],
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0, f"Failed to parse {f}: {result.stderr}"

        # Aggregate all
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / "aggregate_json.py"),
                "--roots",
                str(data_dir),
                "--out",
                str(data_dir / "metadata.json"),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

        # Verify aggregated data
        with open(data_dir / "metadata.json", "r", encoding="utf-8") as f:
            metadata = json.load(f)

        assert len(metadata) == len(files_to_process)

    def test_unsupported_file_type(self, temp_dir):
        """Test that unsupported file types are rejected."""
        data_dir = temp_dir / "data"
        parsed_dir = data_dir / "parsed"
        completed_dir = data_dir / "completed"
        data_dir.mkdir()
        parsed_dir.mkdir()
        completed_dir.mkdir()

        # Create unsupported file
        unsupported = data_dir / "test.txt"
        unsupported.write_text("This is not a supported file type")

        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / "parse_any.py"),
                str(unsupported),
                "-o",
                str(parsed_dir),
                "--completed-dir",
                str(completed_dir),
            ],
            capture_output=True,
            text=True,
        )

        # Should fail with exit code 2 for unsupported extension
        assert result.returncode == 2
        assert "Unsupported file extension" in result.stderr

    def test_file_moved_to_completed_on_success(self, temp_dir, mock_pca_content):
        """Test that successfully parsed files are moved to completed directory."""
        data_dir = temp_dir / "data"
        parsed_dir = data_dir / "parsed"
        completed_dir = data_dir / "completed"
        data_dir.mkdir()
        parsed_dir.mkdir()
        completed_dir.mkdir()

        # Create test file
        test_file = data_dir / "test.pca"
        test_file.write_text(mock_pca_content)

        # Parse
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / "parse_any.py"),
                str(test_file),
                "-o",
                str(parsed_dir),
                "--completed-dir",
                str(completed_dir),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0

        # Original should be moved
        assert not test_file.exists()
        assert (completed_dir / "test.pca").exists()

        # Parsed JSON should exist
        assert (parsed_dir / "test.pca.json").exists()

    def test_duplicate_filename_handling(self, temp_dir, mock_pca_content):
        """Test handling of duplicate filenames in completed directory."""
        data_dir = temp_dir / "data"
        parsed_dir = data_dir / "parsed"
        completed_dir = data_dir / "completed"
        data_dir.mkdir()
        parsed_dir.mkdir()
        completed_dir.mkdir()

        # Pre-create a file in completed
        (completed_dir / "test.pca").write_text("existing file")

        # Create new file with same name
        test_file = data_dir / "test.pca"
        test_file.write_text(mock_pca_content)

        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / "parse_any.py"),
                str(test_file),
                "-o",
                str(parsed_dir),
                "--completed-dir",
                str(completed_dir),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0

        # Should create a renamed file
        moved_files = list(completed_dir.glob("test*.pca"))
        assert len(moved_files) == 2  # Original and moved with suffix
