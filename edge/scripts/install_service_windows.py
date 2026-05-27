"""Install or refresh the rosetta-watchdog Windows service.

Invoked by the per-facility deploy-watchdog.yml workflow on the self-hosted
runner. Uses NSSM if available, otherwise falls back to sc.exe.

Idempotent: safe to call on every deploy. If a service named
``RosettaWatchdog`` already exists it is stopped, reconfigured with the new
config path / install ticket, then restarted.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

SERVICE_NAME = "RosettaWatchdog"
NSSM_URL = "https://nssm.cc/release/nssm-2.24.zip"
INSTALL_DIR = Path(r"C:\rosetta-watchdog")


def _run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    print(f"$ {' '.join(cmd)}", flush=True)
    return subprocess.run(cmd, check=check)


def _find_nssm() -> Path:
    found = shutil.which("nssm")
    if found:
        return Path(found)

    target = INSTALL_DIR / "nssm.exe"
    if target.exists():
        return target

    INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = INSTALL_DIR / "nssm.zip"
    print(f"Downloading nssm from {NSSM_URL}...", flush=True)
    urllib.request.urlretrieve(NSSM_URL, zip_path)
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.namelist():
            if member.endswith("/win64/nssm.exe"):
                with zf.open(member) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                break
    zip_path.unlink(missing_ok=True)
    if not target.exists():
        raise SystemExit("Could not extract nssm.exe from the nssm release zip")
    return target


def _service_exists() -> bool:
    result = subprocess.run(
        ["sc", "query", SERVICE_NAME],
        capture_output=True, text=True,
    )
    return result.returncode == 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Install/refresh the rosetta-watchdog Windows service")
    ap.add_argument("--config", required=True, help="Path to the watchdog config.yml")
    ap.add_argument("--install-ticket", required=True, help="Install ticket from the Cloudflare worker")
    args = ap.parse_args(argv)

    config_path = Path(args.config).resolve()
    if not config_path.exists():
        raise SystemExit(f"Config not found: {config_path}")

    INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    target_config = INSTALL_DIR / "config.yml"
    if config_path.resolve() != target_config.resolve():
        shutil.copy2(config_path, target_config)

    python_exe = sys.executable
    nssm = _find_nssm()

    if _service_exists():
        print(f"Service {SERVICE_NAME} exists — stopping for reconfigure")
        _run([str(nssm), "stop", SERVICE_NAME], check=False)
        _run([str(nssm), "remove", SERVICE_NAME, "confirm"], check=False)

    _run([
        str(nssm), "install", SERVICE_NAME,
        python_exe, "-m", "rosetta_watchdog.cli",
        "-c", str(target_config),
    ])
    _run([str(nssm), "set", SERVICE_NAME, "AppDirectory", str(INSTALL_DIR)])
    _run([str(nssm), "set", SERVICE_NAME, "AppEnvironmentExtra",
          f"ROSETTA_INSTALL_TICKET={args.install_ticket}"])
    _run([str(nssm), "set", SERVICE_NAME, "Start", "SERVICE_AUTO_START"])
    _run([str(nssm), "set", SERVICE_NAME, "AppStdout", str(INSTALL_DIR / "service-stdout.log")])
    _run([str(nssm), "set", SERVICE_NAME, "AppStderr", str(INSTALL_DIR / "service-stderr.log")])
    _run([str(nssm), "set", SERVICE_NAME, "AppRotateFiles", "1"])
    _run([str(nssm), "set", SERVICE_NAME, "AppRotateBytes", "10485760"])

    _run([str(nssm), "start", SERVICE_NAME])
    print(f"Service {SERVICE_NAME} installed and started.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
