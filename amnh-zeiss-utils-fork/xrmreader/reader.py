#!/usr/bin/env python
# -*- coding: utf-8 -*-

# #########################################################################
# Copyright (c) 2015, UChicago Argonne, LLC. All rights reserved.         #
#                                                                         #
# Copyright 2015. UChicago Argonne, LLC. This software was produced       #
# under U.S. Government contract DE-AC02-06CH11357 for Argonne National   #
# Laboratory (ANL), which is operated by UChicago Argonne, LLC for the    #
# U.S. Department of Energy. The U.S. Government has rights to use,       #
# reproduce, and distribute this software.  NEITHER THE GOVERNMENT NOR    #
# UChicago Argonne, LLC MAKES ANY WARRANTY, EXPRESS OR IMPLIED, OR        #
# ASSUMES ANY LIABILITY FOR THE USE OF THIS SOFTWARE.  If software is     #
# modified to produce derivative works, such modified software should     #
# be clearly marked, so as not to confuse it with the version available   #
# from ANL.                                                               #
#                                                                         #
# Additionally, redistribution and use in source and binary forms, with   #
# or without modification, are permitted provided that the following      #
# conditions are met:                                                     #
#                                                                         #
#     * Redistributions of source code must retain the above copyright    #
#       notice, this list of conditions and the following disclaimer.     #
#                                                                         #
#     * Redistributions in binary form must reproduce the above copyright #
#       notice, this list of conditions and the following disclaimer in   #
#       the documentation and/or other materials provided with the        #
#       distribution.                                                     #
#                                                                         #
#     * Neither the name of UChicago Argonne, LLC, Argonne National       #
#       Laboratory, ANL, the U.S. Government, nor the names of its        #
#       contributors may be used to endorse or promote products derived   #
#       from this software without specific prior written permission.     #
#                                                                         #
# THIS SOFTWARE IS PROVIDED BY UChicago Argonne, LLC AND CONTRIBUTORS     #
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT       #
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS       #
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL UChicago     #
# Argonne, LLC OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,        #
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,    #
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;        #
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER        #
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT      #
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN       #
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE         #
# POSSIBILITY OF SUCH DAMAGE.                                             #
# #########################################################################

"""
Module for importing data files.
"""

from __future__ import (absolute_import, division, print_function,
                       unicode_literals)

import numpy as np
import six
import os
import logging
import math
import struct
import dxchange.writer as writer
import warnings
import olefile

# original authors of dxchange
__author__ = "Doga Gursoy, Francesco De Carlo"
__copyright__ = "Copyright (c) 2015-2016, UChicago Argonne, LLC."
__version__ = "0.1.0"
__docformat__ = 'restructuredtext en'
__all__ = ['read_xrm',
           'read_xrm_stack',
           'read_txrm']

# content modified by Mareike Thies

logger = logging.getLogger(__name__)


def read_all_metadata_entries(file):
    '''

    :param file: txrm file
    :return: list of all entries in the ole metadata, but without the corresponding value
    '''
    ole = olefile.OleFileIO(file)
    entries = []
    for entry in ole.listdir():
        entries.append(entry)

    return entries


def read_metadata_byte_stream(file, entry):
    '''

    :param file: txrm file
    :param entry: one specific entry to read from the metadata, e.g. 'ImageInfo/pixelsize'
    :return: bytestream for the entry
    '''
    ole = olefile.OleFileIO(file)
    info = ole.openstream(entry)
    data = info.read()
    return data


# FIXME: raise exception would make more sense, also not sure an extension check
# is very useful, unless we are automatically mapping an extension to a
# function.
def _check_read(fname):
    known_extensions = ['.edf', '.tiff', '.tif', '.h5', '.hdf', '.npy', '.nc', '.xrm',
                        '.txrm', '.txm', '.xmt']
    if not isinstance(fname, six.string_types):
        logger.error('File name must be a string')
    else:
        if writer.get_extension(fname) not in known_extensions:
            logger.error('Unknown file extension')
    return os.path.abspath(fname)


