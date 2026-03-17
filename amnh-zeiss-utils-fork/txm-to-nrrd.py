#!/bin/env python

'''
txm-to-nrrd.py

Convert Zeiss txm metadata to NRRD format.

By Hollister Herhold, AMNH, 2025. I used github copilot for much of the boilerplate code.

'''

import argparse
import xrmreader
import nrrd

# Handle command line arguments.
parser = argparse.ArgumentParser(description="Convert reconstructed Zeiss txm to NRRD format.")

parser.add_argument("-i", "--input-txm-file", help="Input Zeiss txm file", 
                    required=True)
parser.add_argument("-o", "--output-nrrd-file", help="Output NRRD file to save data", 
                    required=True)
parser.add_argument("-v", "--verbose", help="Enable verbose output",
                    action="store_true", default=False)

args = parser.parse_args()

def main():
    # Read the txm file using xrmreader
    scan_volume = xrmreader.read_txm(args.input_txm_file)
    if scan_volume is False:
        print(f"Error: Could not read input file {args.input_txm_file}. Exiting.")
        return
    
    # Change the data type to 16 bit unsigned integers.
    scan_volume = scan_volume.astype('uint16')

    # Print out the shape of the scan volume.
    if args.verbose:
        print(f"Scan volume shape: {scan_volume.shape}")

    # Convert the scan volume to NRRD format and save it.
    nrrd.write(args.output_nrrd_file, scan_volume, compression_level=1, index_order='C')

if __name__ == "__main__":
    main()
