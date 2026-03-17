import os
from XradiaPy import Data
import json
from datetime import datetime
import logging
import sys

class InteractiveTXRMProcessor:
    def __init__(self, output_dir=None):
        self.dataset = Data.XRMData.XrmBasicDataSet()
        self.output_dir = output_dir or os.getcwd()
        
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        
        # Setup logging
        log_file = os.path.join(self.output_dir, 'txrm_processing_{0}.log'.format(
            datetime.now().strftime("%Y%m%d_%H%M%S")))
        logging.basicConfig(
            filename=log_file,
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

    def find_txrm_files(self, search_path):
        """Find all .txrm files in the given path and its subdirectories"""
        txrm_files = []
        print("\nSearching for .txrm files in: {0}".format(search_path))
        
        try:
            for root, _, files in os.walk(search_path):
                for file in files:
                    if file.lower().endswith('.txrm'):
                        full_path = os.path.join(root, file)
                        txrm_files.append(full_path)
                        print("Found: {0}".format(full_path))
        
        except Exception as e:
            print("Error searching directory: {0}".format(str(e)))
            self.logger.error("Directory search error: {0}".format(str(e)))
        
        return txrm_files

    def get_metadata(self, file_path):
        """Extract metadata from a single file"""
        try:
            print("\nProcessing file: {0}".format(file_path))
            self.dataset.ReadFile(file_path)
            
            # Get all available axes
            axes = self.dataset.GetAxesNames()
            
            # Get number of projections
            num_projections = self.dataset.GetProjections()
            
            metadata = {
                "file_info": {
                    "file_path": file_path,
                    "file_name": self.dataset.GetName(),
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
            
            return metadata

        except Exception as e:
            error_msg = "Error processing file {0}: {1}".format(file_path, str(e))
            self.logger.error(error_msg)
            print(error_msg)
            return None

    def _get_projection_summary(self, num_projections, axes):
        """Create summary of projection data"""
        if num_projections == 0:
            return {}

        try:
            exposures = []
            detector_distances = []
            source_distances = []
            axis_positions = {axis: [] for axis in axes}
            
            for idx in range(num_projections):
                exposures.append(self.dataset.GetExposure(idx))
                detector_distances.append(self.dataset.GetDetectorToRADistance(idx))
                source_distances.append(self.dataset.GetSourceToRADistance(idx))
                
                for axis in axes:
                    axis_positions[axis].append(self.dataset.GetAxisPosition(idx, axis))

            summary = {
                "projection_count": num_projections,
                "time_span": {
                    "start_date": self.dataset.GetDate(0),
                    "end_date": self.dataset.GetDate(num_projections - 1)
                },
                "exposure_times": {
                    "min": min(exposures),
                    "max": max(exposures),
                    "mean": sum(exposures) / len(exposures)
                },
                "axis_ranges": {}
            }

            for axis in axes:
                positions = axis_positions[axis]
                summary["axis_ranges"][axis] = {
                    "min": min(positions),
                    "max": max(positions),
                    "range": max(positions) - min(positions)
                }

            return summary

        except Exception as e:
            print("Error creating projection summary: {0}".format(str(e)))
            return {}

    def save_metadata(self, metadata, file_path):
        """Save metadata to JSON file"""
        if not metadata:
            return None

        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_filename = os.path.splitext(os.path.basename(file_path))[0]
            output_path = os.path.join(
                self.output_dir, 
                "{0}_metadata_{1}.json".format(base_filename, timestamp)
            )
            
            with open(output_path, 'w') as f:
                json.dump(metadata, f, indent=4, sort_keys=True)
            
            print("Metadata saved to: {0}".format(output_path))
            return output_path

        except Exception as e:
            print("Error saving metadata: {0}".format(str(e)))
            return None

def get_user_input(prompt, valid_responses=None):
    """Get user input with validation"""
    while True:
        response = raw_input(prompt).strip().lower()
        if valid_responses is None or response in valid_responses:
            return response
        print("Invalid input. Please try again.")

def main():
    print("TXRM File Processor")
    print("==================")
    
    # Get search path
    search_path = get_user_input("\nEnter the folder path to search for .txrm files: ")
    while not os.path.exists(search_path):
        print("Path does not exist!")
        search_path = get_user_input("Enter a valid folder path: ")
    
    # Initialize processor
    processor = InteractiveTXRMProcessor(output_dir="metadata_output")
    
    # Find files
    txrm_files = processor.find_txrm_files(search_path)
    
    if not txrm_files:
        print("\nNo .txrm files found in the specified path.")
        return
    
    print("\nFound {0} .txrm files.".format(len(txrm_files)))
    
    # Process files with user supervision
    for i, file_path in enumerate(txrm_files, 1):
        print("\nFile {0} of {1}:".format(i, len(txrm_files)))
        print(file_path)
        
        process = get_user_input(
            "Process this file? (y/n/q to quit): ",
            valid_responses=['y', 'n', 'q']
        )
        
        if process == 'q':
            print("\nProcessing stopped by user.")
            break
            
        if process == 'y':
            print("\nExtracting metadata...")
            metadata = processor.get_metadata(file_path)
            
            if metadata:
                processor.save_metadata(metadata, file_path)
                
                print("\nMetadata Summary:")
                print("Objective: {0}".format(metadata["machine_settings"]["objective"]))
                print("Total Projections: {0}".format(metadata["image_properties"]["total_projections"]))
                print("Resolution: {0}x{1}".format(
                    metadata["image_properties"]["width_pixels"],
                    metadata["image_properties"]["height_pixels"]
                ))
            
            continue_proc = get_user_input(
                "\nContinue to next file? (y/n): ",
                valid_responses=['y', 'n']
            )
            
            if continue_proc == 'n':
                print("\nProcessing stopped by user.")
                break
    
    print("\nProcessing complete!")
    print("Check the 'metadata_output' folder for results.")

if __name__ == "__main__":
    main()
