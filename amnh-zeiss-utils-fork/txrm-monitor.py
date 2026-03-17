#!/usr/bin/env python

"""
txrm-monitor.py

A PySide6 GUI application that monitors directories for .txrm files and
automatically extracts metadata when files are stable.

By Hollister Herhold, AMNH, 2026.

This application was developed using Claude Sonnet 4.5 using the REQUIREMENTS.md file
as a guide for features and functionality. 

"""

import sys
import os
import json
import logging
import time
from pathlib import Path
from datetime import datetime
from threading import Thread, Lock
from typing import Dict, List, Optional

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTableWidget, QTableWidgetItem, QTextEdit, QFileDialog,
    QLabel, QListWidget, QMessageBox, QHeaderView, QStatusBar
)
from PySide6.QtCore import Qt, QTimer, Signal, QObject
from PySide6.QtGui import QTextCursor

import xrmreader


# Constants
SCAN_INTERVAL = 5 * 60 * 1000  # 5 minutes in milliseconds
STABILITY_CHECK_INTERVAL = 10 * 1000  # 10 seconds in milliseconds (for checking stability)
STABILITY_DURATION = 10 * 60  # 10 minutes in seconds
CONFIG_FILE = "txrm-monitor-config.json"
LOG_DIR = "logs"


class FileMonitorState:
    """Represents the state of a monitored .txrm file"""
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.size = os.path.getsize(filepath)
        self.last_size_change = time.time()
        self.status = "Waiting for changes"
        self.is_processing = False
        self.is_completed = False
        self.error = None
    
    def update_size(self):
        """Check if file size has changed and update state"""
        try:
            current_size = os.path.getsize(self.filepath)
            if current_size != self.size:
                self.size = current_size
                self.last_size_change = time.time()
                return True
        except OSError:
            return False
        return False
    
    def is_stable(self) -> bool:
        """Check if file has been stable for the required duration"""
        return (time.time() - self.last_size_change) >= STABILITY_DURATION
    
    def time_until_stable(self) -> int:
        """Returns seconds until file is considered stable"""
        elapsed = time.time() - self.last_size_change
        remaining = STABILITY_DURATION - elapsed
        return max(0, int(remaining))


class LogSignaler(QObject):
    """Signal emitter for logging to GUI"""
    log_message = Signal(str)


class RotatingFileHandler(logging.Handler):
    """Custom logging handler with daily rotation"""
    def __init__(self, log_dir: str):
        super().__init__()
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self.current_date = None
        self.file_handler = None
        self._rotate_if_needed()
    
    def _rotate_if_needed(self):
        """Rotate log file if date has changed"""
        today = datetime.now().date()
        if today != self.current_date:
            if self.file_handler:
                self.file_handler.close()
            self.current_date = today
            log_file = self.log_dir / f"txrm-monitor-{today}.log"
            self.file_handler = open(log_file, 'a', encoding='utf-8')
    
    def emit(self, record):
        """Write log record to file"""
        self._rotate_if_needed()
        msg = self.format(record)
        self.file_handler.write(msg + '\n')
        self.file_handler.flush()


