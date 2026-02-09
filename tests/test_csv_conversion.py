"""
Tests for CSV conversion and user attribution.
"""

import csv
import json
import sys
from pathlib import Path

import pytest

# Import the conversion functions
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from metadata_to_csv import (
    flatten_dict,
    normalize_path,
    normalize_component,
    split_path_components,
    UsersIndex,
    find_user_email_for_record,
    gather_candidate_paths,
    read_users_index,
)


class TestHelperFunctions:
    """Test helper functions."""

    def test_flatten_dict_simple(self):
        """Test flattening a simple nested dict."""
        nested = {"a": 1, "b": {"c": 2, "d": 3}}
        flat = flatten_dict(nested)
        assert flat == {"a": 1, "b.c": 2, "b.d": 3}

    def test_flatten_dict_deep(self):
        """Test flattening deeply nested dict."""
        nested = {"a": {"b": {"c": {"d": "value"}}}}
        flat = flatten_dict(nested)
        assert flat == {"a.b.c.d": "value"}

    def test_normalize_path_windows(self):
        """Test path normalization with Windows paths."""
        path = "S:\\CT_DATA\\FICS\\project\\file.pca"
        normalized = normalize_path(path)
        assert "\\" not in normalized
        assert "s:/ct_data/fics/project/file.pca" == normalized

    def test_normalize_path_file_uri(self):
        """Test path normalization with file:// URIs."""
        path = "file:///S:/CT_DATA/project/file.pca"
        normalized = normalize_path(path)
        assert not normalized.startswith("file:")

    def test_normalize_component(self):
        """Test component normalization."""
        assert normalize_component("FICS") == "fics"
        assert normalize_component("  Stanley  ") == "stanley"
        assert normalize_component("My  Project") == "my project"

    def test_split_path_components(self):
        """Test path component splitting."""
        windows_path = "S:\\CT_DATA\\FICS\\project"
        components = split_path_components(windows_path)
        assert components == ["S:", "CT_DATA", "FICS", "project"]

        unix_path = "/home/user/data/project"
        components = split_path_components(unix_path)
        assert components == ["home", "user", "data", "project"]


class TestUserAttribution:
    """Test user attribution from paths."""

    def test_gather_candidate_paths(self):
        """Test extracting candidate paths from a record."""
        record = {
            "file_path": "S:\\CT_DATA\\FICS\\project",
            "txrm_file_path": "N/A",
            "file_hyperlink": "file:///S:/CT_DATA/FICS/project/file.pca",
            "calib_images": {
                "MGainImg": "S:\\CT_DATA\\FICS\\calibration\\gain.tif",
                "calib_folder_path": "S:\\CT_DATA\\FICS\\calibration",
            },
        }
        paths = gather_candidate_paths(record)
        assert len(paths) >= 2
        assert "S:\\CT_DATA\\FICS\\project" in paths

    def test_find_user_by_component_match(self):
        """Test finding user by path component."""
        users = UsersIndex(
            component_map={"fics": "john@example.com", "stanley": "jane@example.com"},
            path_list=[],
        )
        record = {"file_path": "S:\\CT_DATA\\FICS\\project\\file.pca"}

        email = find_user_email_for_record(record, users)
        assert email == "john@example.com"

    def test_find_user_by_path_substring(self):
        """Test finding user by path substring match."""
        users = UsersIndex(
            component_map={},
            path_list=[
                ("s:/ct_data/fics/special_project", "john@example.com"),
            ],
        )
        record = {"file_path": "S:\\CT_DATA\\FICS\\special_project\\data\\file.pca"}

        email = find_user_email_for_record(record, users)
        assert email == "john@example.com"

    def test_most_specific_match_wins(self):
        """Test that longer/more specific matches take precedence."""
        users = UsersIndex(
            component_map={
                "fics": "general@example.com",
                "special_project": "specific@example.com",
            },
            path_list=[],
        )
        record = {"file_path": "S:\\CT_DATA\\FICS\\special_project\\file.pca"}

        email = find_user_email_for_record(record, users)
        # "special_project" is longer than "fics", so it should win
        assert email == "specific@example.com"

    def test_no_match_returns_empty(self):
        """Test that no match returns empty string."""
        users = UsersIndex(
            component_map={"other": "other@example.com"},
            path_list=[],
        )
        record = {"file_path": "S:\\CT_DATA\\completely\\different\\path"}

        email = find_user_email_for_record(record, users)
        assert email == ""

    def test_empty_users_returns_empty(self):
        """Test that empty users index returns empty string."""
        users = UsersIndex(component_map={}, path_list=[])
        record = {"file_path": "S:\\CT_DATA\\FICS\\project"}

        email = find_user_email_for_record(record, users)
        assert email == ""