def read_xrm(fname, slice_range=None):
    """
    Read data from xrm file.

    Parameters
    ----------
    fname : str
        String defining the path of file or file name.
    slice_range : sequence of tuples, optional
        Range of values for slicing data in each axis.
        ((start_1, end_1, step_1), ... , (start_N, end_N, step_N))
        defines slicing parameters for each axis of the data matrix.

    Returns
    -------
    ndarray
        Output 2D image.
    """
    fname = _check_read(fname)
    try:
        ole = olefile.OleFileIO(fname)
    except IOError:
        print('No such file or directory: %s', fname)
        return False

    metadata = read_ole_metadata(ole)

    if slice_range is None:
        slice_range = (slice(None), slice(None))
    else:
        slice_range = _make_slice_object_a_tuple(slice_range)

    stream = ole.openstream("ImageData1/Image1")
    data = stream.read()

    data_type = _get_ole_data_type(metadata)
    data_type = data_type.newbyteorder('<')

    arr = np.reshape(
        np.fromstring(data, data_type),
        (
            metadata["image_width"],
            metadata["image_height"]
        )
    )[slice_range]

    _log_imported_data(fname, arr)

    ole.close()
    return arr# , metadata


#  Should slc just take over what ind is doing here?
def read_xrm_stack(fname, ind, slc=None):
    """
    Read data from stack of xrm files in a folder.

    Parameters
    ----------
    fname : str
        One of the file names in the tiff stack.
    ind : list of int
        Indices of the files to read.
    slc : sequence of tuples, optional
        Range of values for slicing data in each axis.
        ((start_1, end_1, step_1), ... , (start_N, end_N, step_N))
        defines slicing parameters for each axis of the data matrix.

    Returns
    -------
    ndarray
        Output 3D image.
    """
    fname = _check_read(fname)
    list_fname = _list_file_stack(fname, ind)

    number_of_images = len(ind)
    arr, metadata = _init_ole_arr_from_stack(
        list_fname[0], number_of_images, slc)
    del metadata["thetas"][0]
    del metadata["x_positions"][0]
    del metadata["y_positions"][0]

    for m, fname in enumerate(list_fname):
        arr[m], angle_metadata = read_xrm(fname, slc)
        metadata["thetas"].append(angle_metadata["thetas"][0])
        metadata["x_positions"].append(angle_metadata["x_positions"][0])
        metadata["y_positions"].append(angle_metadata["y_positions"][0])

    _log_imported_data(fname, arr)
    return arr# , metadata


def read_txrm(file_name, slice_range=None, to_list=False):
    """
    Read data from a .txrm file, a compilation of .xrm files.

    Parameters
    ----------
    file_name : str
        String defining the path of file or file name.
    slice_range : sequence of tuples, optional
        Range of values for slicing data in each axis.
        ((start_1, end_1, step_1), ... , (start_N, end_N, step_N))
        defines slicing parameters for each axis of the data matrix.

    Returns
    -------
    ndarray
        Array of 2D images.

    dictionary
        Dictionary of metadata.
    """
    file_name = _check_read(file_name)
    try:
        ole = olefile.OleFileIO(file_name)
    except IOError:
        print('No such file or directory: %s', file_name)
        return False

    metadata = read_ole_metadata(ole)

    if to_list:
        array_of_images = []
    else:
        array_of_images = np.empty(
            _shape_after_slice(
                (
                    metadata["number_of_images"],
                    metadata["image_height"],
                    metadata["image_width"],
                ),
                slice_range
            ),
            dtype=np.float32
        )

    if slice_range is None:
        slice_range = (slice(None), slice(None), slice(None))
    else:
        slice_range = _make_slice_object_a_tuple(slice_range)

    for i, idx in enumerate(range(*slice_range[0].indices(metadata["number_of_images"]))):
        img_string = "ImageData{}/Image{}".format(
            int(np.ceil((idx + 1) / 100.0)), int(idx + 1))
        if to_list:
            array_of_images.append(_read_ole_image(ole, img_string, metadata)[slice_range[1:]])
        else:
            array_of_images[i] = _read_ole_image(ole, img_string, metadata)[slice_range[1:]]

    reference = metadata['reference']
    if reference is not None:
        metadata['reference'] = reference[slice_range[1:]]

    # _log_imported_data(file_name, array_of_images)

    ole.close()
    return array_of_images# , metadata


