# -*- coding: utf-8 -*-
from __future__ import print_function, division  # Add division for Python 2.7
import os
import ctypes
import sys

# Import all required modules at the top level
from new_enhanced_interactive.config.watch_config import WatchConfig
from new_enhanced_interactive.utils.file_utils import get_user_input, find_txrm_files
from new_enhanced_interactive.utils.file_watcher import TXRMFileWatcher
from new_enhanced_interactive.processors.txrm_processor import TXRMProcessor

# Fix module import path if running script directly
if __name__ == "__main__":
    # Get the absolute path of the parent directory (one above new_enhanced_interactive)
    module_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if module_path not in sys.path:
        sys.path.insert(0, module_path)

def check_admin():
    """Cross-platform admin check"""
    try:
        if os.name == 'nt':  # Windows
            return ctypes.windll.shell32.IsUserAnAdmin()
        return os.geteuid() == 0  # Remove unnecessary else
    except Exception as e:
        print("\nCouldn't verify admin privileges: {0}".format(str(e)))
        return False

def _handle_interactive_mode(_):  # Change file_path to _ since it's unused
    process_file = get_user_input(
        "Process this file? (y/n/q to quit): ",
        ['y', 'n', 'q']
    )
    
    if process_file == 'q':
        print("\nProcessing stopped by user.")
        return False
    return process_file == 'y'  # Simplified return logic

def setup_watch_config():
    """Setup or update watch configuration"""
    config = WatchConfig()
    
    print("\nWatch Mode Configuration")
    print("=" * 30)
    
    # Enable/disable watch mode
    enable = get_user_input(
        "Enable watch mode? (y/n): ",
        ['y', 'n']
    ) == 'y'
    
    if enable:
        # Get watch directory
        watch_dir = raw_input("\nEnter directory to watch for TXRM files: ").strip('"')
        while not os.path.exists(watch_dir):
            print("Directory does not exist!")
            watch_dir = raw_input("Enter a valid directory: ").strip('"')
        
        # Get polling interval
        interval = raw_input("\nEnter polling interval in seconds (default 60): ").strip()
        interval = int(interval) if interval.isdigit() else 60
        
        # Include drift files
        include_drift = get_user_input(
            "\nInclude drift files? (y/n): ",
            ['y', 'n']
        ) == 'y'
        
        # Update config
        config.update_config(
            watch_mode_enabled=True,
            watch_directory=watch_dir,
            polling_interval=interval,
            include_drift_files=include_drift,
            cumulative_csv_path=os.path.join(watch_dir, "metadata_output")
        )
        print("\nWatch mode configuration saved!")
    else:
        config.update_config(watch_mode_enabled=False)
    
    return config

def main():
    if not check_admin():
        user_input = get_user_input("Continue anyway? (y/n): ", ['y', 'n'])
        if user_input != 'y':
            print("Exiting...")
            return

    # Load or setup watch configuration
    config = WatchConfig()
    
    # Ask for mode
    mode = get_user_input(
        "\nSelect mode:\n1. Manual processing\n2. Watch mode\n3. Configure watch mode\nEnter (1/2/3): ",
        ['1', '2', '3']
    )
    
    if mode == '3':
        config = setup_watch_config()
        return
    
    if mode == '2':
        if not config.config['watch_mode_enabled']:
            print("\nWatch mode is not configured! Please configure first.")
            return
        
        # Initialize processor with watch directory output
        processor = TXRMProcessor(output_dir=config.config['cumulative_csv_path'])
        
        # Start file watcher
        watcher = TXRMFileWatcher(processor, config)
        watcher.watch()
        return
    
    # Manual mode
    search_path = raw_input("\nEnter folder path containing TXRM files: ").strip('"')
    while not os.path.exists(search_path):
        print("Path does not exist!")
        search_path = raw_input("Enter a valid folder path: ").strip('"')
    
    # Initialize processor
    processor = TXRMProcessor(output_dir=os.path.join(search_path, "metadata_output"))
    
    # Process files
    include_drift = get_user_input("\nInclude drift files? (y/n): ", ['y', 'n']) == 'y'
    
    # Fix: Call find_txrm_files directly instead of as a method of processor
    txrm_files = find_txrm_files(search_path, include_drift)
    
    if not txrm_files:
        print("\nNo TXRM files found in the specified path.")
        return
    
    process_mode = get_user_input(
        "\nChoose processing mode:\n1. Process all files (batch)\n2. Confirm each file\nEnter (1/2): ",
        ['1', '2']
    )
    
    processed_count = 0
    for i, file_path in enumerate(txrm_files, 1):
        print("\nFile {0} of {1}:".format(i, len(txrm_files)))
        print(file_path)
        
        # Skip drift files if not included
        if not include_drift and 'drift' in os.path.basename(file_path).lower():
            print("Skipping drift file (not included in processing)")
            continue
            
        if process_mode == '2':
            if not _handle_interactive_mode(file_path):
                break
        
        if processor.process_single_file(file_path):
            processed_count += 1
    
    # Generate cumulative CSV file after processing all files
    if processor.all_metadata:
        print("\nProcessed {0} files successfully.".format(processed_count))
        csv_path = processor.save_cumulative_csv()
        if csv_path:
            print("\nCumulative CSV file saved to: {0}".format(csv_path))
        else:
            print("\nError: Failed to generate cumulative CSV file.")
    else:
        print("\nNo metadata was collected. CSV file not generated.")
    
    print("\nProcessing complete!")

if __name__ == "__main__":
    main() 