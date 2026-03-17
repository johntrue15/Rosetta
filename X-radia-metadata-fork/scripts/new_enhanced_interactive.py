# -*- coding: utf-8 -*-
from __future__ import print_function  # Import print function for compatibility
import os
import csv
import ctypes
import ConfigParser
import logging
import gc
from datetime import datetime
from XradiaPy import Data

def check_admin():
    try:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin()
        if not is_admin:
            print("\nWARNING: Script requires administrator privileges.")
            print("Please run PyCharm as administrator.\n")
            return False
        return True
    except Exception as e:  # Catch specific exceptions
        print("\nCouldn't verify admin privileges: {}".format(str(e)))
        return False

class TXRMConfigConverter(object):
    def __init__(self):
        self.dataset = Data.XRMData.XrmBasicDataSet()
        self.config = None  # Initialize as None
    
    def create_config_from_txrm(self, txrm_path):
        try:
            # Reset config object for each new file
            self.config = ConfigParser.ConfigParser()
            
            self.dataset.ReadFile(txrm_path)
            self._init_config_sections()
            self._fill_geometry_section()
            self._fill_ct_and_xray_section()  # Combined CT and Xray
            self._fill_image_section()
            self._fill_detector_section()
            self._fill_axis_section()
            self._fill_general_section()
            return True
        except Exception as e:
            print("Error processing TXRM file: {0}".format(str(e)))
            return False
    
    def _init_config_sections(self):
        # Remove Xray from sections list
        sections = ['Geometry', 'CT', 'Image', 'Detector', 'Axis', 'General']
        for section in sections:
            self.config.add_section(section)
    
    def _fill_geometry_section(self):
        idx = 0
        self.config.set('Geometry', 'FDD', str(self.dataset.GetDetectorToRADistance(idx)))
        self.config.set('Geometry', 'FOD', str(self.dataset.GetSourceToRADistance(idx)))
        self.config.set('Geometry', 'VoxelSizeX', str(self.dataset.GetPixelSize()))
        self.config.set('Geometry', 'VoxelSizeY', str(self.dataset.GetPixelSize()))
    
    def _fill_ct_and_xray_section(self):
        # CT data
        num_projections = self.dataset.GetProjections()
        self.config.set('CT', 'NumberImages', str(num_projections))
        self.config.set('CT', 'Type', '0')
        self.config.set('CT', 'RotationSector', '360.00000000')
        self.config.set('CT', 'NrImgDone', str(num_projections))
        
        # Add Xray data to CT section
        voltage = self.dataset.GetVoltage()  # in kV
        power = self.dataset.GetPower()      # in W
        current = (power / voltage) * 100 if voltage != 0 else 0  # Calculate current in µA
        
        self.config.set('CT', 'Voltage', str(int(voltage)))
        self.config.set('CT', 'Power', str(int(power)))
        self.config.set('CT', 'Current', str(int(current)))
        self.config.set('CT', 'Filter', str(self.dataset.GetFilter()))

    def save_config(self, output_path):
        try:
            with open(output_path, 'w') as configfile:
                self.config.write(configfile)
            return True
        except Exception as e:
            print("Error saving config file: {0}".format(str(e)))
            return False

