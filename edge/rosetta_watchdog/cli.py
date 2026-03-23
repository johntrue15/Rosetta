"""CLI entry point for the Rosetta edge watchdog."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
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
                    help="GitHub PAT (alternative to setting the env var)")
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = ap.parse_args(argv)

    if args.token:
        os.environ["ROSETTA_GITHUB_TOKEN"] = args.token

    config = load_config(Path(args.config))
    _setup_logging(config.logging.level, config.logging.file)
    log = logging.getLogger(__name__)

    txrm_parser = _get_txrm_parser(config.parser_backend)
    pca_parser = _get_pca_parser()
    parser = ParserDispatcher(txrm_parser, pca_parser)
    log.info("Parser backends: txrm=%s, pca=%s", type(txrm_parser).__name__, type(pca_parser).__name__)

    pusher = None
    token_ok = bool(config.github.token)
    repo_ok = bool(config.github.repo)
    log.info(
        "GitHub config: token_env=%s token_set=%s repo=%r",
        config.github.token_env, token_ok, config.github.repo,
    )
    if token_ok and repo_ok:
        pusher = GitHubPusher(config.github)
        log.info("GitHub push enabled → %s (%s)", config.github.repo, config.github.branch)
    else:
        reasons = []
        if not token_ok:
            reasons.append(
                f"env var ${config.github.token_env} is not set"
            )
        if not repo_ok:
            reasons.append(
                "github.repo is empty in config.yml"
            )
        log.warning(
            "GitHub push disabled — %s\n"
            "  PowerShell:  $env:%s = \"ghp_...\"\n"
            "  CMD:         set %s=ghp_...\n"
            "  Mac/Linux:   export %s=\"ghp_...\"",
            "; ".join(reasons),
            config.github.token_env, config.github.token_env, config.github.token_env,
        )

    if not pusher:
        log.error("Cannot run without GitHub push configured — exiting")
        sys.exit(1)

    def process_file(file_path: str, machine_name: str) -> bool:
        log.info("Parsing %s (machine: %s)", file_path, machine_name)
        metadata = parser.parse(file_path)
        if metadata is None:
            return False

        metadata["machine_name"] = machine_name

        sha256 = hashlib.sha256(Path(file_path).read_bytes()).hexdigest()
        metadata["sha256"] = sha256

        json_bytes = json.dumps(metadata, ensure_ascii=False, indent=2).encode("utf-8")
        filename = Path(file_path).name + ".json"

        ok = pusher.push_file(
            content=json_bytes,
            remote_path=config.github.upload_path + filename,
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

    watcher = DirectoryWatcher(config, process_file)

    if args.once:
        count = watcher.run_once()
        log.info("Single scan complete — processed %d file(s)", count)
    else:
        watcher.run_forever()


if __name__ == "__main__":
    main()