class FileMonitor(QObject):
    """Background file monitoring system"""
    
    status_updated = Signal()
    status_message = Signal(str)
    
    def __init__(self, logger: logging.Logger):
        super().__init__()
        self.logger = logger
        self.monitored_files: Dict[str, FileMonitorState] = {}
        self.directories: List[str] = []
        self.lock = Lock()
        self.running = False
    
    def set_directories(self, directories: List[str]):
        """Update list of directories to monitor"""
        with self.lock:
            self.directories = directories
            self.logger.info(f"Updated monitored directories: {directories}")
    
    def scan_directories(self):
        """Scan all directories for .txrm files"""
        if not self.directories:
            self.status_message.emit("No directories configured")
            return
        
        self.logger.info("Scanning directories for .txrm files...")
        self.status_message.emit(f"Scanning {len(self.directories)} directories...")
        found_files = set()
        
        for directory in self.directories:
            if not os.path.isdir(directory):
                self.logger.warning(f"Directory not found: {directory}")
                continue
            
            self.status_message.emit(f"Scanning: {directory}")
            
            try:
                # Recursively scan directory and subdirectories
                for root, dirs, files in os.walk(directory):
                    self.status_message.emit(f"Scanning: {root}")
                    
                    for filename in files:
                        if filename.endswith('.txrm'):
                            txrm_path = os.path.join(root, filename)
                            txt_path = txrm_path + '.txt'
                            
                            # Skip if already has metadata file
                            if os.path.exists(txt_path):
                                continue
                            
                            found_files.add(txrm_path)
                            
                            # Add to monitoring if new
                            with self.lock:
                                if txrm_path not in self.monitored_files:
                                    self.monitored_files[txrm_path] = FileMonitorState(txrm_path)
                                    self.logger.info(f"New file detected: {txrm_path}")
            except Exception as e:
                self.logger.error(f"Error scanning directory {directory}: {e}")
        
        # Remove files that no longer exist or have been processed
        with self.lock:
            to_remove = []
            for filepath in self.monitored_files.keys():
                if filepath not in found_files:
                    to_remove.append(filepath)
            
            for filepath in to_remove:
                del self.monitored_files[filepath]
                self.logger.info(f"Removed from monitoring: {filepath}")
        
        self.logger.info(f"Scan complete. Monitoring {len(self.monitored_files)} files")
        self.status_message.emit(f"Scan complete. Monitoring {len(self.monitored_files)} files")
        self.status_updated.emit()
    
    def check_stability_and_process(self):
        """Check file stability and process stable files"""
        with self.lock:
            files_to_check = list(self.monitored_files.items())
        
        if files_to_check:
            self.status_message.emit(f"Checking stability of {len(files_to_check)} files...")
        
        any_changed = False
        for filepath, state in files_to_check:
            if state.is_processing or state.is_completed:
                continue
            
            # Update file size
            size_changed = state.update_size()
            if size_changed:
                self.logger.info(f"File size changed: {filepath}")
                state.status = f"Waiting for changes ({state.time_until_stable()}s)"
                any_changed = True
                continue
            
            # Check if stable
            if state.is_stable():
                self.logger.info(f"File is stable, processing: {filepath}")
                self.status_message.emit(f"Processing: {os.path.basename(filepath)}")
                state.is_processing = True
                state.status = "Processing"
                any_changed = True
                
                # Process in background thread
                Thread(target=self._process_file, args=(filepath, state), daemon=True).start()
            else:
                remaining = state.time_until_stable()
                state.status = f"Waiting for changes ({remaining}s)"
                any_changed = True
        
        if any_changed:
            self.status_updated.emit()
    
    def _process_file(self, filepath: str, state: FileMonitorState):
        """Extract metadata from file"""
        txt_path = filepath + '.txt'
        
        try:
            self.logger.info(f"Extracting metadata from: {filepath}")
            
            # Use xrmreader to extract metadata
            metadata = xrmreader.read_metadata(filepath)
            
            if not metadata:
                raise Exception("Failed to read metadata")
            
            # Format metadata output (similar to get-metadata-from-txrm.py)
            default_fields = [
                'image_width', 'image_height', 'data_type', 'number_of_images',
                'pixel_size', 'reference_exposure_time', 'reference_current',
                'reference_voltage', 'reference_data_type', 'image_data_type',
                'align-mode', 'center_shift', 'rotation_angle',
                'source_isocenter_distance', 'detector_isocenter_distance', 'cone_angle',
                'fan_angle', 'camera_offset', 'source_drift', 'current', 'voltage',
                'power', 'exposure_time', 'binning', 'filter', 
                'scaling_min', 'scaling_max', 'objective_id', 'objective_mag'
            ]
            
            output_lines = []
            output_lines.append(f"Metadata extracted from: {filepath}")
            output_lines.append(f"Extraction date: {datetime.now()}")
            output_lines.append("")
            
            for field in default_fields:
                value = metadata.get(field, None)
                if value is not None:
                    output_lines.append(f"{field}: {value}")
                else:
                    output_lines.append(f"{field}: Not found in metadata")
            
            # Write metadata to file
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(output_lines))
            
            state.status = "Completed"
            state.is_completed = True
            state.is_processing = False
            self.logger.info(f"Successfully processed: {filepath}")
            
        except Exception as e:
            # Write error file
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write("ERROR PROCESSING METADATA\n")
                f.write(f"Error: {str(e)}\n")
                f.write(f"File: {filepath}\n")
                f.write(f"Date: {datetime.now()}\n")
            
            state.status = "Error"
            state.error = str(e)
            state.is_completed = True  # Mark as completed so it's no longer monitored
            state.is_processing = False
            self.logger.error(f"Error processing {filepath}: {e}")
        
        self.status_updated.emit()
    
    def get_monitored_files(self) -> List[tuple]:
        """Get list of monitored files and their states"""
        with self.lock:
            return [(fp, state.status, state.error) for fp, state in self.monitored_files.items()]
    
    def process_file_now(self, filepath: str):
        """Force immediate processing of a specific file"""
        with self.lock:
            if filepath not in self.monitored_files:
                return False
            state = self.monitored_files[filepath]
            
            if state.is_processing:
                return False  # Already processing
            
            if state.is_completed:
                return False  # Already completed
        
        self.logger.info(f"Force processing file: {filepath}")
        state.is_processing = True
        state.status = "Processing (forced)"
        self.status_updated.emit()
        
        # Process in background thread
        Thread(target=self._process_file, args=(filepath, state), daemon=True).start()
        return True


