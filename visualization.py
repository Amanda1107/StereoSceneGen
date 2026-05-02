import os
import h5py
import numpy as np

from utils.io_utils import create_folder_if_not_exists, return_folder_file_list
from utils.vis_utils import convert_hdf5_to_image

# ================= 基础配置 =================
base_input_dir = "./output/"
base_rgb_output_dir = "./output_colors/"   # 存放 RGB 的主目录
base_depth_output_dir = "./output_depths/" # 存放 Depth 的主目录 (新增)
# ============================================

if not os.path.exists(base_input_dir):
    print(f"找不到输入目录 {base_input_dir}，请确认 BlenderProc 已经跑完并生成了数据！")
    exit()

# 自动获取 ./output/ 下的所有场景文件夹
scenario_folders = [f for f in os.listdir(base_input_dir) if os.path.isdir(os.path.join(base_input_dir, f))]
print(f"共找到 {len(scenario_folders)} 个场景目录需要提取: {scenario_folders}")

for scenario_name in scenario_folders:
    print(f"\n" + "="*50)
    print(f"开始提取场景: {scenario_name} 的 RGB-D 数据对")
    print("="*50)

    # 1. 路径拼接
    hdf5_folder = os.path.join(base_input_dir, scenario_name)
    color_output_folder = os.path.join(base_rgb_output_dir, f"{scenario_name}_rgb")
    depth_output_folder = os.path.join(base_depth_output_dir, f"{scenario_name}_depth") # 新增深度图文件夹
    
    # 2. 确保输出文件夹存在
    create_folder_if_not_exists(color_output_folder)
    create_folder_if_not_exists(depth_output_folder)
    
    # 3. 获取并过滤 .hdf5 文件
    hdf5_file_list = return_folder_file_list(hdf5_folder)
    hdf5_file_list = [f for f in hdf5_file_list if f.endswith(".hdf5")]

    if not hdf5_file_list:
        print(f"在 {hdf5_folder} 中没有找到 .hdf5 文件，跳过当前场景...")
        continue

    # 4. 开始批量提取
    for hdf5_file_name in hdf5_file_list:
        print(f"   正在处理 {hdf5_file_name}...")
        
        hdf5_file_path = os.path.join(hdf5_folder, hdf5_file_name)
        
        # --- 提取 RGB 全彩图 ---
        rgb_image_path = os.path.join(color_output_folder, hdf5_file_name.replace(".hdf5", ".png"))
        convert_hdf5_to_image(hdf5_file_path, "colors", rgb_image_path)
        
        # --- 提取 Depth 深度图 (新增逻辑) ---
        depth_npy_path = os.path.join(depth_output_folder, hdf5_file_name.replace(".hdf5", ".npy"))
        
        try:
            # 打开 HDF5 文件读取深度矩阵
            with h5py.File(hdf5_file_path, 'r') as f:
                if 'distance' in f.keys():
                    depth_array = np.array(f['distance'])
                    # 将深度矩阵保存为 .npy 文件，供 PyTorch/深度学习网络直接读取
                    np.save(depth_npy_path, depth_array)
                else:
                    print(f"      [警告] {hdf5_file_name} 中没有找到 'distance' 通道！请检查渲染脚本是否开启了深度渲染。")
        except Exception as e:
            print(f"      [错误] 读取深度图失败: {e}")
            
    print(f"{scenario_name} 转换完毕！")
    print(f"   - RGB 已保存至: {color_output_folder}")
    print(f"   - Depth 已保存至: {depth_output_folder}")

print("\n" + "="*10)
print("所有场景的 RGB-D 数据对已全部提取完成！")