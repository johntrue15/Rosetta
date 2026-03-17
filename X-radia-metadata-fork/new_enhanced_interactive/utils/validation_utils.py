# -*- coding: utf-8 -*-
from __future__ import print_function
import os
import hashlib
import time

class TXRMValidator(object):
    def __init__(self):
        self.validation_results = {}
    
    def validate_file(self, file_path):
        """Validate TXRM file before processing"""
        try:
            # Check file exists
            if not os.path.exists(file_path):
                return False, "File does not exist", None
            
            # Check file size
            size = os.path.getsize(file_path)
            if size == 0:
                return False, "File is empty", None
            
            # Calculate file hash for integrity
            file_hash = self._calculate_hash(file_path)
            
            # Store validation result
            self.validation_results[file_path] = {
                'size': size,
                'hash': file_hash,
                'validated_at': time.time()
            }
            
            return True, "File validation successful", file_hash
            
        except Exception as e:
            return False, str(e), None
    
    def _calculate_hash(self, file_path):
        """Calculate SHA-256 hash of file"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    def get_validation_info(self, file_path):
        """Get stored validation information for a file"""
        return self.validation_results.get(file_path, {}) 