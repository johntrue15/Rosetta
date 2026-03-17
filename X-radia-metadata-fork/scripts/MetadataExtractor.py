import os
from XradiaPy import Data
import json
from datetime import datetime
import logging
import numpy as np

class MetadataExtractor:
    def __init__(self, output_dir=None):
        self.dataset = Data.XRMData.XrmBasicDataSet()
        self.output_dir = output_dir or os.getcwd()
        
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        
        logging.basicConfig(
            filename=os.path.join(self.output_dir, 'metadata_extraction.log'),
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

    def get_metadata(self, file_path):
        try:
            print("Processing file: {0}".format(file_path))
            self.dataset.ReadFile(file_path)
            
            # Get all available axes
            axes = self.dataset.GetAxesNames()
            
            # Get number of projections
            num_projections = self.dataset.GetProjections()
            
            # Initialize metadata dictionary
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
                
                "axes_info": {
                    "available_axes": list(axes)
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
        """Summarize projection data with statistics"""
        if num_projections == 0:
            return {}

        # Initialize lists to store data for statistics
        exposures = []
        detector_distances = []
        source_distances = []
        axis_positions = {axis: [] for axis in axes}
        
        # Collect data from all projections
        for idx in range(num_projections):
            exposures.append(self.dataset.GetExposure(idx))
            detector_distances.append(self.dataset.GetDetectorToRADistance(idx))
            source_distances.append(self.dataset.GetSourceToRADistance(idx))
            
            for axis in axes:
                axis_positions[axis].append(self.dataset.GetAxisPosition(idx, axis))

        # Create summary with statistics
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
            "detector_distances": {
                "min": min(detector_distances),
                "max": max(detector_distances),
                "mean": sum(detector_distances) / len(detector_distances)
            },
            "source_distances": {
                "min": min(source_distances),
                "max": max(source_distances),
                "mean": sum(source_distances) / len(source_distances)
            },
            "axis_ranges": {}
        }

        # Add statistics for each axis
        for axis in axes:
            positions = axis_positions[axis]
            summary["axis_ranges"][axis] = {
                "min": min(positions),
                "max": max(positions),
                "mean": sum(positions) / len(positions),
                "range": max(positions) - min(positions)
            }

        return summary

    def save_to_json(self, metadata, file_path):
        """Save metadata to a JSON file with pretty printing"""
        if not metadata:
            print("No metadata to save")
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_filename = os.path.splitext(os.path.basename(file_path))[0]
        output_path = os.path.join(
            self.output_dir, 
            "{0}_metadata_{1}.json".format(base_filename, timestamp)
        )
        
        try:
            with open(output_path, 'w') as f:
                json.dump(metadata, f, indent=4, sort_keys=True)
            print("Metadata saved to {0}".format(output_path))
            return output_path
        except Exception as e:
            print("Error saving JSON: {0}".format(str(e)))
            return None

def main():
    extractor = MetadataExtractor(output_dir="output")
    
    # Process single file - replace with your file path
    file_path = r"C:\path\to\your\file.txrm"
    
    print("\nExtracting metadata from: {0}".format(file_path))
    metadata = extractor.get_metadata(file_path)
    
    if metadata:
        # Save to JSON
        extractor.save_to_json(metadata, file_path)
        
        # Print summary to console
        print("\nMetadata Summary:")
        print("File: {0}".format(metadata["file_info"]["file_name"]))
        print("Objective: {0}".format(metadata["machine_settings"]["objective"]))
        print("Total Projections: {0}".format(metadata["image_properties"]["total_projections"]))
        print("Resolution: {0}x{1}".format(
            metadata["image_properties"]["width_pixels"],
            metadata["image_properties"]["height_pixels"]
        ))

if __name__ == "__main__":
    main()