def read_txrm_iterable(file_name, slice_range=None):
    """
    Read data from a .txrm file, a compilation of .xrm files.

    Parameters
    ----------
    file_name : str
        String defining the path of file or file name.
    slice_range : sequence of tuples, optional
        Range of values for slicing data in each axis.
        ((start_1, end_1, step_1), ... , (start_N, end_N, step_N))
        defines slicing parameters for each axis of the data matrix.

    Returns
    -------
    ndarray
        Array of 2D images.

    dictionary
        Dictionary of metadata.
    """
    file_name = _check_read(file_name)
    try:
        ole = olefile.OleFileIO(file_name)
    except IOError:
        print('No such file or directory: %s', file_name)
        return False

    metadata = read_ole_metadata(ole)

    if slice_range is None:
        slice_range = (slice(None), slice(None), slice(None))
    else:
        slice_range = _make_slice_object_a_tuple(slice_range)

    reference = metadata['reference']
    if reference is not None:
        metadata['reference'] = reference[slice_range[1:]]

    for i, idx in enumerate(range(*slice_range[0].indices(metadata["number_of_images"]))):
        img_string = "ImageData{}/Image{}".format(
            int(np.ceil((idx + 1) / 100.0)), int(idx + 1))
        # array_of_images[i] = _read_ole_image(ole, img_string, metadata)[slice_range[1:]]
        yield _read_ole_image(ole, img_string, metadata)[slice_range[1:]]

    ole.close()


def read_metadata(file_name, slice_range=None):
    """
    Read data from a .txrm file, a compilation of .xrm files.

    Parameters
    ----------
    file_name : str
        String defining the path of file or file name.
    slice_range : sequence of tuples, optional
        Range of values for slicing data in each axis.
        ((start_1, end_1, step_1), ... , (start_N, end_N, step_N))
        defines slicing parameters for each axis of the data matrix.

    Returns
    -------
    ndarray
        Array of 2D images.

    dictionary
        Dictionary of metadata.
    """
    file_name = _check_read(file_name)
    try:
        ole = olefile.OleFileIO(file_name)
    except IOError:
        print('No such file or directory: %s', file_name)
        return False

    metadata = read_ole_metadata(ole)

    if slice_range is None:
        slice_range = (slice(None), slice(None), slice(None))
    else:
        slice_range = _make_slice_object_a_tuple(slice_range)

    reference = metadata['reference']
    if reference is not None:
        metadata['reference'] = reference[slice_range[1:]]


    ole.close()

    return metadata


def read_txm(file_name, slice_range=None):
    """
    Read data from a .txm file, the reconstruction file output
    by Zeiss software.

    Parameters
    ----------
    file_name : str
        String defining the path of file or file name.
    slice_range : sequence of tuples, optional
        Range of values for slicing data in each axis.
        ((start_1, end_1, step_1), ... , (start_N, end_N, step_N))
        defines slicing parameters for each axis of the data matrix.

    Returns
    -------
    ndarray
        Array of 2D images.

    dictionary
        Dictionary of metadata.
    """

    return read_txrm(file_name, slice_range)


