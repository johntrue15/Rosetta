"""CLI entry point for the Rosetta edge watchdog."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import platform
import sys
import time
from pathlib import Path

from . import __version__
from .config import load_config
from .push.github_api import GitHubPusher
from .watcher import DirectoryWatcher


def _setup_logging(level: str, log_file: str | None) -> None:
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO),
                        format=fmt, handlers=handlers)


def _get_txrm_parser(backend: str):
    """Resolve the TXRM parser backend."""
    if backend in ("auto", "xradiaPy"):
        try:
            from .parsers.xradiaPy_parser import XradiaPyParser
            return XradiaPyParser()
        except ImportError:
            if backend == "xradiaPy":
                logging.getLogger(__name__).error(
                    "XradiaPy not available — install the Zeiss Xradia Software Suite")
                sys.exit(1)
            logging.getLogger(__name__).info(
                "XradiaPy not available, falling back to olefile backend")

    from .parsers.olefile_parser import OlefileParser
    return OlefileParser()


def _get_pca_parser():
    from .parsers.pca_parser import PcaParser
    return PcaParser()


class ParserDispatcher:
    """Routes files to the correct parser based on extension."""

    def __init__(self, txrm_parser, pca_parser):
        self._txrm = txrm_parser
        self._pca = pca_parser

    def parse(self, file_path: str):
        ext = Path(file_path).suffix.lower()
        if ext == ".pca":
            return self._pca.parse(file_path)
        return self._txrm.parse(file_path)


def _log_startup_banner(log, config, config_path: Path) -> None:
    """Log a detailed startup banner for diagnostics."""
    log.info("=" * 60)
    log.info("Rosetta Edge Watchdog v%s", __version__)
    log.info("Python %s on %s (%s)", platform.python_version(),
             platform.system(), platform.machine())
    log.info("Config: %s", config_path.resolve())
    log.info("State:  %s", Path(config.state_file).resolve())
    log.info("-" * 60)

    log.info("Watch directories (%d):", len(config.watch_directories))
    all_dirs_ok = True
    for wd in config.watch_directories:
        exists = Path(wd.path).is_dir()
        status = "OK" if exists else "NOT FOUND"
        log.info("  [%s] %s  (machine: %s)", status, wd.path, wd.machine_name)
        if not exists:
            all_dirs_ok = False

    if not all_dirs_ok:
        log.warning(
            "One or more watch directories do not exist. "
            "The watchdog will keep polling — create them to start processing."
        )

    log.info("Polling interval: %ds", config.polling_interval_seconds)
    log.info("Parser backend: %s", config.parser_backend)
    log.info("Drift files: %s", "included" if config.include_drift_files else "excluded")
    if config.auth.token_url:
        log.info(
            "Auth mode: Worker (%s, ticket env=%s)",
            config.auth.token_url, config.auth.install_ticket_env,
        )
    else:
        log.info("Auth mode: static PAT (env=%s)", config.github.token_env)
    if config.monitoring.heartbeat_url:
        log.info(
            "Fleet monitoring: ON (heartbeat → %s every %ds)",
            config.monitoring.heartbeat_url, config.monitoring.interval_seconds,
        )
    else:
        log.info("Fleet monitoring: off (no monitoring.heartbeat_url in config)")
    log.info("=" * 60)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(
        prog="rosetta-watchdog",
        description="Rosetta edge watchdog — monitors scan directories "
                    "and pushes metadata to GitHub",
    )
    ap.add_argument("-c", "--config", required=True,
                    help="Path to config YAML file")
    ap.add_argument("--once", action="store_true",
                    help="Run one scan cycle then exit (useful for cron)")
    ap.add_argument("--token",
                    help="GitHub PAT (alternative to setting the env var, legacy install)")
    ap.add_argument("--auth-token-url",
                    help="Cloudflare Worker URL that mints rotating App tokens "
                         "(overrides auth.token_url in config.yml)")
    ap.add_argument("--install-ticket",
                    help="Install ticket from the setup wizard (alternative to "
                         "setting ROSETTA_INSTALL_TICKET in the environment)")
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = ap.parse_args(argv)

    if args.token:
        os.environ["ROSETTA_GITHUB_TOKEN"] = args.token

    config_path = Path(args.config)
    config = load_config(config_path)

    if args.auth_token_url:
        config.auth.token_url = args.auth_token_url
    if args.install_ticket:
        os.environ[config.auth.install_ticket_env] = args.install_ticket

    _setup_logging(config.logging.level, config.logging.file)
    log = logging.getLogger(__name__)

    _log_startup_banner(log, config, config_path)

    txrm_parser = _get_txrm_parser(config.parser_backend)
    pca_parser = _get_pca_parser()
    parser = ParserDispatcher(txrm_parser, pca_parser)
    log.info("Parser backends: txrm=%s, pca=%s",
             type(txrm_parser).__name__, type(pca_parser).__name__)

    pusher = None
    repo_ok = bool(config.github.repo)
    worker_auth = bool(config.auth.token_url)
    static_token_ok = bool(config.github.token)
    install_ticket_ok = bool(os.environ.get(config.auth.install_ticket_env))
    auth_ok = (worker_auth and install_ticket_ok) or static_token_ok

    log.info(
        "GitHub config: repo=%r  worker_auth=%s  install_ticket_set=%s  static_token_set=%s",
        config.github.repo, worker_auth, install_ticket_ok, static_token_ok,
    )

    if auth_ok and repo_ok:
        pusher = GitHubPusher(config.github, config.auth)
        mode = "Worker (rotating App token)" if worker_auth and install_ticket_ok else "static PAT"
        log.info(
            "GitHub push enabled via %s → %s (%s)",
            mode, config.github.repo, config.github.branch,
        )
    else:
        reasons = []
        if not auth_ok:
            if worker_auth:
                reasons.append(
                    f"Worker auth configured but ${config.auth.install_ticket_env} "
                    f"is not set in the environment"
                )
            else:
                reasons.append(
                    f"no PAT in ${config.github.token_env} and no Worker auth configured"
                )
        if not repo_ok:
            reasons.append("github.repo is empty in config.yml")
        log.warning(
            "GitHub push disabled — %s\n"
            "  Modern install (managed by the wizard):\n"
            "    set %s=<install-ticket from the setup wizard>\n"
            "  Legacy PAT install:\n"
            "    PowerShell:  $env:%s = \"ghp_...\"\n"
            "    CMD:         set %s=ghp_...\n"
            "    Mac/Linux:   export %s=\"ghp_...\"",
            "; ".join(reasons),
            config.auth.install_ticket_env,
            config.github.token_env, config.github.token_env, config.github.token_env,
        )

    if not pusher:
        log.error("Cannot run without GitHub push configured — exiting")
        sys.exit(1)

    def process_file(file_path: str, machine_name: str) -> bool:
        log.info("Parsing %s (machine: %s)", file_path, machine_name)
        t0 = time.monotonic()

        metadata = parser.parse(file_path)
        if metadata is None:
            log.error("Parser returned None for %s", file_path)
            return False

        parse_ms = (time.monotonic() - t0) * 1000
        metadata["machine_name"] = machine_name

        sha256 = hashlib.sha256(Path(file_path).read_bytes()).hexdigest()
        metadata["sha256"] = sha256

        json_bytes = json.dumps(metadata, ensure_ascii=False, indent=2).encode("utf-8")
        filename = Path(file_path).name + ".json"
        remote_path = config.github.upload_path + filename

        log.info(
            "Parsed %s (%.0fms, %d bytes JSON, sha256: %s…) → pushing to %s",
            Path(file_path).name, parse_ms, len(json_bytes),
            sha256[:12], remote_path,
        )

        ok = pusher.push_file(
            content=json_bytes,
            remote_path=remote_path,
            commit_message=(
                f"{config.github.commit_prefix} {Path(file_path).name} "
                f"[uploader:edge-watchdog-{machine_name}]"
            ),
            content_sha256=sha256,
        )
        if not ok:
            log.error("Failed to push %s to GitHub", filename)
            return False

        return True

    heartbeat = None
    if config.monitoring.heartbeat_url and (worker_auth and install_ticket_ok):
        from .push.heartbeat import HeartbeatReporter
        heartbeat = HeartbeatReporter(
            config.monitoring, config.auth, config.github, __version__,
        )

    watcher = DirectoryWatcher(config, process_file, heartbeat=heartbeat)

    if args.once:
        count = watcher.run_once()
        log.info("Single scan complete — processed %d file(s)", count)
    else:
        watcher.run_forever()


if __name__ == "__main__":
    main()
