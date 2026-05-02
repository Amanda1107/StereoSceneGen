import os
import matplotlib.pyplot as plt

def create_folder_if_not_exists(folder_path):
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

def return_folder_file_list(folder_path):
    file_path_list = os.listdir(folder_path)
    if '.DS_Store' in file_path_list:
        file_path_list.remove('.DS_Store')
    return sorted(file_path_list)

def save_numpy_array_as_image(array, filename):
    plt.imsave(filename, array)