"""
Tests for CSV conversion, user attribution, and standard_format.json mapping.
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
    load_column_format,
    ColumnFormat,
    convert,
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


class TestColumnFormat:
    """Test standard_format.json loading and column mapping."""

    def test_load_missing_format_returns_none(self, temp_dir):
        """When the format file doesn't exist, return None (use defaults)."""
        fmt = load_column_format(str(temp_dir / "nonexistent.json"))
        assert fmt is None

    def test_load_valid_format(self, temp_dir):
        """Load a valid standard_format.json and verify structure."""
        fmt_data = {
            "version": 1,
            "include_unmapped": True,
            "columns": [
                {"source": "file_name", "name": "File Name"},
                {"source": "xray_tube_voltage", "name": "Voltage (kV)"},
            ],
        }
        fmt_path = temp_dir / "format.json"
        fmt_path.write_text(json.dumps(fmt_data))

        fmt = load_column_format(str(fmt_path))
        assert fmt is not None
        assert fmt.rename("file_name") == "File Name"
        assert fmt.rename("xray_tube_voltage") == "Voltage (kV)"

    def test_rename_unmapped_field_returns_source(self, temp_dir):
        """Fields not in the format config keep their original names."""
        fmt_data = {
            "columns": [{"source": "file_name", "name": "File Name"}],
            "include_unmapped": True,
        }
        fmt_path = temp_dir / "format.json"
        fmt_path.write_text(json.dumps(fmt_data))

        fmt = load_column_format(str(fmt_path))
        assert fmt.rename("some_other_field") == "some_other_field"

    def test_build_fieldnames_order(self, temp_dir):
        """Columns appear in the order defined in the format config."""
        fmt_data = {
            "columns": [
                {"source": "xray_tube_voltage", "name": "Voltage"},
                {"source": "file_name", "name": "File"},
            ],
            "include_unmapped": False,
        }
        fmt_path = temp_dir / "format.json"
        fmt_path.write_text(json.dumps(fmt_data))

        fmt = load_column_format(str(fmt_path))
        all_keys = {"file_name", "xray_tube_voltage", "sha256"}
        headers = fmt.build_fieldnames(all_keys)

        assert headers == ["Voltage", "File"]

    def test_include_unmapped_true(self, temp_dir):
        """Unmapped fields are appended at the end when include_unmapped is true."""
        fmt_data = {
            "columns": [{"source": "file_name", "name": "File Name"}],
            "include_unmapped": True,
        }
        fmt_path = temp_dir / "format.json"
        fmt_path.write_text(json.dumps(fmt_data))

        fmt = load_column_format(str(fmt_path))
        all_keys = {"file_name", "extra_a", "extra_b"}
        headers = fmt.build_fieldnames(all_keys)

        assert headers[0] == "File Name"
        assert "extra_a" in headers
        assert "extra_b" in headers

    def test_include_unmapped_false(self, temp_dir):
        """Unmapped fields are excluded when include_unmapped is false."""
        fmt_data = {
            "columns": [{"source": "file_name", "name": "File Name"}],
            "include_unmapped": False,
        }
        fmt_path = temp_dir / "format.json"
        fmt_path.write_text(json.dumps(fmt_data))

        fmt = load_column_format(str(fmt_path))
        all_keys = {"file_name", "extra_a", "extra_b"}
        headers = fmt.build_fieldnames(all_keys)

        assert headers == ["File Name"]

    def test_include_false_excludes_column(self, temp_dir):
        """Columns with include:false are excluded."""
        fmt_data = {
            "columns": [
                {"source": "file_name", "name": "File Name"},
                {"source": "sha256", "name": "Hash", "include": False},
                {"source": "xray_tube_voltage", "name": "Voltage"},
            ],
            "include_unmapped": False,
        }
        fmt_path = temp_dir / "format.json"
        fmt_path.write_text(json.dumps(fmt_data))

        fmt = load_column_format(str(fmt_path))
        all_keys = {"file_name", "sha256", "xray_tube_voltage"}
        headers = fmt.build_fieldnames(all_keys)

        assert "Hash" not in headers
        assert headers == ["File Name", "Voltage"]

    def test_build_source_order_matches_headers(self, temp_dir):
        """Source order and header order are aligned."""
        fmt_data = {
            "columns": [
                {"source": "xray_tube_voltage", "name": "Voltage (kV)"},
                {"source": "file_name", "name": "File Name"},
            ],
            "include_unmapped": True,
        }
        fmt_path = temp_dir / "format.json"
        fmt_path.write_text(json.dumps(fmt_data))

        fmt = load_column_format(str(fmt_path))
        all_keys = {"file_name", "xray_tube_voltage", "extra"}
        sources = fmt.build_source_order(all_keys)
        headers = fmt.build_fieldnames(all_keys)

        assert len(sources) == len(headers)
        assert sources[0] == "xray_tube_voltage"
        assert headers[0] == "Voltage (kV)"


