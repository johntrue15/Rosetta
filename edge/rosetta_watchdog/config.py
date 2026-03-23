"""YAML configuration loader for the Rosetta edge watchdog."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import yaml


@dataclass
class WatchDirectory:
    path: str
    machine_name: str


@dataclass
class GitHubConfig:
    token_env: str = "ROSETTA_GITHUB_TOKEN"
    repo: str = ""
    branch: str = "main"
    upload_path: str = "data/"
    commit_prefix: str = "[edge-watchdog]"

    @property
    def token(self) -> Optional[str]:
        return os.environ.get(self.token_env)

    @property
    def owner(self) -> str:
        parts = self.repo.split("/", 1)
        return parts[0] if len(parts) == 2 else ""

    @property
    def repo_name(self) -> str:
        parts = self.repo.split("/", 1)
        return parts[1] if len(parts) == 2 else self.repo


@dataclass
class LoggingConfig:
    level: str = "INFO"
    file: Optional[str] = None


@dataclass
class WatchdogConfig:
    watch_directories: List[WatchDirectory] = field(default_factory=list)
    polling_interval_seconds: int = 30
    include_drift_files: bool = False
    parser_backend: str = "auto"
    github: GitHubConfig = field(default_factory=GitHubConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    state_file: str = "processed_files.json"


class ConfigError(Exception):
    """Raised when the configuration file cannot be loaded or is invalid."""


def load_config(path: Path) -> WatchdogConfig:
    """Load watchdog configuration from a YAML file."""
    if not path.exists():
        raise ConfigError(
            f"Configuration file not found: {path}\n"
            "Copy config.example.yml to config.yml and edit for your environment."
        )

    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {path}: {exc}") from exc

    raw_dirs = raw.get("watch_directories", [])
    watch_dirs: List[WatchDirectory] = []
    for i, d in enumerate(raw_dirs):
        if not isinstance(d, dict) or "path" not in d or "machine_name" not in d:
            raise ConfigError(
                f"watch_directories[{i}] must have 'path' and 'machine_name' keys"
            )
        watch_dirs.append(WatchDirectory(path=d["path"], machine_name=d["machine_name"]))

    gh_raw = raw.get("github", {})
    github = GitHubConfig(
        token_env=gh_raw.get("token_env", "ROSETTA_GITHUB_TOKEN"),
        repo=gh_raw.get("repo", ""),
        branch=gh_raw.get("branch", "main"),
        upload_path=gh_raw.get("upload_path", "data/"),
        commit_prefix=gh_raw.get("commit_prefix", "[edge-watchdog]"),
    )

    log_raw = raw.get("logging", {})
    logging_cfg = LoggingConfig(
        level=log_raw.get("level", "INFO"),
        file=log_raw.get("file"),
    )

    return WatchdogConfig(
        watch_directories=watch_dirs,
        polling_interval_seconds=raw.get("polling_interval_seconds", 30),
        include_drift_files=raw.get("include_drift_files", False),
        parser_backend=raw.get("parser_backend", "auto"),
        github=github,
        logging=logging_cfg,
        state_file=raw.get("state_file", "processed_files.json"),
    )
