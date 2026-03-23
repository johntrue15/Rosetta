"""Tests for rosetta_watchdog.config — config loading and validation."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml

from rosetta_watchdog.config import ConfigError, load_config


def _write_yaml(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "config.yml"
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return p


class TestLoadConfigMissingFile:
    def test_raises_on_missing_file(self, tmp_path):
        with pytest.raises(ConfigError, match="not found"):
            load_config(tmp_path / "nonexistent.yml")


class TestLoadConfigInvalidYAML:
    def test_raises_on_invalid_yaml(self, tmp_path):
        bad = tmp_path / "bad.yml"
        bad.write_text(":\n  - :\n  :\n-: {bad", encoding="utf-8")
        with pytest.raises(ConfigError, match="Invalid YAML"):
            load_config(bad)


class TestLoadConfigWatchDirectories:
    def test_valid_watch_directories(self, tmp_path):
        cfg_path = _write_yaml(tmp_path, """\
            watch_directories:
              - path: "/data/scans"
                machine_name: "scanner-1"
        """)
        config = load_config(cfg_path)
        assert len(config.watch_directories) == 1
        assert config.watch_directories[0].path == "/data/scans"
        assert config.watch_directories[0].machine_name == "scanner-1"

    def test_missing_path_key(self, tmp_path):
        cfg_path = _write_yaml(tmp_path, """\
            watch_directories:
              - machine_name: "scanner-1"
        """)
        with pytest.raises(ConfigError, match="watch_directories\\[0\\].*'path'"):
            load_config(cfg_path)

    def test_missing_machine_name_key(self, tmp_path):
        cfg_path = _write_yaml(tmp_path, """\
            watch_directories:
              - path: "/data/scans"
        """)
        with pytest.raises(ConfigError, match="watch_directories\\[0\\].*'machine_name'"):
            load_config(cfg_path)

    def test_non_dict_entry(self, tmp_path):
        cfg_path = _write_yaml(tmp_path, """\
            watch_directories:
              - "just a string"
        """)
        with pytest.raises(ConfigError, match="watch_directories\\[0\\]"):
            load_config(cfg_path)


class TestLoadConfigDefaults:
    def test_empty_yaml_uses_defaults(self, tmp_path):
        cfg_path = _write_yaml(tmp_path, "")
        config = load_config(cfg_path)
        assert config.watch_directories == []
        assert config.polling_interval_seconds == 30
        assert config.include_drift_files is False
        assert config.parser_backend == "auto"
        assert config.github.token_env == "ROSETTA_GITHUB_TOKEN"
        assert config.github.repo == ""
        assert config.state_file == "processed_files.json"

    def test_github_token_from_env(self, tmp_path, monkeypatch):
        cfg_path = _write_yaml(tmp_path, """\
            github:
              token_env: "MY_TOKEN"
              repo: "owner/repo"
        """)
        monkeypatch.setenv("MY_TOKEN", "ghp_test123")
        config = load_config(cfg_path)
        assert config.github.token == "ghp_test123"

    def test_github_token_missing_returns_none(self, tmp_path, monkeypatch):
        cfg_path = _write_yaml(tmp_path, """\
            github:
              token_env: "NONEXISTENT_VAR"
        """)
        monkeypatch.delenv("NONEXISTENT_VAR", raising=False)
        config = load_config(cfg_path)
        assert config.github.token is None