class EnhancedTXRMProcessor(object):
    def __init__(self, output_dir=None):
        self.dataset = Data.XRMData.XrmBasicDataSet()
        self.output_dir = output_dir or os.path.join(os.getcwd(), "metadata_output")
        self.all_metadata = []
        self.config_converter = TXRMConfigConverter()
        
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        
        log_file = os.path.join(
            self.output_dir,
            'processing_{0}.log'.format(datetime.now().strftime("%Y%m%d_%H%M%S"))
        )
        logging.basicConfig(
            filename=log_file,
            level=logging.DEBUG,  # Set to DEBUG to capture all logs
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

    @staticmethod
    def is_drift_file(file_path):
        """Check if file is a drift file based on name"""
        filename = os.path.basename(file_path).lower()
        return 'drift' in filename

    def get_basic_info(self):
        return {
            'file_name': self.dataset.GetName(),
            'initialized_correctly': self.dataset.IsInitializedCorrectly()
        }

    def get_machine_settings(self):
        return {
            'objective': self.dataset.GetObjective(),
            'pixel_size': self.dataset.GetPixelSize(),
            'power': self.dataset.GetPower(),
            'voltage': self.dataset.GetVoltage(),
            'filter': self.dataset.GetFilter(),
            'binning': self.dataset.GetBinning()
        }

    def get_image_properties(self):
        return {
            'height': self.dataset.GetHeight(),
            'width': self.dataset.GetWidth(),
            'total_projections': self.dataset.GetProjections()
        }

    def get_axis_positions(self, projection_idx):
        axis_data = {}
        axis_names = self.dataset.GetAxesNames()
        print("Available axes: {0}".format(", ".join(axis_names)))
        
        for axis in axis_names:
            pos = self.dataset.GetAxisPosition(projection_idx, axis)
            axis_data["{0}_pos".format(axis.replace(" ", "_"))] = pos
        return axis_data

    def get_projection_data(self, projection_idx):
        proj_data = {
            'projection_number': projection_idx,
            'date': self.dataset.GetDate(projection_idx),
            'detector_to_ra_distance': self.dataset.GetDetectorToRADistance(projection_idx),
            'source_to_ra_distance': self.dataset.GetSourceToRADistance(projection_idx),
            'exposure': self.dataset.GetExposure(projection_idx)
        }
        
        # Add axis positions
        proj_data.update(self.get_axis_positions(projection_idx))
        return proj_data

    def get_complete_metadata(self, file_path):
        try:
            print("Processing file: {0}".format(file_path))
            self.dataset.ReadFile(file_path)
            
            metadata = {}
            
            # Basic file info
            metadata['basic_info'] = self.get_basic_info()
            
            # Machine settings
            metadata['machine_settings'] = self.get_machine_settings()
            
            # Image properties
            metadata['image_properties'] = self.get_image_properties()
            
            # Get data for all projections
            print("Getting data for {0} projections...".format(metadata['image_properties']['total_projections']))
            
            projection_data = []
            for idx in range(metadata['image_properties']['total_projections']):
                if idx % 10 == 0:  # Progress update every 10 projections
                    print("Processing projection {0} of {1}...".format(
                        idx + 1, metadata['image_properties']['total_projections']))
                proj_data = self.get_projection_data(idx)
                projection_data.append(proj_data)
            
            metadata['projection_data'] = projection_data

            # Get axes names (for reference)
            metadata['available_axes'] = self.dataset.GetAxesNames()

            return metadata

        except Exception as e:
            error_msg = "Error processing file {0}: {1}".format(file_path, str(e))
            self.logger.error(error_msg)
            print(error_msg)
            return None

    def save_to_csv(self, data, base_filename):
        if not data:
            print("No data to save")
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save basic info
        for section in ['basic_info', 'machine_settings', 'image_properties']:
            if section in data:
                section_path = os.path.join(
                    self.output_dir, 
                    "{0}_{1}_{2}.csv".format(base_filename, section, timestamp)
                )
                try:
                    with open(section_path, 'wb') as csvfile:
                        writer = csv.DictWriter(csvfile, fieldnames=data[section].keys())
                        writer.writeheader()
                        writer.writerow(data[section])
                    print("{0} saved to {1}".format(section, section_path))
                except Exception as e:
                    print("Error saving {0}: {1}".format(section, str(e)))

        # Save projection data
        if 'projection_data' in data and data['projection_data']:
            proj_path = os.path.join(
                self.output_dir, 
                "{0}_projections_{1}.csv".format(base_filename, timestamp)
            )
            try:
                with open(proj_path, 'wb') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=data['projection_data'][0].keys())
                    writer.writeheader()
                    writer.writerows(data['projection_data'])
                print("Projection data saved to {0}".format(proj_path))
            except Exception as e:
                print("Error saving projection data: {0}".format(str(e)))

        # Save available axes list
        if 'available_axes' in data:
            axes_path = os.path.join(
                self.output_dir, 
                "{0}_axes_{1}.txt".format(base_filename, timestamp)
            )
            try:
                with open(axes_path, 'w') as f:
                    f.write("Available axes:\n")
                    f.write("\n".join(data['available_axes']))
                print("Axes list saved to {0}".format(axes_path))
            except Exception as e:
                print("Error saving axes list: {0}".format(str(e)))

    def find_txrm_files(self, search_path, include_drift=False):
        txrm_files = []
        folder_structure = {}
        total_files = 0
        drift_files = 0
        
        print("\nSearching for .txrm files in: {}".format(search_path))
        
        try:
            for root, _, files in os.walk(search_path):
                txrm_in_folder = [f for f in files if f.lower().endswith('.txrm')]
                if txrm_in_folder:
                    # Filter out drift files if not included
                    if not include_drift:
                        txrm_in_folder = [f for f in txrm_in_folder if not self.is_drift_file(f)]
                    
                    rel_path = os.path.relpath(root, search_path)
                    folder_structure[rel_path] = len(txrm_in_folder)
                    total_files += len(txrm_in_folder)
                    
                    for file in txrm_in_folder:
                        full_path = os.path.join(root, file)
                        txrm_files.append(full_path)
                        if self.is_drift_file(file):
                            drift_files += 1
                        print("Found: {}".format(full_path))

            print("\nFolder Structure Summary:")
            for folder, count in folder_structure.items():
                print("  {}: {} TXRM files".format(folder, count))
            print("\nTotal TXRM files found: {}".format(total_files))
            if drift_files > 0:
                print("Drift files {}: {}".format(
                    "included" if include_drift else "excluded",
                    drift_files
                ))
        
        except Exception as e:
            error_msg = "Directory search error: {}".format(str(e))
            print(error_msg)
            self.logger.error(error_msg)
        
        return txrm_files

    def process_single_file(self, file_path):
        try:
            print("\nProcessing: {}".format(file_path))
            
            # Get metadata
            metadata = self.get_complete_metadata(file_path)
            if not metadata:
                return None
            
            # Save metadata to CSV
            base_filename = os.path.splitext(os.path.basename(file_path))[0]
            self.save_to_csv(metadata, base_filename)
            
            # Generate config file
            config_path = os.path.splitext(file_path)[0] + "_config.txt"
            if self.config_converter.create_config_from_txrm(file_path):
                if self.config_converter.save_config(config_path):
                    print("Configuration saved to: {}".format(config_path))
                else:
                    print("Failed to save configuration file!")
            else:
                print("Failed to create configuration!")
            
            # Create individual log file
            log_filename = os.path.splitext(os.path.basename(file_path))[0] + '_processing.log'
            log_path = os.path.join(os.path.dirname(file_path), log_filename)
            
            # Create a file handler for this specific log
            file_handler = logging.FileHandler(log_path)
            file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
            self.logger.addHandler(file_handler)
            
            # Log processing information
            self.logger.info("Processing completed for: %s", file_path)
            self.logger.info("Metadata extracted successfully")
            self.logger.info("Configuration file saved to: %s", config_path)
            
            # Remove the file handler
            self.logger.removeHandler(file_handler)
            file_handler.close()
            
            return metadata
            
        except Exception as e:
            error_msg = "Error processing file {0}: {1}".format(file_path, str(e))
            self.logger.error(error_msg)
            print(error_msg)
            return None
        finally:
            gc.collect()

