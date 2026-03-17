from XradiaPy import Data

class MetadataExtractor(object):
    def __init__(self):
        self.dataset = Data.XRMData.XrmBasicDataSet()

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

    def get_images_per_projection(self, tomo_point_index=0):
        """
        Gets the number of images that will be taken per projection of the recipe point at the index.
        Only applicable for flat panel detectors.
        
        Args:
            tomo_point_index (int): The index of the recipe point to check. Defaults to 0.
            
        Returns:
            int: Number of images per projection, or 1 if the function fails or is not applicable.
        """
        try:
            images_per_projection = self.dataset.GetImagesPerProjection(tomo_point_index)
            return images_per_projection
        except Exception as e:
            print("Error getting images per projection: {0}".format(str(e)))
            return 1  # Default to 1 if the function fails

    def get_axis_positions(self, projection_idx):
        axis_data = {}
        axis_names = self.dataset.GetAxesNames()
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
        proj_data.update(self.get_axis_positions(projection_idx))
        return proj_data

    def get_complete_metadata(self, file_path):
        """Extract all metadata from a TXRM file"""
        try:
            # Ensure file_path is a proper string and normalize path separators
            file_path = str(file_path).replace('\\', '/')
            
            # Reset the dataset before reading a new file
            self.dataset = Data.XRMData.XrmBasicDataSet()
            
            # Read the file
            self.dataset.ReadFile(file_path)
            
            if not self.dataset.IsInitializedCorrectly():
                print("File was not initialized correctly: {}".format(file_path))
                return None
            
            metadata = {}
            metadata['basic_info'] = self.get_basic_info()
            metadata['machine_settings'] = self.get_machine_settings()
            metadata['image_properties'] = self.get_image_properties()
            
            # Get detector-specific information for flat panel detectors
            metadata['detector_info'] = {
                'images_per_projection': self.get_images_per_projection()
            }
            
            # Extract data for each projection
            metadata['projection_data'] = []
            num_projections = self.dataset.GetProjections()
            for idx in range(num_projections):
                proj_data = self.get_projection_data(idx)
                metadata['projection_data'].append(proj_data)
            
            return metadata
        except Exception as e:
            print("Error extracting metadata: {0}".format(str(e)))
            return None 