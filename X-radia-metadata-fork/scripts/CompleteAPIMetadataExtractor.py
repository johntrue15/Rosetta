import os
from XradiaPy import Data
import csv
from datetime import datetime
import logging

class CompleteAPIMetadataExtractor:
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

    def get_basic_info(self):
        basic_info = {
            'file_name': self.dataset.GetName(),
            'initialized_correctly': self.dataset.IsInitializedCorrectly()
        }
        return basic_info

    def get_machine_settings(self):
        settings = {
            'objective': self.dataset.GetObjective(),
            'pixel_size': self.dataset.GetPixelSize(),
            'power': self.dataset.GetPower(),
            'voltage': self.dataset.GetVoltage(),
            'filter': self.dataset.GetFilter(),
            'binning': self.dataset.GetBinning()
        }
        return settings

    def get_image_properties(self):
        properties = {
            'height': self.dataset.GetHeight(),
            'width': self.dataset.GetWidth(),
            'total_projections': self.dataset.GetProjections()
        }
        return properties

    def get_images_per_projection(self, tomo_point_index):
        """
        Gets the number of images that will be taken per projection of the recipe point at the index.
        Only use this function for a flat panel detector.
        
        Args:
            tomo_point_index (int): The index of the recipe point that will be checked.
            
        Returns:
            int: Number of images per projection, or -1 if the function fails.
        """
        try:
            images_per_projection = self.dataset.GetImagesPerProjection(tomo_point_index)
            return images_per_projection
        except Exception as e:
            error_msg = f"Error getting images per projection for index {tomo_point_index}: {str(e)}"
            self.logger.error(error_msg)
            print(error_msg)
            return -1
            
    def set_images_per_projection(self, tomo_point_index, images_per_projection):
        """
        Sets the number of images that will be taken per projection of the recipe point at the index.
        
        Args:
            tomo_point_index (int): The index of the recipe point that will be checked.
            images_per_projection (int): The number of images that will be taken per projection.
            
        Returns:
            bool: True if the function succeeds, False if the function fails.
        """
        try:
            result = self.dataset.SetImagesPerProjection(tomo_point_index, images_per_projection)
            return result
        except Exception as e:
            error_msg = f"Error setting images per projection for index {tomo_point_index}: {str(e)}"
            self.logger.error(error_msg)
            print(error_msg)
            return False
    
    def get_number_of_frames_per_image(self, tomo_point_index):
        """
        Gets the number of frames per image of the recipe point at the index.
        Only use this function for a flat panel detector.
        
        Args:
            tomo_point_index (int): The index of the recipe point that will be checked.
            
        Returns:
            int: Number of frames per image, or -1 if the function fails.
        """
        try:
            frames_per_image = self.dataset.GetNumberOfFramesPerImage(tomo_point_index)
            return frames_per_image
        except Exception as e:
            error_msg = f"Error getting frames per image for index {tomo_point_index}: {str(e)}"
            self.logger.error(error_msg)
            print(error_msg)
            return -1
    
    def set_number_of_frames_per_image(self, tomo_point_index, frames):
        """
        Sets the number of frames per image of the recipe point at the index.
        Only use this function for detectors with a flat panel.
        
        Args:
            tomo_point_index (int): The index of the recipe point that will be checked.
            frames (int): The new value for the number of frames per image.
            
        Returns:
            bool: True if the function succeeds, False if the function fails.
        """
        try:
            result = self.dataset.SetNumberOfFramesPerImage(tomo_point_index, frames)
            return result
        except Exception as e:
            error_msg = f"Error setting frames per image for index {tomo_point_index}: {str(e)}"
            self.logger.error(error_msg)
            print(error_msg)
            return False

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

def main():
    extractor = CompleteAPIMetadataExtractor(output_dir="output")
    
    # Process single file - replace with your file path
    file_path = r"C:\path\to\your\file.txrm"
    
    print("\nExtracting complete metadata from: {0}".format(file_path))
    data = extractor.get_complete_metadata(file_path)
    
    if data:
        print("\nBasic Info:")
        for key, value in data['basic_info'].items():
            print("{0}: {1}".format(key, value))
            
        print("\nMachine Settings:")
        for key, value in data['machine_settings'].items():
            print("{0}: {1}".format(key, value))
            
        print("\nImage Properties:")
        for key, value in data['image_properties'].items():
            print("{0}: {1}".format(key, value))
        
        print("\nFound {0} projections".format(len(data['projection_data'])))
        print("Available axes: {0}".format(", ".join(data['available_axes'])))
        
        # Save all data to CSV files
        base_filename = os.path.splitext(os.path.basename(file_path))[0]
        extractor.save_to_csv(data, base_filename)

if __name__ == "__main__":
    main()
