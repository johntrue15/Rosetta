#!/usr/bin/env python3
"""
metadata_to_csv.py

- Reads data/metadata.json (list of dicts; may include nested dicts like calib_images)
- Reads data/users.csv (Folder,User name,Email) — delimiter can be tab or comma (auto-detected)
- Reads standard_format.json (optional) — controls column order, display names, and inclusion
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
from typing import Any, Dict, List, Optional, Tuple

METADATA_JSON  = "data/metadata.json"
USERS_CSV      = "users.csv"
OUTPUT_CSV     = "data/metadata.csv"
FORMAT_JSON    = "standard_format.json"

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

# -------------------- standard_format.json handling --------------------

class ColumnFormat:
    """Parsed representation of standard_format.json."""
    def __init__(self, columns: List[Dict[str, Any]], include_unmapped: bool):
        self.columns = columns
        self.include_unmapped = include_unmapped
        self._source_to_name = {
            c["source"]: c["name"]
            for c in columns
            if c.get("include", True)
        }
        self._included_sources = [
            c["source"]
            for c in columns
            if c.get("include", True)
        ]

    def build_fieldnames(self, all_keys: set) -> List[str]:
        """Return ordered CSV header names, applying renames and ordering."""
        ordered = []
        seen_sources = set()
        for src in self._included_sources:
            if src in all_keys:
                ordered.append(self._source_to_name.get(src, src))
                seen_sources.add(src)

        if self.include_unmapped:
            unmapped = sorted(k for k in all_keys if k not in seen_sources)
            ordered.extend(unmapped)

        return ordered

    def build_source_order(self, all_keys: set) -> List[str]:
        """Return ordered source field names (pre-rename)."""
        ordered = []
        seen = set()
        for src in self._included_sources:
            if src in all_keys:
                ordered.append(src)
                seen.add(src)

        if self.include_unmapped:
            unmapped = sorted(k for k in all_keys if k not in seen)
            ordered.extend(unmapped)

        return ordered

    def rename(self, source_key: str) -> str:
        """Map internal field name to display name."""
        return self._source_to_name.get(source_key, source_key)


def load_column_format(path: str = FORMAT_JSON) -> Optional[ColumnFormat]:
    """Load standard_format.json if it exists. Returns None if missing."""
    if not os.path.exists(path):
        if DEBUG:
            print(f"[format] {path} not found — using default column order.")
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        columns = data.get("columns", [])
        include_unmapped = data.get("include_unmapped", True)
        if DEBUG:
            print(f"[format] Loaded {len(columns)} column definitions from {path}")
        return ColumnFormat(columns, include_unmapped)
    except Exception as e:
        print(f"[format] WARNING: Failed to parse {path}: {e} — using defaults.")
        return None

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

        for c in split_path_components(folder_raw):
            comp = normalize_component(c)
            if comp:
                component_map[comp] = email

        path_norm = normalize_path(folder_raw)
        if path_norm:
            path_list.append((path_norm, email))

    if DEBUG:
        print(f"[users.csv] Loaded: rows={len(rows) - start}, delimiter='{delim}', header={has_header}")
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

    for k in CANDIDATE_TOP_LEVEL_FIELDS:
        if k in meta:
            maybe_add(meta[k])

    calib = meta.get("calib_images", {})
    if isinstance(calib, dict):
        for k in CANDIDATE_CALIB_FIELDS:
            if k in calib:
                maybe_add(calib[k])

    return candidates

def find_user_email_for_record(meta: dict, users: UsersIndex) -> str:
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

        for c in comps:
            email = users.component_map.get(c)
            if email:
                w = len(c)
                if w > best_weight:
                    best_weight = w
                    best_email = email

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

def convert(metadata_path: str = METADATA_JSON,
            users_path: str = USERS_CSV,
            format_path: str = FORMAT_JSON,
            output_path: str = OUTPUT_CSV) -> None:
    data = read_json(metadata_path)
    if not isinstance(data, list):
        raise ValueError("metadata.json must contain a list of objects")

    users = read_users_index(users_path)
    fmt = load_column_format(format_path)

    rows = []
    fieldnames: set = set()
    for rec in data:
        flat = flatten_dict(rec)
        email = find_user_email_for_record(rec, users)
        flat["X-ray User"] = email
        rows.append(flat)
        fieldnames.update(flat.keys())

    if fmt:
        source_order = fmt.build_source_order(fieldnames)
        csv_headers = fmt.build_fieldnames(fieldnames)
        source_to_header = {src: fmt.rename(src) for src in source_order}
    else:
        preferred = [
            "file_name", "file_hyperlink", "file_path", "txrm_file_path",
            "start_time", "end_time", "ct_voxel_size_um", "ct_objective",
            "ct_number_images", "xray_tube_voltage", "xray_tube_current",
            "xray_tube_power", "xray_filter", "image_width_pixels",
            "image_height_pixels", "scan_time", "sha256", "source_path",
        ]
        remaining = sorted(fn for fn in fieldnames if fn not in preferred and fn != "X-ray User")
        source_order = [fn for fn in preferred if fn in fieldnames] + remaining + ["X-ray User"]
        csv_headers = list(source_order)
        source_to_header = {s: s for s in source_order}

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(csv_headers)
        for r in rows:
            writer.writerow([r.get(src, "") for src in source_order])


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Convert metadata JSON to CSV with user attribution.",
    )
    parser.add_argument(
        "--input",
        default=METADATA_JSON,
        help=f"Input metadata JSON path (default: {METADATA_JSON})",
    )
    parser.add_argument(
        "--output",
        default=OUTPUT_CSV,
        help=f"Output CSV path (default: {OUTPUT_CSV})",
    )
    args = parser.parse_args()
    convert(metadata_path=args.input, output_path=args.output)


if __name__ == "__main__":
    main()
