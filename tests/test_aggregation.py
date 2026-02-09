"""
Tests for JSON aggregation and deduplication logic.
"""

import json
import sys
from pathlib import Path

import pytest

# Import the aggregation functions
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from aggregate_json import dedupe_key, records_from_data, load_json_safely


class TestDedupeKey:
    """Test deduplication key generation."""

    def test_dedupe_key_uses_id_first(self):
        """Test that 'id' field takes priority."""
        record = {"id": "test-123", "uuid": "uuid-456", "filename": "file.txt"}
        key = dedupe_key(record)
        assert key == "id:test-123"

    def test_dedupe_key_uses_uuid_second(self):
        """Test that 'uuid' is used if 'id' is missing."""
        record = {"uuid": "uuid-456", "filename": "file.txt"}
        key = dedupe_key(record)
        assert key == "uuid:uuid-456"

    def test_dedupe_key_uses_source_path(self):
        """Test that 'source_path' is used for deduplication."""
        record = {"source_path": "data/parsed/file.json", "filename": "file.txt"}
        key = dedupe_key(record)
        assert key == "source_path:data/parsed/file.json"

    def test_dedupe_key_uses_filename(self):
        """Test that 'filename' is used if other keys are missing."""
        record = {"filename": "test.pca"}
        key = dedupe_key(record)
        assert key == "filename:test.pca"

    def test_dedupe_key_falls_back_to_hash(self):
        """Test that SHA256 hash is used as fallback."""
        record = {"some_field": "some_value"}
        key = dedupe_key(record)
        # Should be a 64-character hex string (SHA256)
        assert len(key) == 64

    def test_dedupe_key_same_content_same_hash(self):
        """Test that identical records produce the same hash."""
        record1 = {"field": "value", "number": 42}
        record2 = {"field": "value", "number": 42}
        assert dedupe_key(record1) == dedupe_key(record2)

    def test_dedupe_key_different_content_different_hash(self):
        """Test that different records produce different hashes."""
        record1 = {"field": "value1"}
        record2 = {"field": "value2"}
        assert dedupe_key(record1) != dedupe_key(record2)


class TestRecordsFromData:
    """Test record extraction from JSON data."""

    def test_records_from_single_dict(self):
        """Test extracting records from a single dict."""
        data = {"file_name": "test.pca", "voltage": "200"}
        records = records_from_data(data, "path/to/file.json")

        assert len(records) == 1
        assert records[0]["file_name"] == "test.pca"
        assert records[0]["source_path"] == "path/to/file.json"

    def test_records_from_list(self):
        """Test extracting records from a list of dicts."""
        data = [
            {"file_name": "test1.pca"},
            {"file_name": "test2.pca"},
        ]
        records = records_from_data(data, "path/to/file.json")

        assert len(records) == 2
        assert records[0]["file_name"] == "test1.pca"
        assert records[1]["file_name"] == "test2.pca"
        # Both should have source_path set
        assert all(r["source_path"] == "path/to/file.json" for r in records)

    def test_records_from_none(self):
        """Test that None returns empty list."""
        records = records_from_data(None, "path")
        assert records == []

    def test_records_wraps_non_dict(self):
        """Test that non-dict items are wrapped."""
        data = ["string_value"]
        records = records_from_data(data, "path")
        assert len(records) == 1
        assert "_raw" in records[0]


class TestAggregation:
    """Test the full aggregation process."""

    def test_aggregation_creates_metadata_json(self, temp_dir):
        """Test that aggregation creates metadata.json file."""
        # Create some parsed JSON files
        parsed_dir = temp_dir / "data" / "parsed"
        parsed_dir.mkdir(parents=True)

        json1 = {"file_name": "test1.pca", "sha256": "hash1"}
        json2 = {"file_name": "test2.pca", "sha256": "hash2"}

        (parsed_dir / "test1.pca.json").write_text(json.dumps(json1))
        (parsed_dir / "test2.pca.json").write_text(json.dumps(json2))

        # Run aggregation
        import subprocess

        result = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).parent.parent / "scripts" / "aggregate_json.py"),
                "--roots",
                str(temp_dir / "data"),
                "--out",
                str(temp_dir / "data" / "metadata.json"),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Aggregation failed: {result.stderr}"

        # Check output
        output_path = temp_dir / "data" / "metadata.json"
        assert output_path.exists()

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert len(data) == 2

    def test_aggregation_deduplicates(self, temp_dir):
        """Test that aggregation deduplicates records."""
        parsed_dir = temp_dir / "data" / "parsed"
        parsed_dir.mkdir(parents=True)

        # Two files with same source_path (should dedupe)
        json1 = {"source_path": "same/path.json", "version": 1}
        json2 = {"source_path": "same/path.json", "version": 2}  # Should override

        (parsed_dir / "test1.json").write_text(json.dumps(json1))
        (parsed_dir / "test2.json").write_text(json.dumps(json2))

        import subprocess

        result = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).parent.parent / "scripts" / "aggregate_json.py"),
                "--roots",
                str(temp_dir / "data"),
                "--out",
                str(temp_dir / "data" / "metadata.json"),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0

        with open(temp_dir / "data" / "metadata.json", "r", encoding="utf-8") as f:
            data = json.load(f)

        # Should only have one record (deduplicated)
        assert len(data) == 1

    def test_aggregation_preserves_existing(self, temp_dir):
        """Test that aggregation preserves existing records."""
        data_dir = temp_dir / "data"
        parsed_dir = data_dir / "parsed"
        parsed_dir.mkdir(parents=True)

        # Create existing metadata.json
        existing = [{"id": "existing-record", "data": "original"}]
        (data_dir / "metadata.json").write_text(json.dumps(existing))

        # Add a new parsed file
        new_record = {"id": "new-record", "data": "new"}
        (parsed_dir / "new.json").write_text(json.dumps(new_record))

        import subprocess

        result = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).parent.parent / "scripts" / "aggregate_json.py"),
                "--roots",
                str(data_dir),
                "--out",
                str(data_dir / "metadata.json"),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0

        with open(data_dir / "metadata.json", "r", encoding="utf-8") as f:
            data = json.load(f)

        # Should have both records
        assert len(data) == 2
        ids = {r["id"] for r in data}
        assert "existing-record" in ids
        assert "new-record" in ids
