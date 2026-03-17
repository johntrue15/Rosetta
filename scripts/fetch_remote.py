#!/usr/bin/env python3
"""
fetch_remote.py

Download files from remote URLs (Dropbox, Google Drive, direct HTTP).
Handles provider-specific quirks like Dropbox's sharing API and
Google Drive virus-scan confirmation pages.

Usage:
  python scripts/fetch_remote.py <url> -o <output_dir> [--name <filename>]
"""

import argparse
import json
import os
import re
import shutil
import sys
import zipfile
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import requests


def _detect_provider(url: str) -> str:
    host = urlparse(url).hostname or ""
    if "dropbox.com" in host or "dropboxusercontent.com" in host:
        return "dropbox"
    if "drive.google.com" in host:
        return "gdrive"
    return "http"


def _download_dropbox(url: str, dest: Path) -> None:
    """Use the Dropbox content API to download a shared link.

    POST https://content.dropboxapi.com/2/sharing/get_shared_link_file
    works for public shared links with no auth token required.
    """
    # Normalise the URL back to www.dropbox.com form for the API arg
    canonical = url.replace("dl.dropboxusercontent.com", "www.dropbox.com")
    canonical = re.sub(r'[?&]dl=[01]', '', canonical)

    api_arg = json.dumps({"url": canonical})

    print(f"Dropbox API download: {canonical}")
    resp = requests.post(
        "https://content.dropboxapi.com/2/sharing/get_shared_link_file",
        headers={
            "Dropbox-API-Arg": api_arg,
        },
        stream=True,
        timeout=600,
    )

    if resp.status_code != 200:
        # Fallback: try wget-style direct download with cookies
        print(f"Dropbox API returned {resp.status_code}, trying direct download...")
        _download_dropbox_direct(url, dest)
        return

    total = int(resp.headers.get("content-length", 0))
    downloaded = 0
    with open(dest, "wb") as f:
        for chunk in resp.iter_content(chunk_size=1024 * 1024):
            f.write(chunk)
            downloaded += len(chunk)
            if total > 0:
                pct = downloaded * 100 // total
                print(f"\r  {downloaded:,} / {total:,} bytes ({pct}%)", end="", flush=True)
            else:
                print(f"\r  {downloaded:,} bytes", end="", flush=True)
    print()


def _download_dropbox_direct(url: str, dest: Path) -> None:
    """Fallback: try a session-based download that handles redirects and cookies."""
    session = requests.Session()
    # Rewrite to dl=1
    dl_url = url.replace("dl=0", "dl=1")
    if "dl=1" not in dl_url:
        separator = "&" if "?" in dl_url else "?"
        dl_url += separator + "dl=1"

    resp = session.get(dl_url, stream=True, timeout=600, allow_redirects=True)
    resp.raise_for_status()

    total = int(resp.headers.get("content-length", 0))
    downloaded = 0
    with open(dest, "wb") as f:
        for chunk in resp.iter_content(chunk_size=1024 * 1024):
            f.write(chunk)
            downloaded += len(chunk)
            if total > 0:
                pct = downloaded * 100 // total
                print(f"\r  {downloaded:,} / {total:,} bytes ({pct}%)", end="", flush=True)
            else:
                print(f"\r  {downloaded:,} bytes", end="", flush=True)
    print()


