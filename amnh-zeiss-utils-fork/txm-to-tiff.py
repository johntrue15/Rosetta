#!/bin/env python

'''
txm-to-tiff.py

Convert Zeiss txm metadata to NRRD format.

By Hollister Herhold, AMNH, 2025. I used github copilot for much of the boilerplate code.

'''

import argparse
from traitlets import default
import xrmreader
import tifffile
import os
from tqdm import tqdm

# Handle command line arguments.
parser = argparse.ArgumentParser(description="Convert reconstructed Zeiss txm to TIFF format.")

parser.add_argument("-i", "--input-txm-file", help="Input Zeiss txm file", 
                    required=True)
parser.add_argument("-p", "--prefix", help="Filename prefix for output TIFF files",
                    default=None, required=False)
parser.add_argument("-o", "--output-dir", help="Output directory for TIFF files",
                    default="TIFF", required=False)
parser.add_argument("-v", "--verbose", help="Enable verbose output",
                    action="store_true", default=False)

args = parser.parse_args()

def main():
    # Read the txm file using xrmreader. Failure to find the file results in
    # read_txm() just returning False.
    print("Reading input file...", end='', flush=True)
    scan_volume = xrmreader.read_txm(args.input_txm_file)
    if scan_volume is False:
        print(f"Error: Could not read input file {args.input_txm_file}. Exiting.")
        return
    print("done.")
 
    # Strip the file extension from the input file name to create a prefix for 
    # output TIFF files. If a prefix is provided, use that instead.
    output_tiff_prefix = args.input_txm_file.rsplit('.', 1)[0]
    if args.prefix:
        output_tiff_prefix = args.prefix

    # Print out the shape of the scan volume.
    if args.verbose:
        print(f"Scan volume shape: {scan_volume.shape}")

    print("Saving slices as TIFF files.")

    # Create the output directory if it does not exist.
    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)

    num_slices = scan_volume.shape[0]

    for i in tqdm(range(num_slices)):
        slice_i = scan_volume[i, :, :].astype('uint16')
        filename = f"{args.output_dir}/{output_tiff_prefix}{i:04d}.tiff"
        tifffile.imwrite(filename, slice_i)

if __name__ == "__main__":
    main()
