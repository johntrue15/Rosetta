"""Tests for rosetta_watchdog.cli — CLI entry point error handling."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from rosetta_watchdog.cli import main


class TestMainConfigErrors:
    def test_missing_config_file_exits(self, tmp_path):
        """CLI exits with code 1 and prints error when config file is missing."""
        with pytest.raises(SystemExit) as exc_info:
            main(["-c", str(tmp_path / "missing.yml")])
        assert exc_info.value.code == 1

    def test_invalid_yaml_exits(self, tmp_path):
        """CLI exits with code 1 when config file is invalid YAML."""
        bad = tmp_path / "bad.yml"
        bad.write_text(":\n  - :\n  :\n-: {bad", encoding="utf-8")
        with pytest.raises(SystemExit) as exc_info:
            main(["-c", str(bad)])
        assert exc_info.value.code == 1

    def test_invalid_watch_dirs_exits(self, tmp_path):
        """CLI exits with code 1 when watch_directories entries are malformed."""
        cfg = tmp_path / "config.yml"
        cfg.write_text(
            textwrap.dedent("""\
                watch_directories:
                  - wrong_key: "value"
            """),
            encoding="utf-8",
        )
        with pytest.raises(SystemExit) as exc_info:
            main(["-c", str(cfg)])
        assert exc_info.value.code == 1
