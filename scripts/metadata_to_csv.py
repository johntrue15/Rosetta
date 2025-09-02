#!/usr/bin/env python3
"""
metadata_to_csv.py

- Reads data/metadata.json (list of dicts; may include nested dicts like calib_images)
- Reads data/users.csv (Folder,User name,Email) — delimiter can be tab or comma (auto-detected)
- Produces data/metadata.csv with all flattened fields + an appended "X-ray User" column.

Matching strategy (most-specific wins):
  1) Component match: if ANY path component in a record equals the users.csv "Folder" (case/space-insensitive)
  2) Substring match: if users.csv "Folder" is a full/partial path, match as a substring against the record's full path
In both cases, ties are resolved by the length of the matched key (longer = more specific).

Set env LOG_MATCHES=1 to print diagnostic logs.
"""
import csv
import json
import os
import re
from pathlib import Path
from typing import Dict, List, Tuple

METADATA_JSON = "data/metadata.json"
USERS_CSV     = "users.csv"
OUTPUT_CSV    = "data/metadata.csv"

DEBUG = os.getenv("LOG_MATCHES", "0") == "1"

# -------------------- utilities --------------------

def read_json(path: str):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Missing {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def detect_delimiter(sample: str) -> str:
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=[",", "\t", ";", "|"])
        return dialect.delimiter
    except Exception:
        return "\t" if "\t" in sample else ","

def normalize_component(s: str) -> str:
    """Normalize a single path component or short token."""
    return re.sub(r"\s+", " ", s.strip().lower())

def normalize_path(s: str) -> str:
    """Normalize a full path for reliable substring checks."""
    s = s.strip()
    s = re.sub(r"^file:(/{2,3})?", "", s, flags=re.IGNORECASE)  # strip file://
    s = s.replace("\\", "/")
    s = re.sub(r"/+", "/", s)
    s = re.sub(r"\s+", " ", s).lower()
    return s

def split_path_components(any_path_str: str) -> List[str]:
    """Split into components across Windows/POSIX separators."""
    comps = [p for p in re.split(r"[\\/]+", any_path_str) if p]
    return comps

def flatten_dict(d: dict, prefix: str = "", out: dict = None) -> dict:
    if out is None:
        out = {}
    for k, v in d.items():
        key = f"{prefix}{k}" if not prefix else f"{prefix}.{k}"
        if isinstance(v, dict):
            flatten_dict(v, key, out)
        else:
            out[key] = v
    return out

# -------------------- users.csv handling --------------------

class UsersIndex:
    """
    Holds two matching structures:
      - component_map: { normalized_component : email }
      - path_list: [ (normalized_full_path, email) ]  for substring matches
    """
    def __init__(self, component_map: Dict[str, str], path_list: List[Tuple[str, str]]):
        self.component_map = component_map
        self.path_list = path_list

def read_users_index(path: str) -> UsersIndex:
    """
    Reads data/users.csv and builds:
      component_map: keys are normalized short tokens (e.g., 'stanley', 'fics')
      path_list: normalized full paths for substring matches (e.g., 's:/ct_data/stanley/...')
    Assumptions:
      - First row may be a header (expects 'folder' and 'email' if present; case-insensitive)
      - Otherwise: col0 = folder, last col = email
      - Delimiter auto-detected (tab or comma, etc.)
    """
    if not os.path.exists(path):
        if DEBUG:
            print(f"[users.csv] Not found at {path}. No X-ray User mapping will be applied.")
        return UsersIndex({}, [])

    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        sample = f.read(4096)
        f.seek(0)
        delim = detect_delimiter(sample)
        reader = csv.reader(f, delimiter=delim)
        rows = [r for r in reader if any((cell or "").strip() for cell in r)]

    if not rows:
        if DEBUG:
            print("[users.csv] Found but empty.")
        return UsersIndex({}, [])

    header = [c.strip().lower() for c in rows[0]]
    has_header = ("folder" in header and "email" in header)

    folder_idx = 0
    email_idx = -1
    start = 1 if has_header else 0
    if has_header:
        folder_idx = header.index("folder")
        email_idx = header.index("email")

    component_map: Dict[str, str] = {}
    path_list: List[Tuple[str, str]] = []

    for r in rows[start:]:
        if not r:
            continue
        folder_raw = r[folder_idx].strip() if folder_idx < len(r) else ""
        email = r[email_idx].strip() if (email_idx != -1 and email_idx < len(r)) else (r[-1].strip() if r else "")

        if not folder_raw or not email:
            continue

        # Add component keys for each component in the folder_raw (handles short tokens and long paths)
        for c in split_path_components(folder_raw):
            comp = normalize_component(c)
            if comp:
                component_map[comp] = email

        # Add full-path normalized entry for substring matches
        path_norm = normalize_path(folder_raw)
        if path_norm:
            path_list.append((path_norm, email))

    if DEBUG:
        print(f"[users.csv] Loaded: rows={len(rows) - start}, delimiter='{delim}', header={has_header}")
        # show a few examples of component keys and path keys
        comp_preview = sorted(list(component_map.keys()))[:15]
        path_preview = [p for p, _ in path_list[:5]]
        print(f"[users.csv] component_map keys (sample): {comp_preview}")
        print(f"[users.csv] path_list (sample): {path_preview}")

    return UsersIndex(component_map, path_list)

