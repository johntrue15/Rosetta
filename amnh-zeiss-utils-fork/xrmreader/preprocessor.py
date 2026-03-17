import numpy as np
from xrmreader.reader import read_txrm_iterable, read_metadata
# from reader import read_txrm_iterable, read_metadata
from scipy.ndimage import shift, convolve
from tqdm import tqdm
from skimage.measure import block_reduce
from skimage.transform.pyramids import pyramid_reduce


def divide_by_reference(projections, reference):
    '''Homogenizes the background using a reference projection without object.

    :param projections: projections
    :param reference: reference projection
    :return:
    '''
    projections = np.divide(projections, reference)
    return projections


def revert_shifts(projections, x_shifts, y_shifts):
    '''

    :param projections: projection data
    :param x_shifts: x shift parameter per projection
    :param y_shifts: y shift parameter per projection
    :return: shift corrected porjections
    '''
    num_projections, img_size_x, img_size_y = projections.shape
    shifts = np.zeros((num_projections, 2))
    shifts[:, 0] = x_shifts
    shifts[:, 1] = y_shifts

    # shift each projection
    for i in range(num_projections):
        # input is extended by repeating its last value to avoid zeros after cropping
        projections[i, :, :] = shift(projections[i, :, :], (shifts[i, 1], shifts[i, 0]), order=1, mode='nearest')

    return projections


def negative_logarithm(sinogram, epsilon=0.0001):
    ''' Conversion of sinogram to line integral domain.
    Needs to be done after shift correction.
    Type conversion to float might cause memory issues.

    :param epsilon: small number to make sure no zero or negative value occurs
    :param sinogram: sinogram as measured on detector
    :return: sinogram in line integral domain
    '''
    if (sinogram <= 0).any():
        sinogram[sinogram <= 0] = epsilon
    np.log(sinogram, out=sinogram)
    sinogram *= -1
    return sinogram


def downsample(projections, spatial_factor: int, angular_factor: int):
    '''

    :param projections: projections
    :param spatial_factor: factor for spatial downsampling
    :param angular_factor: factor used to use less projections in angular direction
    :return: downsampled projections
    '''
    # using only every n-th projection (averaging in this direction does not make sense)
    projections = projections[::angular_factor, :, :]

    # rather than leaving out every n-th value, compute the mean value over a fixed sized window for reduction
    # projections = block_reduce(projections, block_size=(1, spatial_factor, spatial_factor), func=np.mean)
    if spatial_factor > 1:
        # note: keyword channel_axis was introduced in scikit image 0.19; code breaks from that version on if left
        # unspecified
        projections = pyramid_reduce(projections, downscale=spatial_factor, preserve_range=True, channel_axis=0)

    return projections


def truncation_correction(projections, extension_fraction=0.1):
    ''' Truncation correction on left/right detector side. Avoid bright rim at outer reco area.

    :param projections: projections
    :param extension_fraction: faction of image width to be added to both sides
    :return: extended projections
    '''
    # todo: use simple numpy solution or implement https://pubmed.ncbi.nlm.nih.gov/10659736/ ??
    num_images, img_height, img_width = projections.shape
    n_ext = int(img_width * extension_fraction)
    projection = np.pad(projections, pad_width=((0, 0), (0, 0), (n_ext, n_ext)), mode='symmetric')
    ramp = np.linspace(0, 1, n_ext, endpoint=True)
    projection[:, :, :n_ext] *= ramp
    projection[:, :, -n_ext:] *= ramp[::-1]
    return projection


def insert_quantum_noise(p_A, p_air, p_air_smooth, a=1.):
    '''Simulates quantum noise following eq. (6) and (8) from "Lifeng Yu - Development and Validation of a Practical
    Lower-Dose-Simulation Tool for Optimizing Computed Tomography Scan Protocols".

    :param p_A: projection image with object
    :param p_air: reference image without object to calculate N_0A
    :param p_air_smooth: smoothed reference projection to properly calculate the quantum noise
    :param a: N_0B = a * N_0A, i.e. "dose(P_B)/dose(P_A)" 0 < a <= 1
    :return: Image with inserted quantum noise P_B
    '''
    if a == 1.:
        return p_A
    else:
        p_air = np.array(p_air)
        p_air_norm = p_air / p_air_smooth
        p_air_log = -1 * np.log(p_air_norm)

        mu = 0
        sigma = 1
        x = np.random.normal(mu, sigma, np.shape(p_A))
        n_0A = 1 / np.var(np.exp(-p_air_log))
        p_B = p_A + np.sqrt(((1-a) / a) * (np.exp(p_A) / n_0A)) * x
        return p_B


def smooth_reference(reference, kernel_size=15):
    '''Smooth the reference projection with a large kernel to receive the global intensity distribution of the incident
    beam. Pretty long runtime, so just do this once.

    :param reference: reference projection
    :param kernel_size: kernel size
    :return: Smoothed reference image
    '''
    reference = np.array(reference)
    kernel = np.ones((kernel_size, kernel_size)) / np.sum(np.ones((kernel_size, kernel_size)))
    reference_smooth = convolve(reference, kernel, mode='reflect')
    return reference_smooth


