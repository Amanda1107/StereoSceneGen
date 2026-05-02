import h5py
import numpy as np
import matplotlib.pyplot as plt
from utils.io_utils import create_folder_if_not_exists, save_numpy_array_as_image

def convert_hdf5_to_image(hdf5_file, key, output_file_name):
    with h5py.File(hdf5_file, "r") as f:
        # get the object type for a_group_key: usually group or dataset
        img_np =  f[key][()]
        save_numpy_array_as_image(img_np, output_file_name)