"""Install or refresh the rosetta-watchdog service on Linux/macOS.

Invoked by the per-facility deploy-watchdog.yml workflow on the self-hosted
runner. Uses systemd on Linux and launchd on macOS.

Idempotent: rewrites the unit file and reloads / restarts the service on
every invocation.
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

SERVICE_NAME = "rosetta-watchdog"


def _run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    print(f"$ {' '.join(cmd)}", flush=True)
    return subprocess.run(cmd, check=check)


def _install_linux(config_path: Path, install_ticket: str) -> None:
    install_dir = Path("/opt/rosetta-watchdog")
    install_dir.mkdir(parents=True, exist_ok=True)
    target_config = install_dir / "config.yml"
    if config_path.resolve() != target_config.resolve():
        shutil.copy2(config_path, target_config)

    unit_path = Path(f"/etc/systemd/system/{SERVICE_NAME}.service")
    python_exe = sys.executable
    unit = f"""[Unit]
Description=Rosetta Edge Watchdog
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory={install_dir}
Environment=ROSETTA_INSTALL_TICKET={install_ticket}
ExecStart={python_exe} -m rosetta_watchdog.cli -c {target_config}
Restart=always
RestartSec=10
StandardOutput=append:/var/log/rosetta-watchdog.log
StandardError=append:/var/log/rosetta-watchdog.log

[Install]
WantedBy=multi-user.target
"""
    unit_path.write_text(unit)
    _run(["systemctl", "daemon-reload"])
    _run(["systemctl", "enable", SERVICE_NAME])
    _run(["systemctl", "restart", SERVICE_NAME])


def _install_macos(config_path: Path, install_ticket: str) -> None:
    install_dir = Path.home() / "Library" / "Application Support" / "rosetta-watchdog"
    install_dir.mkdir(parents=True, exist_ok=True)
    target_config = install_dir / "config.yml"
    if config_path.resolve() != target_config.resolve():
        shutil.copy2(config_path, target_config)

    plist_dir = Path.home() / "Library" / "LaunchAgents"
    plist_dir.mkdir(parents=True, exist_ok=True)
    plist_path = plist_dir / f"dev.rosetta.{SERVICE_NAME}.plist"
    log_path = install_dir / "watchdog.log"
    python_exe = sys.executable
    plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>dev.rosetta.{SERVICE_NAME}</string>
  <key>ProgramArguments</key>
  <array>
    <string>{python_exe}</string>
    <string>-m</string><string>rosetta_watchdog.cli</string>
    <string>-c</string><string>{target_config}</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>ROSETTA_INSTALL_TICKET</key><string>{install_ticket}</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>{log_path}</string>
  <key>StandardErrorPath</key><string>{log_path}</string>
</dict></plist>
"""
    plist_path.write_text(plist)
    label = f"dev.rosetta.{SERVICE_NAME}"
    _run(["launchctl", "unload", str(plist_path)], check=False)
    _run(["launchctl", "load", str(plist_path)])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Install/refresh the rosetta-watchdog service")
    ap.add_argument("--config", required=True, help="Path to the watchdog config.yml")
    ap.add_argument("--install-ticket", required=True, help="Install ticket from the Cloudflare worker")
    args = ap.parse_args(argv)

    config_path = Path(args.config).resolve()
    if not config_path.exists():
        raise SystemExit(f"Config not found: {config_path}")

    system = platform.system()
    if system == "Linux":
        _install_linux(config_path, args.install_ticket)
    elif system == "Darwin":
        _install_macos(config_path, args.install_ticket)
    else:
        raise SystemExit(f"Unsupported platform: {system}")

    print(f"Service {SERVICE_NAME} installed and started.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