def apply_polynomial(data, coefficients):
    degree = len(coefficients)
    out = np.zeros_like(data)
    for i in range(degree):
        out = out + coefficients[i] * np.power(data, i + 1)
    return out


def read_and_preprocess_txrm(projections_file, downsample_factor=1, angular_factor=1, do_truncation_correction=True,
                             extension_fraction=0.1, dose_reduction=1., datatype=np.float32, keep_rows=None,
                             do_beam_hardening_correction=False, poly=None, do_shift=True):
    '''Preprocess the raw images, i.e. remove shifts, transform into line integral domain.
    Projections are extended for truncation correction if needed.

    :param keep_rows: bool type array of same length as image height indicating which detector rows to keep
    :param dose_reduction: determines the dose relative to the high dose acquisition -> Poisson noise is inserted
    :param projections_file: Path to txrm projection file, images are loaded on-the-fly to avoid high memory consumption
    :param downsample_factor: factor by which the projections are downsampled spatially; 1 means no downsampling
    :param angular_factor: factor by which the number of projections is downsampled; 1 means no downsampling
    :param do_truncation_correction: whether or not truncation corrections should be applied to the projections
    :param extension_fraction: if truncation correction is applied -> which fraction of original image width is appended
    to both sides of the image
    :param datatype: numpy datatype to use for storing the projections; should be one of float16, float32, float64
    :param do_beam_hardening_correction: whether or not polynomial beam hardening correction is applied
    :param poly: coefficients for beam hardening correction
    :param do_shift: if shift correction should be performed while loading the projections or in the projection images
    :return:
    '''
    metadata = read_metadata(str(projections_file))
    num_images = metadata['number_of_images']
    x_shifts = metadata['x-shifts'][::angular_factor]
    y_shifts = metadata['y-shifts'][::angular_factor]
    reference = metadata['reference']
    if not dose_reduction == 1.:
        reference_smooth = smooth_reference(reference)
    if keep_rows is not None:
        keep_rows = keep_rows.astype(bool)
        projection_height = int(np.ceil(np.sum(keep_rows) / downsample_factor))
    else:
        projection_height = int(np.ceil(float(metadata['image_height']) / downsample_factor))
    if do_truncation_correction:
        projections = np.zeros((int(np.ceil(num_images / angular_factor)),
                                projection_height,
                                int(np.ceil(float(metadata['image_width']) / downsample_factor)) + 2 * int(
                                    np.ceil(float(metadata['image_width']) / downsample_factor) * extension_fraction)),
                               dtype=datatype)
    else:
        projections = np.zeros((int(np.ceil(num_images / angular_factor)),
                                projection_height,
                                int(np.ceil(float(metadata['image_width']) / downsample_factor))),
                               dtype=datatype)

    # todo: can this loop be parallelized without further memory consumption?
    for i, (projection, x_shift, y_shift) in tqdm(enumerate(
            zip(read_txrm_iterable(str(projections_file), slice_range=(
            (0, num_images, angular_factor), (0, metadata['image_height'], 1), (0, metadata['image_width'], 1))),
                x_shifts, y_shifts)), total=np.ceil(num_images / angular_factor)):
        projection = np.expand_dims(projection, 0)
        projection = divide_by_reference(projection, reference)
        if do_shift:
            projection = revert_shifts(projection, x_shift, y_shift)
        if keep_rows is not None:
            projection = projection[:, keep_rows, :]
        projection = negative_logarithm(projection)
        if not dose_reduction == 1.:
            projection = insert_quantum_noise(projection, reference, reference_smooth, dose_reduction)
        if downsample_factor != 1 or angular_factor != 1:
            projection = downsample(projection, downsample_factor, angular_factor)
        if do_truncation_correction:
            projection = truncation_correction(projection, extension_fraction=extension_fraction)
        if do_beam_hardening_correction:
            projection = apply_polynomial(projection, poly)
        projections[i, :, :] = np.squeeze(projection)

    return projections


def read_single_projection(projections_file, downsample_factor=1, angular_factor=1, do_truncation_correction=True,
                             extension_fraction=0.1, dose_reduction=1., datatype=np.float32, keep_rows=None,
                             do_beam_hardening_correction=False, poly=None):
    metadata = read_metadata(str(projections_file))
    reference = metadata['reference']
    if not dose_reduction == 1.:
        reference_smooth = smooth_reference(reference)
    if keep_rows is not None:
        keep_rows = keep_rows.astype(bool)
    for projection in read_txrm_iterable(str(projections_file)):
        projection = np.expand_dims(projection, 0)
        projection = divide_by_reference(projection, reference)
        if keep_rows is not None:
            projection = projection[:, keep_rows, :]
        projection = negative_logarithm(projection)
        if not dose_reduction == 1.:
            projection = insert_quantum_noise(projection, reference, reference_smooth, dose_reduction)
        if downsample_factor != 1 or angular_factor != 1:
            projection = downsample(projection, downsample_factor, angular_factor)
        if do_truncation_correction:
            projection = truncation_correction(projection, extension_fraction=extension_fraction)
        if do_beam_hardening_correction:
            projection = apply_polynomial(projection, poly)
        break

    return projection
