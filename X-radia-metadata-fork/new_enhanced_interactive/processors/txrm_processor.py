# -*- coding: utf-8 -*-
from __future__ import print_function, division
import os
import csv
from datetime import datetime
import gc
import time

# Fix the imports to use absolute imports from the package root
from new_enhanced_interactive.config.txrm_config_converter import TXRMConfigConverter
from new_enhanced_interactive.metadata.metadata_extractor import MetadataExtractor
from new_enhanced_interactive.utils.logging_utils import setup_logger
from new_enhanced_interactive.utils.validation_utils import TXRMValidator

class TXRMProcessor(object):
    def __init__(self, output_dir=None):
        self.output_dir = output_dir or os.path.join(os.getcwd(), "metadata_output")
        
        # Create output directory if it doesn't exist
        if not os.path.exists(self.output_dir):
            try:
                os.makedirs(self.output_dir)
            except Exception as e:
                print("Warning: Could not create output directory: {}".format(str(e)))
        
        self.all_metadata = []  # Store metadata from all processed files
        self.config_converter = TXRMConfigConverter()
        self.metadata_extractor = MetadataExtractor()
        self.validator = TXRMValidator()
        self.logger = setup_logger('txrm_processor')

    def save_metadata_txt(self, metadata, file_path):
        """Save metadata as formatted text file next to TXRM file"""
        txt_path = os.path.splitext(file_path)[0] + "_metadata.txt"
        try:
            with open(txt_path, 'w') as f:
                # Write file info
                f.write("TXRM File Metadata\n")
                f.write("=" * 50 + "\n\n")
                
                # File Hash
                f.write("File Information:\n")
                f.write("-" * 20 + "\n")
                f.write("SHA-256 Hash: %s\n" % metadata['file_hash'])
                f.write("File Size: %s bytes\n" % metadata['validation_info'].get('size', 'Unknown'))
                f.write("Validated At: %s\n\n" %
                    time.strftime('%Y-%m-%d %H:%M:%S', 
                    time.localtime(metadata['validation_info'].get('validated_at', 0))))
                
                # Basic Info
                f.write("Basic Information:\n")
                f.write("-" * 20 + "\n")
                for key, value in metadata['basic_info'].items():
                    f.write("%s: %s\n" % (key, value))
                f.write("\n")
                
                # Machine Settings
                f.write("Machine Settings:\n")
                f.write("-" * 20 + "\n")
                for key, value in metadata['machine_settings'].items():
                    f.write("%s: %s\n" % (key, value))
                f.write("\n")
                
                # Image Properties
                f.write("Image Properties:\n")
                f.write("-" * 20 + "\n")
                for key, value in metadata['image_properties'].items():
                    f.write("%s: %s\n" % (key, value))
                f.write("\n")
                
                # Detector Information
                if 'detector_info' in metadata:
                    f.write("Detector Information:\n")
                    f.write("-" * 20 + "\n")
                    for key, value in metadata['detector_info'].items():
                        f.write("%s: %s\n" % (key, value))
                    f.write("\n")
                
                # Projection Data Summary
                f.write("Projection Data Summary:\n")
                f.write("-" * 20 + "\n")
                if metadata['projection_data']:
                    first_proj = metadata['projection_data'][0]
                    last_proj = metadata['projection_data'][-1]
                    f.write("Total Projections: %s\n" % len(metadata['projection_data']))
                    f.write("First Projection Date: %s\n" % first_proj['date'])
                    f.write("Last Projection Date: %s\n" % last_proj['date'])
                    
                    # Write axis positions for first and last projections
                    f.write("\nFirst Projection Axis Positions:\n")
                    for key, value in first_proj.items():
                        if '_pos' in key:
                            f.write("%s: %s\n" % (key, value))
                            
                    f.write("\nLast Projection Axis Positions:\n")
                    for key, value in last_proj.items():
                        if '_pos' in key:
                            f.write("%s: %s\n" % (key, value))
            
            self.logger.info("Metadata text file saved to: %s", txt_path)
            return True
        
        except Exception as e:
            error_msg = "Error saving metadata text file: %s" % str(e)
            self.logger.error(error_msg)
            print(error_msg)
            return False

    def _get_file_name(self, m):
        """Get file name without extension"""
        return os.path.splitext(os.path.basename(m.get('file_path', '')))[0]

    def _get_file_path(self, m):
        """Get file path"""
        return m.get('file_path', '')

    def _get_file_hyperlink(self, m):
        """Create a file hyperlink that opens the file when clicked"""
        file_path = m.get('file_path', '')
        if file_path:
            # Create a hyperlink formula that works in Excel
            # Use file:/// protocol for local files to ensure it works on the same workstation
            file_url = 'file:///' + file_path.replace('\\', '/').lstrip('/')
            return '=HYPERLINK("{0}","{1}")'.format(
                file_url,
                os.path.basename(file_path)
            )
        return ''

    def _calculate_xray_power(self, metadata):
        """Safely calculate X-ray tube power if not already available"""
        try:
            # First check if power is already available
            power = metadata['machine_settings'].get('power')
            if power is not None and power != '':
                return str(power)
                
            # If not, calculate from voltage and current
            voltage = float(metadata['machine_settings'].get('voltage', 0))
            # Current is in μA, need to convert to A for power calculation
            current_ua = float(metadata['machine_settings'].get('current', 0))
            if voltage > 0 and current_ua > 0:
                # Convert μA to A (divide by 1,000,000) then multiply by voltage
                power_watts = (current_ua / 1000000) * voltage
                return str(round(power_watts, 2))
            return ''
        except (ValueError, TypeError, ZeroDivisionError):
            return ''

    def save_cumulative_csv(self):
        """Save all collected metadata to a single CSV file with specified column order"""
        if not self.all_metadata:
            self.logger.warning("No metadata to save to cumulative CSV")
            return False
        
        # Filter out any None or empty metadata entries
        filtered_metadata = [m for m in self.all_metadata if m and isinstance(m, dict)]
        
        if not filtered_metadata:
            self.logger.warning("No valid metadata entries to save after filtering")
            return False
            
        # Define column order and mappings with clear descriptions based on new format
        column_order = [
            # File Information
            ('file_hash', lambda m: m.get('file_hash', '')),  # File hash (SHA-256)
            ('file_name', self._get_file_name),  # FILE NAME (minus .txrm)
            ('file_hyperlink', self._get_file_hyperlink),  # File hyperlink
            ('ct_voxel_size_um', lambda m: str(m['machine_settings'].get('pixel_size', '0.0'))),  # CT: Voxel size (um)
            ('ct_objective', lambda m: str(m['machine_settings'].get('objective', ''))),  # CT: Objective
            ('ct_number_images', lambda m: str(m['image_properties'].get('total_projections', '0'))),  # CT: Number of images
            ('ct_optical_magnification', lambda m: 'yes' if str(m['machine_settings'].get('objective', '')).lower() in ['4x', '20x', '40x'] else 'no'),  # CT: Optical magnification
            ('xray_tube_voltage', lambda m: str(m['machine_settings'].get('voltage', '0.0'))),  # X-ray Tube: voltage
            ('xray_tube_power', self._calculate_xray_power),  # X-ray Tube: power (W)
            ('xray_tube_current', self._calculate_xray_current),  # Xray tube: current (uA)
            ('xray_filter', lambda m: str(m['machine_settings'].get('filter', ''))),  # X-ray: Filter
            ('detector_binning', lambda m: str(m['machine_settings'].get('binning', '0'))),  # Detector: Binning
            ('detector_capture_time', lambda m: str(m['projection_data'][0].get('exposure', '0.0')) if m.get('projection_data') else '0.0'),  # Detector: capture time (s)
            ('detector_averaging', lambda m: str(m.get('detector_info', {}).get('images_per_projection', 1))),  # Detector: Averaging (images per projection)
            ('image_width_pixels', lambda m: str(m['image_properties'].get('width', '0'))),  # Image width (pixels)
            ('image_height_pixels', lambda m: str(m['image_properties'].get('height', '0'))),  # Image height (pixels)
            ('image_width_real', lambda m: self._calculate_real_dimension(m, 'width')),  # Image width real
            ('image_height_real', lambda m: self._calculate_real_dimension(m, 'height')),  # Image height real
            ('scan_time', self._calculate_scan_time),  # Scan time
            ('start_time', lambda m: str(m['projection_data'][0].get('date', '')) if m.get('projection_data') else ''),  # Start time
            ('end_time', lambda m: str(m['projection_data'][-1].get('date', '')) if m.get('projection_data') else ''),  # End time
            ('txrm_file_path', self._get_file_path),  # TXRM File path
            ('file_path', lambda m: os.path.dirname(m.get('file_path', ''))),  # File path
            ('acquisition_successful', lambda m: str(m['basic_info'].get('initialized_correctly', 'False'))),  # Acquisition stage successful?
        ]

        # Add sample axis positions
        sample_axes = [
            ('Sample X', 'Sample_X_pos'),
            ('Sample Y', 'Sample_Y_pos'),
            ('Sample Z', 'Sample_Z_pos'),
            ('Sample Theta', 'Sample_Theta_pos'),
        ]
        
        for display_name, metadata_name in sample_axes:
            safe_name = display_name.lower().replace(' ', '_')
            column_order.extend([
                ('{0}_start'.format(safe_name), lambda m, name=metadata_name: self._get_axis_position(m, name, 0)),
                ('{0}_end'.format(safe_name), lambda m, name=metadata_name: self._get_axis_position(m, name, -1)),
                ('{0}_range'.format(safe_name), lambda m, name=metadata_name: self._calculate_axis_range_new(m, name))
            ])
        
        # Add source axis positions
        source_axes = [
            ('Source X', 'Source_X_pos'),
            ('Source Z', 'Source_Z_pos'),
        ]
        
        for display_name, metadata_name in source_axes:
            safe_name = display_name.lower().replace(' ', '_')
            column_order.extend([
                ('{0}_start'.format(safe_name), lambda m, name=metadata_name: self._get_axis_position(m, name, 0)),
                ('{0}_end'.format(safe_name), lambda m, name=metadata_name: self._get_axis_position(m, name, -1)),
                ('{0}_range'.format(safe_name), lambda m, name=metadata_name: self._calculate_axis_range_new(m, name))
            ])
        
        # Add flat panel axis positions
        flat_panel_axes = [
            ('Flat Panel Z', 'Flat_Panel_Z_pos'),
            ('Flat Panel X', 'Flat_Panel_X_pos'),
        ]
        
        for display_name, metadata_name in flat_panel_axes:
            safe_name = display_name.lower().replace(' ', '_')
            column_order.extend([
                ('{0}_start'.format(safe_name), lambda m, name=metadata_name: self._get_axis_position(m, name, 0)),
                ('{0}_end'.format(safe_name), lambda m, name=metadata_name: self._get_axis_position(m, name, -1)),
                ('{0}_range'.format(safe_name), lambda m, name=metadata_name: self._calculate_axis_range_new(m, name))
            ])
        
        # Add detector axis positions
        detector_axes = [
            ('Detector Z', 'Detector_Z_pos'),
        ]
        
        for display_name, metadata_name in detector_axes:
            safe_name = display_name.lower().replace(' ', '_')
            column_order.extend([
                ('{0}_start'.format(safe_name), lambda m, name=metadata_name: self._get_axis_position(m, name, 0)),
                ('{0}_end'.format(safe_name), lambda m, name=metadata_name: self._get_axis_position(m, name, -1)),
                ('{0}_range'.format(safe_name), lambda m, name=metadata_name: self._calculate_axis_range_new(m, name))
            ])
        
        # Add CCD axis positions (which might be the "???" in the requirements)
        ccd_axes = [
            ('CCD Z', 'CCD_Z_pos'),
            ('CCD X', 'CCD_X_pos'),
        ]
        
        for display_name, metadata_name in ccd_axes:
            safe_name = display_name.lower().replace(' ', '_')
            column_order.extend([
                ('{0}_start'.format(safe_name), lambda m, name=metadata_name: self._get_axis_position(m, name, 0)),
                ('{0}_end'.format(safe_name), lambda m, name=metadata_name: self._get_axis_position(m, name, -1)),
                ('{0}_range'.format(safe_name), lambda m, name=metadata_name: self._calculate_axis_range_new(m, name))
            ])
            
        # Add any remaining axes that might be in the data but not explicitly listed
        # This covers the "???" fields in the requirements
        other_axes = [
            ('MkIV Filter Wheel', 'MkIV_Filter_Wheel_pos'),
            ('DCT', 'DCT_pos')
        ]
        
        for display_name, metadata_name in other_axes:
            safe_name = display_name.lower().replace(' ', '_')
            column_order.extend([
                ('{0}_start'.format(safe_name), lambda m, name=metadata_name: self._get_axis_position(m, name, 0)),
                ('{0}_end'.format(safe_name), lambda m, name=metadata_name: self._get_axis_position(m, name, -1)),
                ('{0}_range'.format(safe_name), lambda m, name=metadata_name: self._calculate_axis_range_new(m, name))
            ])

        # Create output directory if it doesn't exist
        if not os.path.exists(self.output_dir):
            try:
                os.makedirs(self.output_dir)
                self.logger.info("Created output directory: %s", self.output_dir)
            except Exception as e:
                error_msg = "Error creating output directory: %s" % str(e)
                self.logger.error(error_msg)
                print(error_msg)
                return False

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = os.path.join(self.output_dir, "cumulative_metadata_{0}.csv".format(timestamp))
        
        try:
            # Prepare data with specified column order
            rows = []
            for metadata in filtered_metadata:
                row = {}
                for column_name, value_func in column_order:
                    try:
                        value = value_func(metadata)
                        # Ensure numeric values are properly formatted
                        if isinstance(value, float):
                            row[column_name] = "{0:.6f}".format(value)
                        else:
                            row[column_name] = str(value) if value is not None else ''
                    except Exception as e:
                        self.logger.warning("Error getting value for %s: %s", column_name, str(e))
                        row[column_name] = ''
                # Only add non-empty rows
                if any(row.values()):
                    rows.append(row)

            # Write to CSV with specified column order
            fieldnames = [col[0] for col in column_order]
            
            with open(csv_path, 'w') as csvfile:  # Changed from 'wb' to 'w' for better compatibility
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames, lineterminator='\n')
                writer.writeheader()
                for row in rows:
                    writer.writerow(row)
                
            self.logger.info("Cumulative metadata saved to: %s", csv_path)
            print("\nCumulative metadata saved to: {}".format(csv_path))
            return csv_path
            
        except Exception as e:
            error_msg = "Error saving cumulative CSV: %s" % str(e)
            self.logger.error(error_msg, exc_info=True)
            print(error_msg)
            return False

    def _calculate_xray_current(self, metadata):
        """Safely calculate X-ray tube current"""
        try:
            power = float(metadata['machine_settings'].get('power', 0))
            voltage = float(metadata['machine_settings'].get('voltage', 0))
            if voltage > 0:
                return str(round((power / voltage) * 100, 2))
            return ''
        except (ValueError, TypeError, ZeroDivisionError):
            return ''

    def _check_and_fix_pixel_size(self, pixel_size):
        """
        Check if the pixel size seems reasonable and fix it if not.
        Pixel size should typically be in the range of 0.5-50 μm for X-ray microscopy.
        """
        try:
            pixel_size_float = float(pixel_size)
            
            # If pixel size is unusually large (>100 μm), it might be in the wrong units
            if pixel_size_float > 100:
                self.logger.warning("Unusually large pixel size detected: %s μm. Attempting to correct.", pixel_size_float)
                # Try dividing by 1000 to convert from nm to μm if that's the issue
                corrected_size = pixel_size_float / 1000
                self.logger.info("Corrected pixel size: %s μm", corrected_size)
                return corrected_size
                
            # If pixel size is extremely small (<0.01 μm), it might be in the wrong units
            if 0 < pixel_size_float < 0.01:
                self.logger.warning("Unusually small pixel size detected: %s μm. Attempting to correct.", pixel_size_float)
                # Try multiplying by 1000 to convert from mm to μm if that's the issue
                corrected_size = pixel_size_float * 1000
                self.logger.info("Corrected pixel size: %s μm", corrected_size)
                return corrected_size
                
            return pixel_size_float
        except (ValueError, TypeError):
            return pixel_size
            
    def _calculate_real_dimension(self, metadata, dimension):
        """Calculate real dimension (pixels × pixel size)"""
        try:
            pixels = float(metadata['image_properties'].get(dimension, 0))
            raw_pixel_size = metadata['machine_settings'].get('pixel_size', 0)
            
            # Check and fix pixel size if needed
            pixel_size = self._check_and_fix_pixel_size(raw_pixel_size)
            
            # Log the values for debugging
            self.logger.debug("Calculating real dimension for %s: pixels=%s, raw_pixel_size=%s, corrected_pixel_size=%s", 
                             dimension, pixels, raw_pixel_size, pixel_size)
            
            if pixels > 0 and pixel_size > 0:
                # Real dimension = number of pixels × pixel size in μm
                real_dimension = pixels * pixel_size
                
                # Log the calculated value
                self.logger.debug("Calculated real dimension: %s μm", real_dimension)
                
                # Check if the result seems reasonable (less than 100,000 μm which is 10cm)
                if real_dimension > 100000:
                    self.logger.warning("Unusually large real dimension calculated: %s μm. Check pixel size units.", real_dimension)
                
                return str(round(real_dimension, 2))
            return ''
        except (ValueError, TypeError) as e:
            self.logger.error("Error calculating real dimension: %s", str(e))
            return ''

    def _parse_date_string(self, date_string):
        """
        Parse a date string using multiple possible formats.
        Returns a datetime object if successful, None otherwise.
        """
        if not date_string or not isinstance(date_string, str):
            return None
            
        # List of possible date formats to try
        date_formats = [
            "%m/%d/%Y %H:%M:%S.%f",  # 09/10/2022 15:17:54.773
            "%m/%d/%Y %H:%M:%S",     # 09/10/2022 15:17:54
            "%Y-%m-%d %H:%M:%S.%f",  # 2022-09-10 15:17:54.773
            "%Y-%m-%d %H:%M:%S",     # 2022-09-10 15:17:54
            "%d/%m/%Y %H:%M:%S.%f",  # 10/09/2022 15:17:54.773 (European format)
            "%d/%m/%Y %H:%M:%S"      # 10/09/2022 15:17:54 (European format)
        ]
        
        # Try each format until one works
        for date_format in date_formats:
            try:
                return datetime.strptime(date_string, date_format)
            except ValueError:
                continue
                
        # If we get here, none of the formats worked
        self.logger.error("Could not parse date string: %s", date_string)
        return None
        
    def _calculate_scan_time(self, metadata):
        """Calculate scan time (end time - start time)"""
        try:
            if not metadata.get('projection_data'):
                self.logger.warning("No projection data found for scan time calculation")
                return ''
                
            start_time = metadata['projection_data'][0].get('date')
            end_time = metadata['projection_data'][-1].get('date')
            
            # Log the raw date values for debugging
            self.logger.debug("Start time (raw): %s", start_time)
            self.logger.debug("End time (raw): %s", end_time)
            
            # If the dates are already datetime objects, use them directly
            if start_time and end_time and isinstance(start_time, datetime) and isinstance(end_time, datetime):
                time_diff = end_time - start_time
                self.logger.debug("Time difference (datetime objects): %s", time_diff)
                return str(time_diff)
                
            # If the dates are strings, parse them
            if start_time and end_time:
                # Try to parse the date strings
                start_dt = self._parse_date_string(str(start_time))
                end_dt = self._parse_date_string(str(end_time))
                
                if start_dt and end_dt:
                    self.logger.debug("Parsed start time: %s", start_dt)
                    self.logger.debug("Parsed end time: %s", end_dt)
                    
                    # Calculate the time difference
                    time_diff = end_dt - start_dt
                    
                    # Format the time difference as hours:minutes:seconds
                    total_seconds = time_diff.total_seconds()
                    hours = int(total_seconds // 3600)
                    minutes = int((total_seconds % 3600) // 60)
                    seconds = int(total_seconds % 60)
                    
                    formatted_time = "{:02d}:{:02d}:{:02d}".format(hours, minutes, seconds)
                    self.logger.debug("Formatted time difference: %s", formatted_time)
                    
                    return formatted_time
            
            self.logger.warning("Could not calculate scan time: invalid date values")
            return ''
        except (IndexError, TypeError, ValueError) as e:
            self.logger.error("Error calculating scan time: %s", str(e))
            return ''

    def _get_axis_position(self, metadata, axis_name, index):
        """Get axis position with improved precision"""
        try:
            if metadata.get('projection_data'):
                pos = metadata['projection_data'][index].get(axis_name)
                if pos is not None:
                    return "{0:.6f}".format(float(pos))
            return '0.0'
        except (KeyError, IndexError, ValueError) as e:
            self.logger.debug("Error getting position for %s: %s", axis_name, str(e))
            return '0.0'

    def _calculate_axis_range_new(self, metadata, axis_name):
        """Calculate axis range with improved precision"""
        try:
            if not metadata.get('projection_data'):
                return '0.0'
            start_pos = float(metadata['projection_data'][0].get(axis_name, 0))
            end_pos = float(metadata['projection_data'][-1].get(axis_name, 0))
            range_value = abs(end_pos - start_pos)
            return "{0:.6f}".format(range_value)
        except (ValueError, TypeError, IndexError) as e:
            self.logger.debug("Error calculating range for %s: %s", axis_name, str(e))
            return '0.0'

    def process_single_file(self, file_path):
        try:
            print("\nProcessing: {}".format(file_path))
            
            # Check if this is a drift file
            is_drift = 'drift' in os.path.basename(file_path).lower()
            if is_drift:
                self.logger.info("Processing drift file: %s", file_path)
            
            # Validate file and get hash
            valid, message, file_hash = self.validator.validate_file(file_path)
            if not valid:
                error_msg = "File validation failed: %s" % message
                self.logger.error(error_msg)
                print(error_msg)
                return False
                
            # Log file hash
            self.logger.info("File hash (SHA-256): %s", file_hash)
            
            # Get metadata
            metadata = self.metadata_extractor.get_complete_metadata(file_path)
            if not metadata:
                self.logger.error("Failed to extract metadata from file: %s", file_path)
                print("Error: Failed to extract metadata from file")
                return False
            
            # Log key metadata values for debugging
            self.logger.debug("File: %s", file_path)
            self.logger.debug("Image dimensions: %s x %s pixels", 
                             metadata['image_properties'].get('width', 'N/A'),
                             metadata['image_properties'].get('height', 'N/A'))
            self.logger.debug("Pixel size: %s μm", metadata['machine_settings'].get('pixel_size', 'N/A'))
            
            if metadata.get('projection_data'):
                self.logger.debug("First projection date: %s", metadata['projection_data'][0].get('date', 'N/A'))
                self.logger.debug("Last projection date: %s", metadata['projection_data'][-1].get('date', 'N/A'))
                
            # Add file path and hash to metadata
            metadata['file_path'] = file_path
            metadata['file_hash'] = file_hash
            metadata['validation_info'] = self.validator.get_validation_info(file_path)
            metadata['is_drift_file'] = is_drift
            
            # Save metadata as text file next to TXRM file
            if not self.save_metadata_txt(metadata, file_path):
                return False
            
            # Store metadata for cumulative CSV
            self.all_metadata.append(metadata)
            
            # Generate config file - continue even if this fails
            config_path = os.path.splitext(file_path)[0] + "_config.txt"
            try:
                if self.config_converter.create_config_from_txrm(file_path, metadata=metadata):
                    if self.config_converter.save_config(config_path):
                        self.logger.info("Configuration saved to: %s", config_path)
                    else:
                        self.logger.error("Failed to save configuration file")
                else:
                    self.logger.error("Failed to create configuration")
            except Exception as e:
                self.logger.error("Error generating config file: %s", str(e), exc_info=True)
                print("Warning: Could not generate config file, but continuing with metadata processing")
            
            return True
            
        except Exception as e:
            error_msg = "Error processing file %s: %s" % (file_path, str(e))
            self.logger.error(error_msg)
            print(error_msg)
            return False
        finally:
            gc.collect() 