import h5py
import numpy as np
from pathlib import Path

from utils.io_utils import create_folder_if_not_exists, return_folder_file_list
from utils.vis_utils import convert_hdf5_to_image

PROJECT_ROOT = Path(__file__).resolve().parent
base_input_dir = PROJECT_ROOT / "output"
base_rgb_output_dir = PROJECT_ROOT / "output_colors"
base_depth_output_dir = PROJECT_ROOT / "output_depths"

if not base_input_dir.exists():
    print(f"Input directory not found: {base_input_dir}. Run BlenderProc first to generate data.")
    exit()

scenario_folders = sorted(path.name for path in base_input_dir.iterdir() if path.is_dir())
print(f"Found {len(scenario_folders)} scene directories to extract: {scenario_folders}")

for scenario_name in scenario_folders:
    print(f"\n" + "="*50)
    print(f"Extracting RGB-D data for scene: {scenario_name}")
    print("="*50)

    hdf5_folder = base_input_dir / scenario_name
    color_output_folder = base_rgb_output_dir / f"{scenario_name}_rgb"
    depth_output_folder = base_depth_output_dir / f"{scenario_name}_depth"
    
    create_folder_if_not_exists(color_output_folder)
    create_folder_if_not_exists(depth_output_folder)
    
    hdf5_file_list = return_folder_file_list(hdf5_folder)
    hdf5_file_list = [f for f in hdf5_file_list if f.endswith(".hdf5")]

    if not hdf5_file_list:
        print(f"No .hdf5 files found in {hdf5_folder}; skipping this scene.")
        continue

    for hdf5_file_name in hdf5_file_list:
        print(f"   Processing {hdf5_file_name}...")
        
        hdf5_file_path = hdf5_folder / hdf5_file_name
        
        rgb_image_path = color_output_folder / hdf5_file_name.replace(".hdf5", ".png")
        convert_hdf5_to_image(hdf5_file_path, "colors", rgb_image_path)
        
        depth_npy_path = depth_output_folder / hdf5_file_name.replace(".hdf5", ".npy")
        
        try:
            with h5py.File(hdf5_file_path, 'r') as f:
                if 'distance' in f.keys():
                    depth_array = np.array(f['distance'])
                    np.save(depth_npy_path, depth_array)
                else:
                    print(f"      [Warning] No 'distance' channel found in {hdf5_file_name}. Check that distance output is enabled.")
        except Exception as e:
            print(f"      [Error] Failed to read depth data: {e}")
            
    print(f"Finished converting {scenario_name}.")
    print(f"   - RGB saved to: {color_output_folder}")
    print(f"   - Depth saved to: {depth_output_folder}")

print("\n" + "="*10)
print("RGB-D extraction completed for all scenes.")