class TXRMMonitorApp(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TXRM File Monitor")
        self.setGeometry(100, 100, 1000, 700)
        
        # Setup logging
        self.setup_logging()
        
        # Initialize file monitor
        self.file_monitor = FileMonitor(self.logger)
        self.file_monitor.status_updated.connect(self.update_file_table)
        self.file_monitor.status_message.connect(self.update_status_bar)
        
        # Load configuration
        self.load_config()
        
        # Setup UI
        self.setup_ui()
        
        # Setup timers
        self.next_scan_time = time.time() + (SCAN_INTERVAL / 1000)
        
        self.scan_timer = QTimer()
        self.scan_timer.timeout.connect(self.on_scan_timeout)
        self.scan_timer.start(SCAN_INTERVAL)
        
        self.stability_timer = QTimer()
        self.stability_timer.timeout.connect(self.file_monitor.check_stability_and_process)
        self.stability_timer.start(STABILITY_CHECK_INTERVAL)
        
        # Countdown update timer (updates every second)
        self.countdown_timer = QTimer()
        self.countdown_timer.timeout.connect(self.update_countdown)
        self.countdown_timer.start(1000)  # Update every second
        
        # Initial scan
        self.file_monitor.scan_directories()
        
        self.logger.info("TXRM Monitor application started")
    
    def setup_logging(self):
        """Setup logging system with daily rotation and GUI display"""
        self.logger = logging.getLogger('TXRMMonitor')
        self.logger.setLevel(logging.INFO)
        
        # Create logs directory
        Path(LOG_DIR).mkdir(exist_ok=True)
        
        # Setup rotating file handler
        file_handler = RotatingFileHandler(LOG_DIR)
        file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)
        
        # Setup GUI handler
        self.log_signaler = LogSignaler()
        
        class GUIHandler(logging.Handler):
            def __init__(self, signaler):
                super().__init__()
                self.signaler = signaler
            
            def emit(self, record):
                msg = self.format(record)
                self.signaler.log_message.emit(msg)
        
        gui_handler = GUIHandler(self.log_signaler)
        gui_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        gui_handler.setFormatter(gui_formatter)
        self.logger.addHandler(gui_handler)
    
    def setup_ui(self):
        """Create the user interface"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Directory configuration section
        dir_layout = QHBoxLayout()
        dir_label = QLabel("Monitored Directories:")
        dir_layout.addWidget(dir_label)
        
        self.dir_list = QListWidget()
        self.dir_list.setMaximumHeight(100)
        for directory in self.file_monitor.directories:
            self.dir_list.addItem(directory)
        dir_layout.addWidget(self.dir_list)
        
        dir_button_layout = QVBoxLayout()
        add_dir_btn = QPushButton("Add Directory")
        add_dir_btn.clicked.connect(self.add_directory)
        dir_button_layout.addWidget(add_dir_btn)
        
        remove_dir_btn = QPushButton("Remove Selected")
        remove_dir_btn.clicked.connect(self.remove_directory)
        dir_button_layout.addWidget(remove_dir_btn)
        
        dir_layout.addLayout(dir_button_layout)
        layout.addLayout(dir_layout)
        
        # Countdown timer display and scan now button
        scan_control_layout = QHBoxLayout()
        self.countdown_label = QLabel("Next scan in: --:--")
        self.countdown_label.setStyleSheet("font-weight: bold; padding: 5px;")
        scan_control_layout.addWidget(self.countdown_label)
        
        scan_now_btn = QPushButton("Scan Now")
        scan_now_btn.clicked.connect(self.scan_now)
        scan_control_layout.addWidget(scan_now_btn)
        scan_control_layout.addStretch()
        
        layout.addLayout(scan_control_layout)
        
        # File status table
        file_section_layout = QHBoxLayout()
        status_label = QLabel("Monitored Files:")
        file_section_layout.addWidget(status_label)
        file_section_layout.addStretch()
        
        process_selected_btn = QPushButton("Process Selected Now")
        process_selected_btn.clicked.connect(self.process_selected_now)
        file_section_layout.addWidget(process_selected_btn)
        
        layout.addLayout(file_section_layout)
        
        self.file_table = QTableWidget()
        self.file_table.setColumnCount(3)
        self.file_table.setHorizontalHeaderLabels(["File Path", "Status", "Error"])
        self.file_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.file_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.file_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.file_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.file_table.setSelectionMode(QTableWidget.SingleSelection)
        layout.addWidget(self.file_table)
        
        # Log viewer
        log_label = QLabel("Activity Log:")
        layout.addWidget(log_label)
        
        self.log_viewer = QTextEdit()
        self.log_viewer.setReadOnly(True)
        self.log_viewer.setMaximumHeight(200)
        layout.addWidget(self.log_viewer)
        
        # Connect log signaler
        self.log_signaler.log_message.connect(self.append_log)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
    
    def add_directory(self):
        """Add a directory to monitor"""
        directory = QFileDialog.getExistingDirectory(self, "Select Directory to Monitor")
        if directory:
            # Add to list widget
            self.dir_list.addItem(directory)
            
            # Update file monitor
            directories = [self.dir_list.item(i).text() for i in range(self.dir_list.count())]
            self.file_monitor.set_directories(directories)
            
            # Save config
            self.save_config()
            
            # Trigger immediate scan
            self.file_monitor.scan_directories()
            self.next_scan_time = time.time() + (SCAN_INTERVAL / 1000)
    
    def remove_directory(self):
        """Remove selected directory from monitoring"""
        current_item = self.dir_list.currentItem()
        if current_item:
            self.dir_list.takeItem(self.dir_list.row(current_item))
            
            # Update file monitor
            directories = [self.dir_list.item(i).text() for i in range(self.dir_list.count())]
            self.file_monitor.set_directories(directories)
            
            # Save config
            self.save_config()
    
    def update_file_table(self):
        """Update the file status table"""
        files = self.file_monitor.get_monitored_files()
        self.file_table.setRowCount(len(files))
        
        for row, (filepath, status, error) in enumerate(files):
            self.file_table.setItem(row, 0, QTableWidgetItem(filepath))
            self.file_table.setItem(row, 1, QTableWidgetItem(status))
            error_text = error if error else ""
            self.file_table.setItem(row, 2, QTableWidgetItem(error_text))
    
    def append_log(self, message: str):
        """Append message to log viewer"""
        self.log_viewer.append(message)
        # Auto-scroll to bottom
        cursor = self.log_viewer.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.log_viewer.setTextCursor(cursor)
    
    def update_status_bar(self, message: str):
        """Update status bar with current activity"""
        self.status_bar.showMessage(message)
    
    def on_scan_timeout(self):
        """Handle scan timer timeout"""
        self.file_monitor.scan_directories()
        self.next_scan_time = time.time() + (SCAN_INTERVAL / 1000)
    
    def update_countdown(self):
        """Update the countdown display"""
        remaining = self.next_scan_time - time.time()
        if remaining < 0:
            remaining = 0
        
        minutes = int(remaining // 60)
        seconds = int(remaining % 60)
        self.countdown_label.setText(f"Next scan in: {minutes:02d}:{seconds:02d}")
    
    def scan_now(self):
        """Trigger an immediate scan"""
        self.logger.info("Manual scan triggered")
        self.file_monitor.scan_directories()
        self.next_scan_time = time.time() + (SCAN_INTERVAL / 1000)
        self.update_countdown()
    
    def process_selected_now(self):
        """Process the currently selected file immediately"""
        selected_rows = self.file_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "No Selection", "Please select a file to process.")
            return
        
        row = selected_rows[0].row()
        filepath_item = self.file_table.item(row, 0)
        if not filepath_item:
            return
        
        filepath = filepath_item.text()
        success = self.file_monitor.process_file_now(filepath)
        
        if not success:
            QMessageBox.warning(self, "Cannot Process", 
                              "This file cannot be processed now (already processing or completed).")
        else:
            self.logger.info(f"User requested immediate processing of: {filepath}")
    
    def load_config(self):
        """Load configuration from JSON file"""
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                    directories = config.get('directories', [])
                    self.file_monitor.set_directories(directories)
                    self.logger.info(f"Configuration loaded from {CONFIG_FILE}")
        except Exception as e:
            self.logger.error(f"Error loading configuration: {e}")
    
    def save_config(self):
        """Save configuration to JSON file"""
        try:
            directories = [self.dir_list.item(i).text() for i in range(self.dir_list.count())]
            config = {'directories': directories}
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=2)
            self.logger.info(f"Configuration saved to {CONFIG_FILE}")
        except Exception as e:
            self.logger.error(f"Error saving configuration: {e}")
    
    def closeEvent(self, event):
        """Handle window close event"""
        self.logger.info("TXRM Monitor application closing")
        self.save_config()
        event.accept()


def main():
    app = QApplication(sys.argv)
    window = TXRMMonitorApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
