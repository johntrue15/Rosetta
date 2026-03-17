# -*- coding: utf-8 -*-
from __future__ import division

class ProgressTracker(object):  # Make it a new-style class
    def __init__(self, total_files):
        self.total_files = float(total_files)
        self.processed_files = 0
        self.failed_files = []
        
    def update(self, file_path, success):
        self.processed_files += 1
        if not success:
            self.failed_files.append(file_path)
            
    def get_progress(self):
        return {
            'total': int(self.total_files),
            'processed': self.processed_files,
            'failed': len(self.failed_files),
            'percentage': (self.processed_files / self.total_files) * 100.0
        }