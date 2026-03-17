import os
from XradiaPy import Data
import ConfigParser
from datetime import datetime

class TXRMConfigConverter:
    def __init__(self):
        self.dataset = Data.XRMData.XrmBasicDataSet()
        self.config = ConfigParser.ConfigParser()
    
    def create_config_from_txrm(self, txrm_path):
        """Convert TXRM metadata to config file format"""
        try:
            # Read TXRM file
            self.dataset.ReadFile(txrm_path)
            
            # Initialize ConfigParser with sections
            self._init_config_sections()
            
            # Fill sections with data
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
        """Initialize all config sections"""
        sections = ['General', 'Geometry', 'CT', 'Image', 'Detector', 'Xray', 'Axis']
        for section in sections:
            self.config.add_section(section)
    
    def _fill_general_section(self):
        """Fill [General] section"""
        self.config.set('General', 'Version', '2.8.2.20099')  # Default version
        self.config.set('General', 'Version-pca', '2')
        self.config.set('General', 'Comment', '')
        self.config.set('General', 'LoadDefault', '1')
        self.config.set('General', 'SystemName', 'ZEISS XRM')
    
    def _fill_geometry_section(self):
        """Fill [Geometry] section with TXRM data"""
        # Get first projection for reference
        idx = 0
        self.config.set('Geometry', 'FDD', str(self.dataset.GetDetectorToRADistance(idx)))
        self.config.set('Geometry', 'FOD', str(self.dataset.GetSourceToRADistance(idx)))
        self.config.set('Geometry', 'VoxelSizeX', str(self.dataset.GetPixelSize()))
        self.config.set('Geometry', 'VoxelSizeY', str(self.dataset.GetPixelSize()))
    
    def _fill_ct_section(self):
        """Fill [CT] section with TXRM data"""
        num_projections = self.dataset.GetProjections()
        self.config.set('CT', 'NumberImages', str(num_projections))
        self.config.set('CT', 'Type', '0')
        self.config.set('CT', 'RotationSector', '360.00000000')  # Default full rotation
        self.config.set('CT', 'NrImgDone', str(num_projections))
    
    def _fill_image_section(self):
        """Fill [Image] section with TXRM data"""
        width = self.dataset.GetWidth()
        height = self.dataset.GetHeight()
        
        self.config.set('Image', 'DimX', str(width))
        self.config.set('Image', 'DimY', str(height))
        self.config.set('Image', 'Top', '0')
        self.config.set('Image', 'Left', '0')
        self.config.set('Image', 'Bottom', str(height-1))
        self.config.set('Image', 'Right', str(width-1))
    
    def _fill_detector_section(self):
        """Fill [Detector] section with TXRM data"""
        idx = 0  # First projection for reference
        self.config.set('Detector', 'Binning', str(self.dataset.GetBinning()))
        self.config.set('Detector', 'BitPP', '16')  # Common value
        self.config.set('Detector', 'TimingVal', str(self.dataset.GetExposure(idx)))
        self.config.set('Detector', 'NrPixelsX', str(self.dataset.GetWidth()))
        self.config.set('Detector', 'NrPixelsY', str(self.dataset.GetHeight()))
    
    def _fill_xray_section(self):
        """Fill [Xray] section with TXRM data"""
        self.config.set('Xray', 'Voltage', str(int(self.dataset.GetVoltage())))
        self.config.set('Xray', 'Current', str(int(self.dataset.GetPower())))
        self.config.set('Xray', 'Filter', str(self.dataset.GetFilter()))
    
    def _fill_axis_section(self):
        """Fill [Axis] section with TXRM data"""
        idx = 0  # First projection for reference
        axes = self.dataset.GetAxesNames()
        
        for axis in axes:
            pos = self.dataset.GetAxisPosition(idx, axis)
            clean_name = axis.replace(" ", "")
            self.config.set('Axis', clean_name, str(pos))
    
    def save_config(self, output_path):
        """Save configuration to file"""
        try:
            with open(output_path, 'w') as configfile:
                self.config.write(configfile)
            return True
        except Exception as e:
            print("Error saving config file: {0}".format(str(e)))
            return False

def main():
    converter = TXRMConfigConverter()
    
    # Get input file
    txrm_path = raw_input("Enter path to .txrm file: ").strip('"')
    if not os.path.exists(txrm_path):
        print("File not found!")
        return
    
    # Process file
    print("Processing TXRM file...")
    if converter.create_config_from_txrm(txrm_path):
        # Create output path
        output_path = os.path.splitext(txrm_path)[0] + "_config.txt"
        
        # Save config
        if converter.save_config(output_path):
            print("Configuration saved to: {0}".format(output_path))
        else:
            print("Failed to save configuration file!")
    else:
        print("Failed to process TXRM file!")

if __name__ == "__main__":
    main()
