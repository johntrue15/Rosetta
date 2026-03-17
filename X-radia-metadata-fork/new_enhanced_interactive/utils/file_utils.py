# -*- coding: utf-8 -*-
from __future__ import print_function
import os

def is_drift_file(file_path):
    """Check if file is a drift file based on name"""
    filename = os.path.basename(file_path).lower()
    return 'drift' in filename

def find_txrm_files(search_path, include_drift=False):
    txrm_files = []
    folder_structure = {}
    total_files = 0
    drift_files = 0
    
    print("\nSearching for .txrm files in: {0}".format(search_path))
    
    try:
        for root, _, filenames in os.walk(search_path):
            txrm_in_folder = [f for f in filenames if f.lower().endswith('.txrm')]
            if txrm_in_folder:
                if not include_drift:
                    txrm_in_folder = [f for f in txrm_in_folder if not is_drift_file(f)]
                
                rel_path = os.path.relpath(root, search_path)
                folder_structure[rel_path] = len(txrm_in_folder)
                total_files += len(txrm_in_folder)
                
                for txrm_file in txrm_in_folder:
                    full_path = os.path.join(root, txrm_file)
                    txrm_files.append(full_path)
                    if is_drift_file(txrm_file):
                        drift_files += 1
                    print("Found: {0}".format(full_path))

        print("\nFolder Structure Summary:")
        for folder, count in folder_structure.items():
            print("  {0}: {1} TXRM files".format(folder, count))
        print("\nTotal TXRM files found: {0}".format(total_files))
        if drift_files > 0:
            print("Drift files {0}: {1}".format(
                "included" if include_drift else "excluded",
                drift_files
            ))
    
    except Exception as e:
        print("Directory search error: {0}".format(str(e)))
    
    return txrm_files

def get_user_input(prompt, valid_responses=None):
    """Get user input with validation"""
    while True:
        try:
            response = raw_input(prompt).strip().lower()
            if valid_responses is None or response in valid_responses:
                return response
            print("Invalid input. Please try again.")
        except EOFError:
            return valid_responses[0] if valid_responses else '' 