def read_ole_metadata(ole):
    """
    Read metadata from an xradia OLE file (.xrm, .txrm, .txm).

    Parameters
    ----------
    ole : OleFileIO instance
        An ole file to read from.

    Returns
    -------
    tuple
        A tuple of image metadata.
    """

    number_of_images = _read_ole_value(ole, "ImageInfo/NoOfImages", "<I")
    multi_reference_found = False
    single_reference_found = False
    for entry in ole.listdir():
        if 'MultiReferenceData' in entry:
            multi_reference_found = True
        if 'ReferenceData' in entry:
            single_reference_found = True
    reference_prefix = None
    read_reference_info = True
    if single_reference_found and multi_reference_found:
        # print('\nFound both single- and multi-reference data. Using single.\n')
        reference_prefix = 'ReferenceData'
    elif single_reference_found and not multi_reference_found:
        reference_prefix = 'ReferenceData'
    elif multi_reference_found and not single_reference_found:
        # print('\nFound multi-reference data. Using mean of all reference images.\n')
        reference_prefix = 'MultiReferenceData'
    else:
        print('\nCould not find any reference data in metadata.\n')
        read_reference_info = False

    if read_reference_info:
        metadata = {
            'facility': _read_ole_value(ole, 'SampleInfo/Facility', '<50s'),
            'image_width': _read_ole_value(ole, 'ImageInfo/ImageWidth', '<I'),
            'image_height': _read_ole_value(ole, 'ImageInfo/ImageHeight', '<I'),
            'data_type': _read_ole_value(ole, 'ImageInfo/DataType', '<1I'),
            'number_of_images': number_of_images,
            'pixel_size': _read_ole_value(ole, 'ImageInfo/pixelsize', '<f'),
            # 'cam_pixel_size': _read_ole_value(ole, 'ImageInfo/CamPixelSize', '<f'),
            'reference_exposure_time': _read_ole_value(ole, reference_prefix + '/ExpTime', '<f'),
            'reference_current': _read_ole_value(ole, reference_prefix + '/XrayCurrent', '<f'),
            'reference_voltage': _read_ole_value(ole, reference_prefix + '/XrayVoltage', '<f'),
            'reference_data_type': _read_ole_value(ole, reference_prefix + '/DataType', '<1I'),
            'image_data_type': _read_ole_value(ole, 'ImageInfo/DataType', '<1I'),
            # NOTE: converting theta to radians from degrees
            'thetas': _read_ole_arr(ole, 'ImageInfo/Angles', "<{0}f".format(number_of_images)) * np.pi / 180.,
            # 'x_positions': _read_ole_arr(ole, 'ImageInfo/XPosition', "<{0}f".format(number_of_images)),
            # 'y_positions': _read_ole_arr(ole, 'ImageInfo/YPosition', "<{0}f".format(number_of_images)),
            # 'z_positions': _read_ole_arr(ole, 'ImageInfo/ZPosition', "<{0}f".format(number_of_images)),
            'x-shifts': _read_ole_arr(ole, 'alignment/x-shifts', "<{0}f".format(number_of_images)),
            'y-shifts': _read_ole_arr(ole, 'alignment/y-shifts', "<{0}f".format(number_of_images)),
            'AMC-x-shifts': _read_ole_arr(ole, 'alignment/AMCDriftXShifts', "<{0}f".format(number_of_images)),
            'AMC-y-shifts': _read_ole_arr(ole, 'alignment/AMCDriftYShifts', "<{0}f".format(number_of_images)),
            'temperature-x-shifts': _read_ole_arr(ole, 'alignment/TemperatureXShifts', "<{0}f".format(number_of_images)),
            'temperature-y-shifts': _read_ole_arr(ole, 'alignment/TemperatureYShifts', "<{0}f".format(number_of_images)),
            'source-x-shifts': _read_ole_arr(ole, 'alignment/SourceDriftXShifts', "<{0}f".format(number_of_images)),
            'source-y-shifts': _read_ole_arr(ole, 'alignment/SourceDriftYShifts', "<{0}f".format(number_of_images)),
            'align-mode': _read_ole_arr(ole, 'alignment/AlignMode', '<1I'),
            'center_shift': _read_ole_value(ole, 'ReconSettings/CenterShift', '<f'),
            'rotation_angle': _read_ole_value(ole, 'ReconSettings/RotationAngle', '<f'),
            'source_isocenter_distance': _read_ole_value(ole, 'ImageInfo/StoRADistance', "<{0}f".format(number_of_images)),
            'detector_isocenter_distance': _read_ole_value(ole, 'ImageInfo/DtoRADistance', "<{0}f".format(number_of_images)),
            'cone_angle': _read_ole_value(ole, 'ImageInfo/ConeAngle', "<{0}f".format(number_of_images)),
            'fan_angle': _read_ole_value(ole, 'ImageInfo/FanAngle', "<{0}f".format(number_of_images)),
            'camera_offset': _read_ole_value(ole, 'ImageInfo/CameraOffset', '<f'),
            'source_drift': _read_ole_value(ole, 'ImageInfo/SourceDriftTotal', '<f'),
            'current': _read_ole_value(ole, 'ImageInfo/Current', '<f'),
            'voltage': _read_ole_value(ole, 'ImageInfo/Voltage', '<f'),
            'power': _read_ole_value(ole, 'AcquisitionSettings/SrcPower', '<f'),
            'exposure_time': _read_ole_value(ole, 'AcquisitionSettings/ExpTime', '<f'),
            'binning': _read_ole_value(ole, 'AcquisitionSettings/Binning', '<I'),
            'filter': _read_ole_value(ole, 'AcquisitionSettings/SourceFilterName', '<260s'),
            'scaling_min': _read_ole_value(ole, 'GlobalMinMax/GlobalMin', '<f'),
            'scaling_max': _read_ole_value(ole, 'GlobalMinMax/GlobalMax', '<f'),
            'objective_id': _read_ole_value(ole, 'AcquisitionSettings/ObjectiveID', '<I'),
            'objective_mag': _read_ole_value(ole, 'AcquisitionSettings/ObjectiveMag', '<f')
        }
    else:
        metadata = {
            'facility': _read_ole_value(ole, 'SampleInfo/Facility', '<50s'),
            'image_width': _read_ole_value(ole, 'ImageInfo/ImageWidth', '<I'),
            'image_height': _read_ole_value(ole, 'ImageInfo/ImageHeight', '<I'),
            'data_type': _read_ole_value(ole, 'ImageInfo/DataType', '<1I'),
            'number_of_images': number_of_images,
            'pixel_size': _read_ole_value(ole, 'ImageInfo/pixelsize', '<f'),
            # 'cam_pixel_size': _read_ole_value(ole, 'ImageInfo/CamPixelSize', '<f'),
            'image_data_type': _read_ole_value(ole, 'ImageInfo/DataType', '<1I'),
            # NOTE: converting theta to radians from degrees
            'thetas': _read_ole_arr(ole, 'ImageInfo/Angles', "<{0}f".format(number_of_images)) * np.pi / 180.,
            # 'x_positions': _read_ole_arr(ole, 'ImageInfo/XPosition', "<{0}f".format(number_of_images)),
            # 'y_positions': _read_ole_arr(ole, 'ImageInfo/YPosition', "<{0}f".format(number_of_images)),
            # 'z_positions': _read_ole_arr(ole, 'ImageInfo/ZPosition', "<{0}f".format(number_of_images)),
            'x-shifts': _read_ole_arr(ole, 'alignment/x-shifts', "<{0}f".format(number_of_images)),
            'y-shifts': _read_ole_arr(ole, 'alignment/y-shifts', "<{0}f".format(number_of_images)),
            'AMC-x-shifts': _read_ole_arr(ole, 'alignment/AMCDriftXShifts', "<{0}f".format(number_of_images)),
            'AMC-y-shifts': _read_ole_arr(ole, 'alignment/AMCDriftYShifts', "<{0}f".format(number_of_images)),
            'temperature-x-shifts': _read_ole_arr(ole, 'alignment/TemperatureXShifts',
                                                  "<{0}f".format(number_of_images)),
            'temperature-y-shifts': _read_ole_arr(ole, 'alignment/TemperatureYShifts',
                                                  "<{0}f".format(number_of_images)),
            'source-x-shifts': _read_ole_arr(ole, 'alignment/SourceDriftXShifts', "<{0}f".format(number_of_images)),
            'source-y-shifts': _read_ole_arr(ole, 'alignment/SourceDriftYShifts', "<{0}f".format(number_of_images)),
            'align-mode': _read_ole_arr(ole, 'alignment/AlignMode', '<1I'),
            'center_shift': _read_ole_value(ole, 'ReconSettings/CenterShift', '<f'),
            'rotation_angle': _read_ole_value(ole, 'ReconSettings/RotationAngle', '<f'),
            'source_isocenter_distance': _read_ole_value(ole, 'ImageInfo/StoRADistance',
                                                         "<{0}f".format(number_of_images)),
            'detector_isocenter_distance': _read_ole_value(ole, 'ImageInfo/DtoRADistance',
                                                           "<{0}f".format(number_of_images)),
            'cone_angle': _read_ole_value(ole, 'ImageInfo/ConeAngle', "<{0}f".format(number_of_images)),
            'fan_angle': _read_ole_value(ole, 'ImageInfo/FanAngle', "<{0}f".format(number_of_images)),
            'camera_offset': _read_ole_value(ole, 'ImageInfo/CameraOffset', '<f'),
            'source_drift': _read_ole_value(ole, 'ImageInfo/SourceDriftTotal', '<f'),
            'current': _read_ole_value(ole, 'ImageInfo/Current', '<f'),
            'voltage': _read_ole_value(ole, 'ImageInfo/Voltage', '<f'),
            'power': _read_ole_value(ole, 'AcquisitionSettings/SrcPower', '<f'),
            'exposure_time': _read_ole_value(ole, 'AcquisitionSettings/ExpTime', '<f'),
            'binning': _read_ole_value(ole, 'AcquisitionSettings/Binning', '<I'),
            'filter': _read_ole_value(ole, 'AcquisitionSettings/SourceFilterName', '<260s'),
            'scaling_min': _read_ole_value(ole, 'GlobalMinMax/GlobalMin', '<f'),
            'scaling_max': _read_ole_value(ole, 'GlobalMinMax/GlobalMax', '<f')
        }

    try:
        metadata['filter'] = metadata['filter'].decode('utf-8').rstrip('\x00')
    except:
        print('Could not decode filter information.')
    # special case to remove trailing null characters
    reference_filename = _read_ole_value(ole, 'ImageInfo/referencefile', '<260s')
    if reference_filename is not None:
        for i in range(len(reference_filename)):
            if reference_filename[i] == '\x00':
                #null terminate
                reference_filename = reference_filename[:i]
                break
    #metadata['reference_filename'] = reference_filename
    if reference_prefix == 'ReferenceData':
        if ole.exists(reference_prefix + '/Image'):
            reference = _read_ole_image(ole, reference_prefix + '/Image', metadata, metadata['reference_data_type'])
        else:
            reference = None
    elif reference_prefix == 'MultiReferenceData':
        i = 1
        reference = []
        while ole.exists(reference_prefix + '/Image' + str(i)):
            reference.append(_read_ole_image(ole, reference_prefix + '/Image' + str(i), metadata, metadata['reference_data_type']))
            i += 1
        reference = np.array(reference)
        reference = np.mean(reference, axis=0)
    else:
        reference = None
    metadata['reference'] = reference
    return metadata


