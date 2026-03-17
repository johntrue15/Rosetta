# -*- coding: utf-8 -*-
from __future__ import print_function
import os
from new_enhanced_interactive.utils.file_utils import get_user_input

class UserConfig(object):  # Explicitly inherit from object
    def __init__(self):
        self.search_path = None
        self.output_dir = None
        self.include_drift = False
        self.process_mode = None
        
    def _get_valid_path(self):
        """Get and validate path from user"""
        path = raw_input("\nEnter folder path containing .txrm files: ").strip('"')
        while not os.path.exists(path):
            print("Path does not exist!")
            path = raw_input("Enter a valid folder path: ").strip('"')
        return path
        
    def setup_from_user_input(self):
        # Get search path
        self.search_path = self._get_valid_path()
        
        # Get output location
        save_location = get_user_input(
            "\nWhere would you like to save the metadata output folder?\n"
            "1. Current working directory\n"
            "2. Same directory as TXRM files\n"
            "Enter (1/2): ",
            ['1', '2']
        )
        self.output_dir = os.getcwd() if save_location == '1' else self.search_path
        
        # Get drift file preference
        self.include_drift = get_user_input(
            "\nInclude drift files in processing? (y/n): ",
            ['y', 'n']
        ) == 'y'
        
        # Get process mode
        self.process_mode = get_user_input(
            "\nChoose processing mode:\n1. Process all files (batch)\n"
            "2. Confirm each file\nEnter (1/2): ",
            ['1', '2']
        ) 