def _download_gdrive(url: str, dest: Path) -> None:
    """Download from a Google Drive share link, handling the virus-scan confirm page."""
    # Extract file ID
    m = re.search(r'/d/([a-zA-Z0-9_-]+)', url)
    if not m:
        qs = parse_qs(urlparse(url).query)
        file_id = qs.get("id", [None])[0]
    else:
        file_id = m.group(1)

    if not file_id:
        raise ValueError(f"Could not extract Google Drive file ID from: {url}")

    session = requests.Session()
    dl_url = f"https://drive.google.com/uc?export=download&id={file_id}"

    resp = session.get(dl_url, stream=True, timeout=600)

    # Check for the "confirm download" page (large file virus scan warning)
    if "text/html" in resp.headers.get("content-type", ""):
        confirm_token = None
        for k, v in resp.cookies.items():
            if k.startswith("download_warning"):
                confirm_token = v
                break
        if confirm_token:
            dl_url += f"&confirm={confirm_token}"
            resp = session.get(dl_url, stream=True, timeout=600)

    resp.raise_for_status()
    total = int(resp.headers.get("content-length", 0))
    downloaded = 0
    with open(dest, "wb") as f:
        for chunk in resp.iter_content(chunk_size=1024 * 1024):
            f.write(chunk)
            downloaded += len(chunk)
            if total > 0:
                pct = downloaded * 100 // total
                print(f"\r  {downloaded:,} / {total:,} bytes ({pct}%)", end="", flush=True)
            else:
                print(f"\r  {downloaded:,} bytes", end="", flush=True)
    print()


def _download_http(url: str, dest: Path) -> None:
    """Plain HTTP(S) download with streaming."""
    resp = requests.get(url, stream=True, timeout=600, allow_redirects=True)
    resp.raise_for_status()

    total = int(resp.headers.get("content-length", 0))
    downloaded = 0
    with open(dest, "wb") as f:
        for chunk in resp.iter_content(chunk_size=1024 * 1024):
            f.write(chunk)
            downloaded += len(chunk)
            if total > 0:
                pct = downloaded * 100 // total
                print(f"\r  {downloaded:,} / {total:,} bytes ({pct}%)", end="", flush=True)
            else:
                print(f"\r  {downloaded:,} bytes", end="", flush=True)
    print()


def download(url: str, out_dir: Path, name: str | None = None) -> list[Path]:
    """Download a remote file, extract if ZIP, return list of downloaded file paths."""
    out_dir.mkdir(parents=True, exist_ok=True)

    if not name:
        # Extract from URL path, stripping query params
        name = Path(urlparse(url).path).name or "download"

    dest = out_dir / name
    provider = _detect_provider(url)
    print(f"Provider: {provider} | Target: {dest}")

    if provider == "dropbox":
        _download_dropbox(url, dest)
    elif provider == "gdrive":
        _download_gdrive(url, dest)
    else:
        _download_http(url, dest)

    # Validate
    if not dest.exists() or dest.stat().st_size == 0:
        print(f"ERROR: Download produced empty or missing file: {dest}", file=sys.stderr)
        sys.exit(1)

    size = dest.stat().st_size
    print(f"Downloaded: {dest.name} ({size:,} bytes)")

    # Check if we got HTML instead of a binary
    with open(dest, "rb") as f:
        header = f.read(256)
    if b"<!DOCTYPE" in header or b"<html" in header.lower():
        print(f"ERROR: Downloaded file appears to be HTML, not binary.", file=sys.stderr)
        print(f"First 256 bytes: {header[:256]}", file=sys.stderr)
        dest.unlink()
        sys.exit(1)

    # Unzip if needed
    if zipfile.is_zipfile(dest):
        print(f"Extracting ZIP: {dest.name}")
        extract_dir = out_dir / "_extracted"
        extract_dir.mkdir(exist_ok=True)
        with zipfile.ZipFile(dest) as zf:
            zf.extractall(extract_dir)
        dest.unlink()

        extracted = []
        for f in extract_dir.rglob("*"):
            if f.is_file():
                target = out_dir / f.name
                shutil.move(str(f), str(target))
                extracted.append(target)
                print(f"  Extracted: {target.name}")
        shutil.rmtree(extract_dir, ignore_errors=True)
        return extracted

    return [dest]


def main():
    ap = argparse.ArgumentParser(description="Download remote files for Rosetta")
    ap.add_argument("url", help="Remote file URL (Dropbox, Google Drive, HTTP)")
    ap.add_argument("-o", "--out-dir", required=True, help="Output directory")
    ap.add_argument("--name", default=None, help="Override output filename")
    args = ap.parse_args()

    files = download(args.url, Path(args.out_dir), args.name)
    # Output file list for shell consumption
    print("FILES=" + " ".join(str(f) for f in files))


if __name__ == "__main__":
    main()
