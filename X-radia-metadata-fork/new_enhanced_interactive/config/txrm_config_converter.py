# -*- coding: utf-8 -*-
from __future__ import print_function
import ConfigParser
from XradiaPy import Data
from new_enhanced_interactive.utils.logging_utils import setup_logger

class TXRMConfigConverter(object):
    def __init__(self):
        self.dataset = Data.XRMData.XrmBasicDataSet()
        self.config = None
        self.logger = setup_logger('txrm_config')
        self.metadata = None  # Add metadata storage

    def _init_config_sections(self):
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
        num_projections = self.dataset.GetProjections()
        self.config.set('CT', 'NumberImages', str(num_projections))
        self.config.set('CT', 'Type', '0')
        self.config.set('CT', 'RotationSector', '360.00000000')
        self.config.set('CT', 'NrImgDone', str(num_projections))

    def _fill_image_section(self):
        self.config.set('Image', 'Width', str(self.dataset.GetWidth()))
        self.config.set('Image', 'Height', str(self.dataset.GetHeight()))

    def _fill_detector_section(self):
        self.config.set('Detector', 'Binning', str(self.dataset.GetBinning()))

    def _fill_axis_section(self):
        """Fill the Axis section with actual axis positions from the metadata"""
        # Map of config file axis names to metadata axis names
        axis_mapping = {
            'sample x': 'Sample_X_pos',
            'sample y': 'Sample_Y_pos',
            'sample z': 'Sample_Z_pos',
            'sample theta': 'Sample_Theta_pos',
            'source x': 'Source_X_pos',
            'source z': 'Source_Z_pos',
            'detector z': 'Detector_Z_pos',
            'ccd_z': 'CCD_Z_pos',
            'ccd_x': 'CCD_X_pos',
            'flat panel x': 'Flat_Panel_X_pos',
            'flat panel z': 'Flat_Panel_Z_pos',
            'mkiv filter wheel': 'MkIV_Filter_Wheel_pos',
            'dct': 'DCT_pos'
        }
        
        try:
            if self.metadata and 'projection_data' in self.metadata and self.metadata['projection_data']:
                # Get first projection data
                first_proj = self.metadata['projection_data'][0]
                
                # Set each axis position in the config
                for config_name, metadata_name in axis_mapping.items():
                    if metadata_name in first_proj:
                        value = first_proj[metadata_name]
                        if value is not None:
                            self.config.set('Axis', config_name, str(value))
                            self.logger.info("Set axis %s to %s", config_name, value)
                        else:
                            self.logger.warning("Axis %s value is None", metadata_name)
                            self.config.set('Axis', config_name, '0.0')
                    else:
                        self.logger.warning("Axis %s not found in metadata", metadata_name)
                        self.config.set('Axis', config_name, '0.0')
            else:
                self.logger.error("No projection data found in metadata")
                # Fallback to dataset if metadata is not available
                positions = self.dataset.GetAxisPositions(0)
                for config_name, metadata_name in axis_mapping.items():
                    dataset_name = metadata_name.replace('_pos', '')  # Convert metadata name to dataset name
                    if dataset_name in positions:
                        self.config.set('Axis', config_name, str(positions[dataset_name]))
                    else:
                        self.logger.warning("Axis %s not found in dataset", dataset_name)
                        self.config.set('Axis', config_name, '0.0')
        except Exception as e:
            self.logger.error("Error setting axis positions: %s", str(e), exc_info=True)
            # Fallback to setting all axes to 0.0 if there's an error
            for config_name in axis_mapping:
                self.config.set('Axis', config_name, '0.0')

    def _fill_general_section(self):
        self.config.set('General', 'Version', '1.0')

    def create_config_from_txrm(self, txrm_path, metadata=None):
        """Create config from TXRM file, optionally using provided metadata"""
        try:
            self.config = ConfigParser.ConfigParser()
            self.metadata = metadata  # Store metadata for use in axis section
            
            # Ensure txrm_path is a proper string and normalize path separators
            txrm_path = str(txrm_path).replace('\\', '/')
            
            # Reset the dataset before reading a new file
            self.dataset = Data.XRMData.XrmBasicDataSet()
            
            # Read the file
            self.dataset.ReadFile(txrm_path)
            
            self._init_config_sections()
            self._fill_geometry_section()
            self._fill_ct_and_xray_section()
            self._fill_image_section()
            self._fill_detector_section()
            self._fill_axis_section()
            self._fill_general_section()
            return True
        except Exception as e:
            self.logger.error("Error processing TXRM file: %s", str(e), exc_info=True)
            return False

    def save_config(self, output_path):
        try:
            with open(output_path, 'w') as configfile:
                self.config.write(configfile)
            return True
        except Exception as e:
            self.logger.error("Error saving config file: %s", str(e))
            return False

    # ... (rest of the config converter methods) 