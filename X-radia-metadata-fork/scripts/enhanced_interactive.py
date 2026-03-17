import os
import sys
import json
import csv
import ctypes
import ConfigParser
from XradiaPy import Data
from datetime import datetime
import logging
import gc

def check_admin():
    try:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin()
        if not is_admin:
            print("\nWARNING: Script requires administrator privileges.")
            print("Please run PyCharm as administrator.\n")
            return False
        return True
    except:
        print("\nCouldn't verify admin privileges.")
        return False

class TXRMConfigConverter:
    def __init__(self):
        self.dataset = Data.XRMData.XrmBasicDataSet()
        self.config = None  # Initialize as None
    
    def create_config_from_txrm(self, txrm_path):
        try:
            # Reset config object for each new file
            self.config = ConfigParser.ConfigParser()
            
            self.dataset.ReadFile(txrm_path)
            self._init_config_sections()
            self._fill_general_section()
            self._fill_geometry_section()
            self._fill_ct_section()
            self._fill_image_section()
            self._fill_detector_section()
            self._fill_xray_section()
            self._fill_axis_section()
            return True
        except Exception as e:
            print("Error processing TXRM file: {0}".format(str(e)))
            return False
    
    def _init_config_sections(self):
        sections = ['General', 'Geometry', 'CT', 'Image', 'Detector', 'Xray', 'Axis']
        for section in sections:
            self.config.add_section(section)
    
    def _fill_general_section(self):
        self.config.set('General', 'Version', '2.8.2.20099')
        self.config.set('General', 'Version-pca', '2')
        self.config.set('General', 'Comment', '')
        self.config.set('General', 'LoadDefault', '1')
        self.config.set('General', 'SystemName', 'ZEISS XRM')
    
    def _fill_geometry_section(self):
        idx = 0
        self.config.set('Geometry', 'FDD', str(self.dataset.GetDetectorToRADistance(idx)))
        self.config.set('Geometry', 'FOD', str(self.dataset.GetSourceToRADistance(idx)))
        self.config.set('Geometry', 'VoxelSizeX', str(self.dataset.GetPixelSize()))
        self.config.set('Geometry', 'VoxelSizeY', str(self.dataset.GetPixelSize()))
    
    def _fill_ct_section(self):
        num_projections = self.dataset.GetProjections()
        self.config.set('CT', 'NumberImages', str(num_projections))
        self.config.set('CT', 'Type', '0')
        self.config.set('CT', 'RotationSector', '360.00000000')
        self.config.set('CT', 'NrImgDone', str(num_projections))
    
    def _fill_image_section(self):
        width = self.dataset.GetWidth()
        height = self.dataset.GetHeight()
        self.config.set('Image', 'DimX', str(width))
        self.config.set('Image', 'DimY', str(height))
        self.config.set('Image', 'Top', '0')
        self.config.set('Image', 'Left', '0')
        self.config.set('Image', 'Bottom', str(height-1))
        self.config.set('Image', 'Right', str(width-1))
    
    def _fill_detector_section(self):
        idx = 0
        self.config.set('Detector', 'Binning', str(self.dataset.GetBinning()))
        self.config.set('Detector', 'BitPP', '16')
        self.config.set('Detector', 'TimingVal', str(self.dataset.GetExposure(idx)))
        self.config.set('Detector', 'NrPixelsX', str(self.dataset.GetWidth()))
        self.config.set('Detector', 'NrPixelsY', str(self.dataset.GetHeight()))
    
    def _fill_xray_section(self):
        self.config.set('Xray', 'Voltage', str(int(self.dataset.GetVoltage())))
        self.config.set('Xray', 'Current', str(int(self.dataset.GetPower())))
        self.config.set('Xray', 'Filter', str(self.dataset.GetFilter()))
    
    def _fill_axis_section(self):
        idx = 0
        axes = self.dataset.GetAxesNames()
        for axis in axes:
            pos = self.dataset.GetAxisPosition(idx, axis)
            clean_name = axis.replace(" ", "")
            self.config.set('Axis', clean_name, str(pos))
    
    def save_config(self, output_path):
        try:
            with open(output_path, 'w') as configfile:
                self.config.write(configfile)
            return True
        except Exception as e:
            print("Error saving config file: {0}".format(str(e)))
            return False