class TestConvertWithFormat:
    """Test the full convert() function with standard_format.json."""

    def test_convert_with_format_renames_headers(self, temp_dir, mock_metadata_json):
        """CSV headers should use the display names from standard_format.json."""
        data_dir = temp_dir / "data"
        data_dir.mkdir()

        (data_dir / "metadata.json").write_text(json.dumps(mock_metadata_json))
        (temp_dir / "users.csv").write_text("")

        fmt = {
            "version": 1,
            "include_unmapped": True,
            "columns": [
                {"source": "file_name", "name": "File Name"},
                {"source": "xray_tube_voltage", "name": "Voltage (kV)"},
                {"source": "X-ray User", "name": "X-ray User"},
            ],
        }
        fmt_path = temp_dir / "standard_format.json"
        fmt_path.write_text(json.dumps(fmt))

        out_csv = data_dir / "metadata.csv"
        convert(
            metadata_path=str(data_dir / "metadata.json"),
            users_path=str(temp_dir / "users.csv"),
            format_path=str(fmt_path),
            output_path=str(out_csv),
        )

        with open(out_csv, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            headers = next(reader)

        assert "File Name" in headers
        assert "Voltage (kV)" in headers
        assert "file_name" not in headers

    def test_convert_without_format_uses_defaults(self, temp_dir, mock_metadata_json):
        """Without standard_format.json, original field names are used."""
        data_dir = temp_dir / "data"
        data_dir.mkdir()

        (data_dir / "metadata.json").write_text(json.dumps(mock_metadata_json))
        (temp_dir / "users.csv").write_text("")

        out_csv = data_dir / "metadata.csv"
        convert(
            metadata_path=str(data_dir / "metadata.json"),
            users_path=str(temp_dir / "users.csv"),
            format_path=str(temp_dir / "nonexistent.json"),
            output_path=str(out_csv),
        )

        with open(out_csv, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            headers = next(reader)

        assert "file_name" in headers
        assert "xray_tube_voltage" in headers

    def test_convert_respects_column_order(self, temp_dir, mock_metadata_json):
        """CSV columns appear in the order specified by standard_format.json."""
        data_dir = temp_dir / "data"
        data_dir.mkdir()

        (data_dir / "metadata.json").write_text(json.dumps(mock_metadata_json))
        (temp_dir / "users.csv").write_text("")

        fmt = {
            "columns": [
                {"source": "xray_tube_voltage", "name": "Voltage"},
                {"source": "file_name", "name": "File"},
                {"source": "ct_number_images", "name": "Images"},
            ],
            "include_unmapped": False,
        }
        fmt_path = temp_dir / "format.json"
        fmt_path.write_text(json.dumps(fmt))

        out_csv = data_dir / "metadata.csv"
        convert(
            metadata_path=str(data_dir / "metadata.json"),
            users_path=str(temp_dir / "users.csv"),
            format_path=str(fmt_path),
            output_path=str(out_csv),
        )

        with open(out_csv, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            headers = next(reader)

        assert headers == ["Voltage", "File", "Images"]

    def test_convert_uploaded_by_appears_in_csv(self, temp_dir):
        """The uploaded_by field from parsed JSON shows up in CSV output."""
        data_dir = temp_dir / "data"
        data_dir.mkdir()

        metadata = [
            {
                "file_name": "test.pca",
                "uploaded_by": "johntrue15",
                "xray_tube_voltage": "200",
            }
        ]
        (data_dir / "metadata.json").write_text(json.dumps(metadata))
        (temp_dir / "users.csv").write_text("")

        fmt = {
            "columns": [
                {"source": "file_name", "name": "File Name"},
                {"source": "uploaded_by", "name": "Uploaded By"},
                {"source": "X-ray User", "name": "X-ray User"},
            ],
            "include_unmapped": True,
        }
        fmt_path = temp_dir / "format.json"
        fmt_path.write_text(json.dumps(fmt))

        out_csv = data_dir / "metadata.csv"
        convert(
            metadata_path=str(data_dir / "metadata.json"),
            users_path=str(temp_dir / "users.csv"),
            format_path=str(fmt_path),
            output_path=str(out_csv),
        )

        with open(out_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            row = next(reader)

        assert row["Uploaded By"] == "johntrue15"


class TestUploadedByInjection:
    """Test uploaded_by injection in parse_any.py."""

    def test_inject_uploaded_by(self, temp_dir):
        """inject_uploaded_by should add the field to existing JSON."""
        from parse_any import inject_uploaded_by

        json_path = temp_dir / "test.json"
        json_path.write_text(json.dumps({"file_name": "test.pca", "sha256": "abc"}))

        inject_uploaded_by(json_path, "johntrue15")

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["uploaded_by"] == "johntrue15"
        assert data["file_name"] == "test.pca"
        assert data["sha256"] == "abc"

    def test_inject_uploaded_by_overwrites(self, temp_dir):
        """If uploaded_by already exists, it gets overwritten."""
        from parse_any import inject_uploaded_by

        json_path = temp_dir / "test.json"
        json_path.write_text(json.dumps({"file_name": "a.pca", "uploaded_by": "old_user"}))

        inject_uploaded_by(json_path, "new_user")

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["uploaded_by"] == "new_user"