class TestReadUsersIndex:
    """Test reading users.csv file."""

    def test_read_users_csv(self, temp_dir, mock_users_csv):
        """Test reading a valid users.csv file."""
        users_path = temp_dir / "users.csv"
        users_path.write_text(mock_users_csv)

        users = read_users_index(str(users_path))

        assert "fics" in users.component_map
        assert users.component_map["fics"] == "john.doe@example.com"
        assert "nishimura" in users.component_map
        assert users.component_map["nishimura"] == "jane.smith@example.com"

    def test_read_missing_users_csv(self, temp_dir):
        """Test handling of missing users.csv."""
        users = read_users_index(str(temp_dir / "nonexistent.csv"))

        assert users.component_map == {}
        assert users.path_list == []


class TestCSVConversion:
    """Test full CSV conversion."""

    def test_full_conversion(self, temp_dir, mock_metadata_json, mock_users_csv):
        """Test full metadata.json to metadata.csv conversion."""
        # Create data directory structure
        data_dir = temp_dir / "data"
        data_dir.mkdir()

        # Write metadata.json
        metadata_path = data_dir / "metadata.json"
        metadata_path.write_text(json.dumps(mock_metadata_json))

        # Write users.csv
        users_path = temp_dir / "users.csv"
        users_path.write_text(mock_users_csv)

        # Run conversion (need to change directory context)
        import subprocess
        import os

        # Create a wrapper script that changes to the temp directory
        script = """
import sys
import os
sys.path.insert(0, '{scripts_dir}')
os.chdir('{temp_dir}')

# Override paths in the module
import metadata_to_csv
metadata_to_csv.METADATA_JSON = 'data/metadata.json'
metadata_to_csv.USERS_CSV = 'users.csv'
metadata_to_csv.OUTPUT_CSV = 'data/metadata.csv'
metadata_to_csv.main()
""".format(
            scripts_dir=str(Path(__file__).parent.parent / "scripts"),
            temp_dir=str(temp_dir),
        )

        wrapper_script = temp_dir / "run_conversion.py"
        wrapper_script.write_text(script)

        result = subprocess.run(
            [sys.executable, str(wrapper_script)],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Conversion failed: {result.stderr}"

        # Check output CSV
        csv_path = data_dir / "metadata.csv"
        assert csv_path.exists()

        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 2

        # Check user attribution
        assert "X-ray User" in rows[0]

        # FICS should be attributed to john.doe@example.com
        fics_row = next((r for r in rows if "FICS" in r.get("file_path", "")), None)
        if fics_row:
            assert fics_row["X-ray User"] == "john.doe@example.com"

    def test_flattened_nested_fields(self, temp_dir):
        """Test that nested fields like calib_images are flattened."""
        data_dir = temp_dir / "data"
        data_dir.mkdir()

        # Metadata with nested calib_images
        metadata = [
            {
                "file_name": "test.pca",
                "calib_images": {
                    "MGainImg": "path/to/gain.tif",
                    "OffsetImg": "path/to/offset.tif",
                },
            }
        ]
        (data_dir / "metadata.json").write_text(json.dumps(metadata))

        # Empty users.csv
        (temp_dir / "users.csv").write_text("")

        import subprocess

        script = """
import sys
import os
sys.path.insert(0, '{scripts_dir}')
os.chdir('{temp_dir}')

import metadata_to_csv
metadata_to_csv.METADATA_JSON = 'data/metadata.json'
metadata_to_csv.USERS_CSV = 'users.csv'
metadata_to_csv.OUTPUT_CSV = 'data/metadata.csv'
metadata_to_csv.main()
""".format(
            scripts_dir=str(Path(__file__).parent.parent / "scripts"),
            temp_dir=str(temp_dir),
        )

        wrapper = temp_dir / "run.py"
        wrapper.write_text(script)
        subprocess.run([sys.executable, str(wrapper)], capture_output=True)

        with open(data_dir / "metadata.csv", "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            row = next(reader)

        # Nested fields should be flattened with dot notation
        assert "calib_images.MGainImg" in row
        assert row["calib_images.MGainImg"] == "path/to/gain.tif"