class EnhancedTXRMProcessor:
    def __init__(self, output_dir=None):
        self.dataset = Data.XRMData.XrmBasicDataSet()
        self.output_dir = output_dir or os.path.join(os.getcwd(), "metadata_output")
        self.all_metadata = []
        self.config_converter = TXRMConfigConverter()
        
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        
        log_file = os.path.join(self.output_dir, 
                               'processing_{0}.log'.format(
                                   datetime.now().strftime("%Y%m%d_%H%M%S")))
        logging.basicConfig(
            filename=log_file,
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

    def find_txrm_files(self, search_path):
        txrm_files = []
        folder_structure = {}
        total_files = 0
        
        print("\nSearching for .txrm files in: {0}".format(search_path))
        
        try:
            for root, dirs, files in os.walk(search_path):
                txrm_in_folder = [f for f in files if f.lower().endswith('.txrm')]
                if txrm_in_folder:
                    rel_path = os.path.relpath(root, search_path)
                    folder_structure[rel_path] = len(txrm_in_folder)
                    total_files += len(txrm_in_folder)
                    
                    for file in txrm_in_folder:
                        full_path = os.path.join(root, file)
                        txrm_files.append(full_path)
                        print("Found: {0}".format(full_path))

            print("\nFolder Structure Summary:")
            for folder, count in folder_structure.items():
                print("  {0}: {1} TXRM files".format(folder, count))
            print("\nTotal TXRM files found: {0}".format(total_files))
        
        except Exception as e:
            error_msg = "Directory search error: {0}".format(str(e))
            print(error_msg)
            self.logger.error(error_msg)
        
        return txrm_files

    def get_metadata(self, file_path):
        try:
            print("\nProcessing file: {0}".format(file_path))
            self.dataset.ReadFile(file_path)
            
            axes = self.dataset.GetAxesNames()
            num_projections = self.dataset.GetProjections()
            
            metadata = {
                "file_info": {
                    "file_path": file_path,
                    "file_hyperlink": '=HYPERLINK("{0}", "Click to Open")'.format(
                        file_path.replace("\\", "\\\\")),
                    "file_name": os.path.basename(file_path),
                    "folder_path": os.path.dirname(file_path),
                    "acquisition_complete": self.dataset.IsInitializedCorrectly()
                },
                "machine_settings": {
                    "objective": self.dataset.GetObjective(),
                    "pixel_size_um": self.dataset.GetPixelSize(),
                    "power_watts": self.dataset.GetPower(),
                    "voltage_kv": self.dataset.GetVoltage(),
                    "filter": self.dataset.GetFilter(),
                    "binning": self.dataset.GetBinning()
                },
                "image_properties": {
                    "height_pixels": self.dataset.GetHeight(),
                    "width_pixels": self.dataset.GetWidth(),
                    "total_projections": num_projections
                },
                "projection_summary": self._get_projection_summary(num_projections, axes)
            }
            
            self.all_metadata.append(self._flatten_metadata(metadata))
            return metadata

        except Exception as e:
            error_msg = "Error processing file {0}: {1}".format(file_path, str(e))
            self.logger.error(error_msg)
            print(error_msg)
            return None
        finally:
            gc.collect()

    def _get_projection_summary(self, num_projections, axes):
        if num_projections == 0:
            return {}

        try:
            summary = {
                "projection_count": num_projections,
                "time_span": {
                    "start_date": self.dataset.GetDate(0),
                    "end_date": self.dataset.GetDate(num_projections - 1)
                },
                "exposure": self.dataset.GetExposure(0)
            }

            for axis in axes:
                first_pos = self.dataset.GetAxisPosition(0, axis)
                last_pos = self.dataset.GetAxisPosition(num_projections - 1, axis)
                summary["{0}_start".format(axis)] = first_pos
                summary["{0}_end".format(axis)] = last_pos
                summary["{0}_range".format(axis)] = last_pos - first_pos

            return summary

        except Exception as e:
            print("Error creating projection summary: {0}".format(str(e)))
            return {}

    def _flatten_metadata(self, metadata):
        flat_data = {}
        flat_data['file_hyperlink'] = metadata['file_info']['file_hyperlink']
        
        for key, value in metadata['file_info'].items():
            if key != 'file_hyperlink':
                flat_data["file_{0}".format(key)] = value
            
        for key, value in metadata['machine_settings'].items():
            flat_data["machine_{0}".format(key)] = value
            
        for key, value in metadata['image_properties'].items():
            flat_data["image_{0}".format(key)] = value
            
        for key, value in metadata['projection_summary'].items():
            if isinstance(value, dict):
                for subkey, subvalue in value.items():
                    flat_data["proj_{0}_{1}".format(key, subkey)] = subvalue
            else:
                flat_data["proj_{0}".format(key)] = value
                
        return flat_data

    def process_single_file(self, file_path):
        try:
            print("\nProcessing: {0}".format(file_path))
            
            # Get metadata
            metadata = self.get_metadata(file_path)
            
            # Generate config file
            config_path = os.path.splitext(file_path)[0] + "_config.txt"
            if self.config_converter.create_config_from_txrm(file_path):
                if self.config_converter.save_config(config_path):
                    print("Configuration saved to: {0}".format(config_path))
                else:
                    print("Failed to save configuration file!")
            else:
                print("Failed to create configuration!")
            
            return metadata
            
        except Exception as e:
            error_msg = "Error processing file {0}: {1}".format(file_path, str(e))
            self.logger.error(error_msg)
            print(error_msg)
            return None
        finally:
            gc.collect()

    def save_to_csv(self, filename="metadata_summary.csv"):
        if not self.all_metadata:
            print("No metadata to save")
            return

        output_path = os.path.join(self.output_dir, filename)
        
        try:
            with open(output_path, 'wb') as csvfile:
                fieldnames = self.all_metadata[0].keys()
                fieldnames = ['file_hyperlink'] + [f for f in fieldnames if f != 'file_hyperlink']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                writer.writerows(self.all_metadata)
                
            print("\nMetadata summary saved to: {0}".format(output_path))
            return output_path
            
        except Exception as e:
            error_msg = "Error saving CSV: {0}".format(str(e))
            print(error_msg)
            self.logger.error(error_msg)
            return None

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

    processor = EnhancedTXRMProcessor()
    
    search_path = raw_input("\nEnter folder path containing .txrm files: ").strip('"')
    while not os.path.exists(search_path):
        print("Path does not exist!")
        search_path = raw_input("Enter a valid folder path: ").strip('"')
    
    txrm_files = processor.find_txrm_files(search_path)
    
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
    print("Check each .txrm location for config files")
    print("Check the 'metadata_output' folder for the CSV summary.")

if __name__ == "__main__":
    main()