# -------------------- metadata path gathering & matching --------------------

CANDIDATE_TOP_LEVEL_FIELDS = (
    "file_path",
    "txrm_file_path",
    "file_hyperlink",
    "source_path",
)
CANDIDATE_CALIB_FIELDS = (
    "MGainImg",
    "OffsetImg",
    "GainImg",
    "DefPixelImg",
    "calib_folder_path",
)

def gather_candidate_paths(meta: dict) -> List[str]:
    candidates: List[str] = []

    def maybe_add(val):
        if isinstance(val, str):
            v = val.strip()
            if v and v.lower() != "n/a":
                candidates.append(v)

    # top-level
    for k in CANDIDATE_TOP_LEVEL_FIELDS:
        if k in meta:
            maybe_add(meta[k])

    # nested calib_images
    calib = meta.get("calib_images", {})
    if isinstance(calib, dict):
        for k in CANDIDATE_CALIB_FIELDS:
            if k in calib:
                maybe_add(calib[k])

    return candidates

def find_user_email_for_record(meta: dict, users: UsersIndex) -> str:
    """
    Match order (highest specificity wins):
      1) Component equals user 'Folder' component  -> weight = len(component)
      2) Full-path contains user 'Folder' normalized path -> weight = len(folder_path_norm)
    """
    if not users.component_map and not users.path_list:
        return ""

    candidates = gather_candidate_paths(meta)
    if not candidates:
        return ""

    best_email = ""
    best_weight = -1

    for raw in candidates:
        full_norm = normalize_path(raw)
        comps = [normalize_component(c) for c in split_path_components(raw)]

        # 1) component matches
        for c in comps:
            email = users.component_map.get(c)
            if email:
                w = len(c)
                if w > best_weight:
                    best_weight = w
                    best_email = email

        # 2) full-path substring matches
        for key_norm_path, email in users.path_list:
            if key_norm_path and key_norm_path in full_norm:
                w = len(key_norm_path)
                if w > best_weight:
                    best_weight = w
                    best_email = email

    if DEBUG:
        print("---- MATCH DEBUG ----")
        print("Record candidates:", candidates)
        if best_email:
            print("Chosen email:", best_email, "weight:", best_weight)
        else:
            print("No match found.")
            print("Normalized candidates:", [normalize_path(c) for c in candidates])
            print("Components examined:", [normalize_component(c) for c in split_path_components(' | '.join(candidates))])
        print("---------------------")

    return best_email

# -------------------- main conversion --------------------

def main():
    data = read_json(METADATA_JSON)
    if not isinstance(data, list):
        raise ValueError("metadata.json must contain a list of objects")

    users = read_users_index(USERS_CSV)

    # Flatten and collect rows
    rows = []
    fieldnames = set()
    for rec in data:
        flat = flatten_dict(rec)
        email = find_user_email_for_record(rec, users)
        flat["X-ray User"] = email
        rows.append(flat)
        fieldnames.update(flat.keys())

    # Preferred order for readability if present
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
    remaining = sorted(fn for fn in fieldnames if fn not in preferred and fn != "X-ray User")
    ordered = [fn for fn in preferred if fn in fieldnames] + remaining + ["X-ray User"]

    Path(OUTPUT_CSV).parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=ordered, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in ordered})

if __name__ == "__main__":
    main()
