#!/bin/env python

'''

get-metadata-from-txrm.py

Extract metadata from a Zeiss txrm file.

By Hollister Herhold, AMNH, 2025. I used github copilot for much of the boilerplate code.

'''

import argparse
import xrmreader

# Handle command line arguments.

parser = argparse.ArgumentParser(description="Extract metadata from a Zeiss txrm file.")

parser.add_argument("-i", "--input-txrm-file", help="Input Zeiss txrm file", 
                    required=True)
parser.add_argument("-o", "--output-file", help="Output file to save metadata", 
                    required=False, default=None)
parser.add_argument("-v", "--verbose", help="Enable verbose output",
                    action="store_true", default=False)
parser.add_argument("-f", "--fields", help="Comma-separated list of fields to extract",
                    required=False, default=None)
parser.add_argument("-a", "--all", help="Extract all available metadata fields",
                    action="store_true", default=False)


args = parser.parse_args()

# The list of fields to grab by default. This can be extended as needed. You also
# can grab any fields by specifying them in the command line arguments. Using the
# -f/--fields option, you can provide a comma-separated list of fields to extract.
default_fields = [
    'image_width', 'image_height', 'data_type', 'number_of_images',
    'pixel_size', 'reference_exposure_time', 'reference_current',
    'reference_voltage', 'reference_data_type', 'image_data_type',
    'align-mode', 'center_shift', 'rotation_angle',
    'source_isocenter_distance', 'detector_isocenter_distance', 'cone_angle',
    'fan_angle', 'camera_offset', 'source_drift', 'current', 'voltage',
    'power', 'exposure_time', 'binning', 'filter', 
    'scaling_min', 'scaling_max', 'objective_id', 'objective_mag'
]

# Objective ID
# 3 = 4X
# 5 = 20X

def get_field_from_metadata(metadata, field_name):
    """
    Get a specific field from the metadata dictionary.
    
    :param metadata: Dictionary containing metadata fields.
    :param field_name: Name of the field to retrieve.
    :return: Value of the specified field or None if not found.
    """
    return metadata.get(field_name, None)

def print_all_available_fields(metadata):
    print("Available metadata fields:")
    for key in metadata.keys():
        print(f"{key}: {metadata[key]}")

def print_selected_fields(metadata, fields):
    print("Selected metadata fields:")
    for field in fields:
        value = get_field_from_metadata(metadata, field)
        if value is not None:
            print(f"{field}: {value}")
        else:
            print(f"{field}: Not found in metadata")

def main():
    if args.verbose:
        print("Verbose mode enabled.")
        print("Input file:", args.input_txrm_file)
        if args.output_file:
            print("Output file:", args.output_file)

    #metadata_entries = xrmreader.read_all_metadata_entries(args.input_txrm_file)

    metadata = xrmreader.read_metadata(args.input_txrm_file)

    if args.verbose:
        print("Metadata read successfully.")

    if args.all:
        print_all_available_fields(metadata)
        return

    if args.fields:
        fields = [field.strip() for field in args.fields.split(',')]
    else:
        fields = default_fields

    print_selected_fields(metadata, fields)

if __name__ == "__main__":
    main()
