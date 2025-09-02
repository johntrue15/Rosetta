#!/usr/bin/env python3
import csv
import json
import os
import re
from pathlib import PurePosixPath, PureWindowsPath

METADATA_JSON = "data/metadata.json"
USERS_CSV     = "data/users.csv"
OUTPUT_CSV    = "data/metadata.csv"

# -------- Helpers

def read_json(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Missing {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def detect_delimiter(sample):
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=[",", "\t", ";", "|"])
        return dialect.delimiter
    except Exception:
        # Fallbacks: prefer tab (your example), then comma
        return "\t" if "\t" in sample else ","

def read_users_map(path):
    """
    Reads data/users.csv and returns a dict:
      { normalized_folder_name : email }
    Assumptions:
      - First column = folder key (what appears as a path component)
      - Last column = email
      - There may or may not be a header row. If present and includes
        'folder' and 'email' (any case), we honor it. Otherwise:
        col0=folder, col_last=email.
    """
    if not os.path.exists(path):
        return {}

    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        sample = f.read(2048)
        f.seek(0)
        delim = detect_delimiter(sample)
        reader = csv.reader(f, delimiter=delim)
        rows = [r for r in reader if any(cell.strip() for cell in r)]

    if not rows:
        return {}

    # Check for header
    header = [c.strip().lower() for c in rows[0]]
    has_header = ("folder" in header and "email" in header) or ("name" in header and "email" in header)

    folder_idx = 0
    email_idx = -1
    start = 1 if has_header else 0
    if has_header:
        # Prefer 'folder' if present, else 'name'
        if "folder" in header:
            folder_idx = header.index("folder")
        elif "name" in header:
            folder_idx = header.index("name")
        email_idx = header.index("email")

    mapping = {}
    for r in rows[start:]:
        if not r:
            continue
        # Tolerant indexing
        if len(r) == 1:
            # Only one column? Can't map email—skip.
            continue
        fkey = r[folder_idx].strip()
        email = r[email_idx].strip() if email_idx != -1 else r[-1].strip()
        if fkey and email:
            mapping[normalize(fkey)] = email
    return mapping

def normalize(s):
    return re.sub(r"\s+", " ", s.strip().lower())

def split_path_components(any_path_str):
    """
    Split a path string into components, handling both Windows and POSIX.
    """
    # Use regex split on both separators
    parts = [p for p in re.split(r"[\\/]+", any_path_str) if p]
    return parts

def gather_candidate_paths(meta):
    """
    Collect all path-like fields from a metadata record where a user-folder might appear.
    Priority order: file_path, txrm_file_path, calib_images.* entries, source_path.
    """
    candidates = []
    def maybe_add(val):
        if isinstance(val, str) and val.strip() and val.strip().lower() != "n/a":
            candidates.append(val.strip())

    # top-level
    for k in ("file_path", "txrm_file_path", "source_path"):
        if k in meta:
            maybe_add(meta[k])

    # nested calib_images paths (if present)
    calib = meta.get("calib_images", {})
    if isinstance(calib, dict):
        for k in ("MGainImg", "OffsetImg", "GainImg", "DefPixelImg", "calib_folder_path"):
            if k in calib:
                maybe_add(calib[k])

    return candidates

def find_user_email_for_record(meta, users_map):
    """
    Try to match any folder component found in candidate paths against keys in users_map.
    If multiple match, prefer the longest folder key (most specific).
    """
    if not users_map:
        return ""

    candidates = gather_candidate_paths(meta)
    if not candidates:
        return ""

    # Collect matches as (key, email)
    matches = []
    for p in candidates:
        # Remove URI prefixes like file:// if present
        p2 = re.sub(r"^file:(/{2,3})?", "", p, flags=re.IGNORECASE).strip()
        # Split into components
        comps = split_path_components(p2)
        for c in comps:
            c_norm = normalize(c)
            if c_norm in users_map:
                matches.append((c_norm, users_map[c_norm]))

    if not matches:
        return ""

    # Pick the match with the longest key (most specific)
    best = max(matches, key=lambda x: len(x[0]))
    return best[1]

def flatten_dict(d, prefix="", out=None):
    if out is None:
        out = {}
    for k, v in d.items():
        key = f"{prefix}{k}" if not prefix else f"{prefix}.{k}"
        if isinstance(v, dict):
            flatten_dict(v, key, out)
        else:
            out[key] = v
    return out

# -------- Main conversion

def main():
    data = read_json(METADATA_JSON)
    if not isinstance(data, list):
        raise ValueError("metadata.json must contain a list of objects")

    users_map = read_users_map(USERS_CSV)

    # Flatten and build field set
    rows = []
    fieldnames = set()
    for rec in data:
        flat = flatten_dict(rec)
        email = find_user_email_for_record(rec, users_map)
        flat["X-ray User"] = email
        rows.append(flat)
        fieldnames.update(flat.keys())

    # Ensure consistent, readable column order:
    # 1) Put a few common fields first if present
    preferred = [
        "file_name",
        "file_hyperlink",
        "file_path",
        "txrm_file_path",
        "start_time",
        "end_time",
        "ct_voxel_size_um",
        "ct_objective",
        "ct_number_images",
        "xray_tube_voltage",
        "xray_tube_current",
        "xray_tube_power",
        "xray_filter",
        "image_width_pixels",
        "image_height_pixels",
        "scan_time",
        "sha256",
        "source_path",
    ]
    # Append all other fields (sorted) except X-ray User, then finally X-ray User
    remaining = sorted(fn for fn in fieldnames if fn not in preferred and fn != "X-ray User")
    ordered = [fn for fn in preferred if fn in fieldnames] + remaining + ["X-ray User"]

    os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)
    with open(OUTPUT_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=ordered, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in ordered})

if __name__ == "__main__":
    main()