def _log_imported_data(fname, arr):
    logger.debug('Data shape & type: %s %s', arr.shape, arr.dtype)
    logger.info('Data successfully imported: %s', fname)


def _init_ole_arr_from_stack(fname, number_of_files, slc):
    """
    Initialize numpy array from files in a folder.
    """
    _arr, metadata = read_xrm(fname, slc)
    size = (number_of_files, _arr.shape[0], _arr.shape[1])
    logger.debug('Data initialized with size: %s', size)
    return np.empty(size, dtype=_arr.dtype), metadata


def _get_ole_data_type(metadata, datatype=None):
    # 10 float; 5 uint16 (unsigned 16-bit (2-byte) integers)
    if datatype is None:
        datatype = metadata["data_type"]
    if datatype == 10:
        return np.dtype(np.float32)
    elif datatype == 5:
        return np.dtype(np.uint16)
    else:
        raise Exception("Unsupport XRM datatype: %s" % str(datatype))


def _make_slice_object_a_tuple(slc):
    """
    Fix up a slc object to be tuple of slices.
    slc = None returns None
    slc is container and each element is converted into a slice object

    Parameters
    ----------
    slc : None or sequence of tuples
        Range of values for slicing data in each axis.
        ((start_1, end_1, step_1), ... , (start_N, end_N, step_N))
        defines slicing parameters for each axis of the data matrix.
    """
    if slc is None:
        return None  # need arr shape to create slice
    fixed_slc = list()
    for s in slc:
        if not isinstance(s, slice):
            # create slice object
            if s is None or isinstance(s, int):
                # slice(None) is equivalent to np.s_[:]
                # numpy will return an int when only an int is passed to
                # np.s_[]
                s = slice(s)
            else:
                s = slice(*s)
        fixed_slc.append(s)
    return tuple(fixed_slc)


