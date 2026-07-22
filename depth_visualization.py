import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
base_depth_dir = PROJECT_ROOT / "output_depths"

if not base_depth_dir.exists():
    print(f"Input directory not found: {base_depth_dir}. Extract the depth arrays first.")
    exit()

scenario_folders = sorted(path for path in base_depth_dir.iterdir() if path.is_dir())

print(f"Found {len(scenario_folders)} scene depth directories: {[path.name for path in scenario_folders]}")

for scenario_path in scenario_folders:
    scenario = scenario_path.name
    
    npy_files = sorted(path for path in scenario_path.iterdir() if path.suffix == ".npy")
    
    if not npy_files:
        continue
        
    print(f"\n" + "="*50)
    print(f"Processing scene: {scenario}")
    print("="*50)
    
    for npy_path in npy_files:
        npy_file = npy_path.name

        depth_matrix = np.load(npy_path)

        # Ignore infinite values and distances outside the supported range.
        valid_depths = depth_matrix[(depth_matrix < 1000) & (~np.isinf(depth_matrix))]
        
        if len(valid_depths) > 0:
            min_depth = np.min(valid_depths)
            max_depth = np.max(valid_depths)
            print(f"   Processing {npy_file} -> nearest: {min_depth:.2f} m | farthest: {max_depth:.2f} m")
        else:
            print(f"   Warning: no valid physical depth data found in {npy_file}.")
            continue
            
        print("Generating a high-dynamic-range depth image with LogNorm...")
        
        depth_matrix_visual = np.copy(depth_matrix)
        
        if len(valid_depths) > 0:
            # Percentile limits reduce the influence of depth outliers.
            min_visual_distance = max(np.percentile(valid_depths, 1), 0.1)
            max_visual_distance = np.percentile(valid_depths, 99) 
        else:
            min_visual_distance = 0.1
            max_visual_distance = 50.0 
            
        depth_matrix_visual[(np.isinf(depth_matrix_visual)) | (depth_matrix_visual > 1000)] = max_visual_distance
        depth_matrix_visual = np.clip(depth_matrix_visual, min_visual_distance, max_visual_distance)

        plt.figure(figsize=(10, 8))

        plt.imshow(depth_matrix_visual, cmap='plasma', 
                   norm=mcolors.LogNorm(vmin=min_visual_distance, vmax=max_visual_distance)) 
                   
        plt.colorbar(label='Distance (Meters) - Log Scale')
        plt.title(f"{scenario} - Frame: {npy_file}\n(Log Scale: {min_visual_distance:.1f}m to {max_visual_distance:.1f}m)")

        output_img_name = npy_file.replace(".npy", "_vis.png")
        output_img_path = scenario_path / output_img_name
        
        plt.savefig(output_img_path, dpi=300, bbox_inches='tight')
        plt.close()

        
    print(f"Depth visualization completed for scene: {scenario}")

print("\n" + "="*15)
print("Depth visualization completed for all scenes.")
print(f"View images with the '_vis' suffix in each subdirectory of {base_depth_dir}.")