def get_user_input(prompt, valid_responses=None):
    """Get user input with validation"""
    while True:
        response = raw_input(prompt).strip().lower()
        if valid_responses is None or response in valid_responses:
            return response
        print("Invalid input. Please try again.")

def main():
    if not check_admin():
        user_input = get_user_input("Continue anyway? (y/n): ", ['y', 'n'])
        if user_input != 'y':
            print("Exiting...")
            return

    search_path = raw_input("\nEnter folder path containing .txrm files: ").strip('"')
    while not os.path.exists(search_path):
        print("Path does not exist!")
        search_path = raw_input("Enter a valid folder path: ").strip('"')
    
    # Ask user where to save metadata output
    save_location = get_user_input(
        "\nWhere would you like to save the metadata output folder?\n"
        "1. Current working directory\n"
        "2. Same directory as TXRM files\n"
        "Enter (1/2): ",
        ['1', '2']
    )
    
    # Set output directory based on user choice
    output_dir = os.getcwd() if save_location == '1' else search_path
    processor = EnhancedTXRMProcessor(output_dir=os.path.join(output_dir, "metadata_output"))
    
    # Ask about processing drift files
    include_drift = get_user_input(
        "\nInclude drift files in processing? (y/n): ",
        ['y', 'n']
    ) == 'y'
    
    txrm_files = processor.find_txrm_files(search_path, include_drift)
    
    if not txrm_files:
        print("\nNo .txrm files found in the specified path.")
        return
    
    process_mode = get_user_input(
        "\nChoose processing mode:\n1. Process all files (batch)\n2. Confirm each file\nEnter (1/2): ",
        ['1', '2']
    )
    
    for i, file_path in enumerate(txrm_files, 1):
        print("\nFile {0} of {1}:".format(i, len(txrm_files)))
        print(file_path)
        
        if process_mode == '2':
            process_file = get_user_input(
                "Process this file? (y/n/q to quit): ",
                ['y', 'n', 'q']
            )
            
            if process_file == 'q':
                print("\nProcessing stopped by user.")
                break
            elif process_file == 'n':
                continue
        
        processor.process_single_file(file_path)
        
        if process_mode == '2':
            continue_proc = get_user_input(
                "\nContinue to next file? (y/n): ",
                ['y', 'n']
            )
            if continue_proc == 'n':
                print("\nProcessing stopped by user.")
                break
    
    # Save final CSV
    if processor.all_metadata:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_filename = "metadata_summary_{0}.csv".format(timestamp)
        processor.save_to_csv(csv_filename)
    
    print("\nProcessing complete!")
    print("Check the 'metadata_output' folder for the CSV summary.")
    print("Check each .txrm location for config files")

if __name__ == "__main__":
    main()