def _slice_array(arr, slc):
    """
    Perform slicing on ndarray.

    Parameters
    ----------
    arr : ndarray
        Input array to be sliced.
    slc : sequence of tuples
        Range of values for slicing data in each axis.
        ((start_1, end_1, step_1), ... , (start_N, end_N, step_N))
        defines slicing parameters for each axis of the data matrix.

    Returns
    -------
    ndarray
        Sliced array.
    """
    if slc is None:
        logger.debug('No slicing applied to image')
        return arr[:]
    axis_slice = _make_slice_object_a_tuple(slc)
    logger.debug('Data sliced according to: %s', axis_slice)
    return arr[axis_slice]


def _shape_after_slice(shape, slc):
    """
    Return the calculated shape of an array after it has been sliced.
    Only handles basic slicing (not advanced slicing).

    Parameters
    ----------
    shape : tuple of ints
        Tuple of ints defining the ndarray shape
    slc : tuple of slices
        Object representing a slice on the array.  Should be one slice per
        dimension in shape.

    """
    if slc is None:
        return shape
    new_shape = list(shape)
    slc = _make_slice_object_a_tuple(slc)
    for m, s in enumerate(slc):
        # indicies will perform wrapping and such for the shape
        start, stop, step = s.indices(shape[m])
        new_shape[m] = int(math.ceil((stop - start) / float(step)))
        if new_shape[m] < 0:
            new_shape[m] = 0
    return tuple(new_shape)


def _list_file_stack(fname, ind, digit=None):
    """
    Return a stack of file names in a folder as a list.

    Parameters
    ----------
    fname : str
        String defining the path of file or file name.
    ind : list of int
        Indices of the files to read.
    digit : int
        Deprecated input for the number of digits in all indexes
        of the stacked files.
    """

    if digit is not None:
        warnings.warn(("The 'digit' argument is deprecated and no longer used."
                      "  It may be removed completely in a later version."),
                      FutureWarning)

    body = writer.get_body(fname)
    body, digits = writer.remove_trailing_digits(body)

    ext = writer.get_extension(fname)
    list_fname = []
    for m in ind:
        counter_string = str(m).zfill(digits)
        list_fname.append(body + counter_string + ext)
    return list_fname


def _read_ole_struct(ole, label, struct_fmt):
    """
    Reads the struct associated with label in an ole file
    """
    value = None
    if ole.exists(label):
        stream = ole.openstream(label)
        data = stream.read()
        value = struct.unpack(struct_fmt, data)
    return value


def _read_ole_value(ole, label, struct_fmt):
    """
    Reads the value associated with label in an ole file
    """
    value = _read_ole_struct(ole, label, struct_fmt)
    if value is not None:
        value = value[0]
    return value


def _read_ole_arr(ole, label, struct_fmt):
    """
    Reads the numpy array associated with label in an ole file
    """
    arr = _read_ole_struct(ole, label, struct_fmt)
    if arr is not None:
        arr = np.array(arr)
    return arr


def _read_ole_image(ole, label, metadata, datatype=None):
    stream = ole.openstream(label)
    data = stream.read()
    data_type = _get_ole_data_type(metadata, datatype)
    data_type = data_type.newbyteorder('<')
    image = np.reshape(
        np.fromstring(data, data_type),
        (metadata["image_height"], metadata["image_width"], )
    )
    return image


def read_amc_images(file_name, slice_range=None, to_list=False):
    file_name = _check_read(file_name)
    try:
        ole = olefile.OleFileIO(file_name)
    except IOError:
        print('No such file or directory: %s', file_name)
        return False

    metadata = read_ole_metadata(ole)

    if to_list:
        array_of_images = []
    else:
        array_of_images = np.empty(
            _shape_after_slice(
                (
                    21,
                    metadata["image_height"],
                    metadata["image_width"],
                ),
                slice_range
            ),
            dtype=np.float32
        )

    if slice_range is None:
        slice_range = (slice(None), slice(None), slice(None))
    else:
        slice_range = _make_slice_object_a_tuple(slice_range)

    for i, idx in enumerate(range(*slice_range[0].indices(21))):
        img_string = "AMC/ImageData1/Image{}".format(int(idx + 1))
        if to_list:
            array_of_images.append(_read_ole_image(ole, img_string, metadata)[slice_range[1:]])
        else:
            array_of_images[i] = _read_ole_image(ole, img_string, metadata)[slice_range[1:]]

    ole.close()

    return array_of_images
