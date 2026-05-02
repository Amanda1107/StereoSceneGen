import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
# ================= 1. 基础配置 =================
base_depth_dir = "./output_depths/"

if not os.path.exists(base_depth_dir):
    print(f"找不到输入目录 {base_depth_dir}，请确认已经提取了深度矩阵！")
    exit()

# 获取所有场景的深度文件夹
scenario_folders = [f for f in os.listdir(base_depth_dir) if os.path.isdir(os.path.join(base_depth_dir, f))]

print(f"共找到 {len(scenario_folders)} 个场景深度目录: {scenario_folders}")

for scenario in scenario_folders:
    scenario_path = os.path.join(base_depth_dir, scenario)
    
    # 获取当前场景下的所有 .npy 文件
    npy_files = [f for f in os.listdir(scenario_path) if f.endswith(".npy")]
    
    if not npy_files:
        continue
        
    print(f"\n" + "="*50)
    print(f"开始处理场景: {scenario}")
    print("="*50)
    
    # 开始遍历当前场景的每一帧深度图
    for npy_file in npy_files:
        npy_path = os.path.join(scenario_path, npy_file)
        
        # ================= 2. 加载与分析数据 =================
        depth_matrix = np.load(npy_path)
        
        # 过滤掉无穷大(inf)和异常大数值(如 1.45e10)，假设有效距离 < 1000米
        valid_depths = depth_matrix[(depth_matrix < 1000) & (~np.isinf(depth_matrix))]
        
        if len(valid_depths) > 0:
            min_depth = np.min(valid_depths)
            max_depth = np.max(valid_depths)
            print(f"   处理 {npy_file} -> 最近: {min_depth:.2f}m | 最远: {max_depth:.2f}m")
        else:
            print(f"   警告: {npy_file} 中没有找到有效的物理深度数据！")
            continue
            
        # ================= 3. 数据可视化预处理 (对数映射) =================
        print("正在生成对数映射(LogNorm)高动态深度图...")
        
        depth_matrix_visual = np.copy(depth_matrix)
        
        if len(valid_depths) > 0:
            # 动态下限：取 1%，但为了使用对数计算，必须保证绝对大于 0 (这里保底 0.1米)
            min_visual_distance = max(np.percentile(valid_depths, 1), 0.1)
            
            # 动态上限：取 99% 包含几乎所有深巷子的远景
            max_visual_distance = np.percentile(valid_depths, 99) 
        else:
            min_visual_distance = 0.1
            max_visual_distance = 50.0 
            
        # 将天空 (inf 或 异常大值) 强行涂成背景色极限值
        depth_matrix_visual[(np.isinf(depth_matrix_visual)) | (depth_matrix_visual > 1000)] = max_visual_distance
        depth_matrix_visual = np.clip(depth_matrix_visual, min_visual_distance, max_visual_distance)

        # ================= 4. 开始画图并保存 =================
        plt.figure(figsize=(10, 8))
        
        # 使用 LogNorm 进行对数映射
        plt.imshow(depth_matrix_visual, cmap='plasma', 
                   norm=mcolors.LogNorm(vmin=min_visual_distance, vmax=max_visual_distance)) 
                   
        plt.colorbar(label='Distance (Meters) - Log Scale')
        plt.title(f"{scenario} - Frame: {npy_file}\n(Log Scale: {min_visual_distance:.1f}m to {max_visual_distance:.1f}m)")

        output_img_name = npy_file.replace(".npy", "_vis.png")
        output_img_path = os.path.join(scenario_path, output_img_name)
        
        plt.savefig(output_img_path, dpi=300, bbox_inches='tight')
        plt.close()

        
    print(f"{scenario} 下的所有深度图可视化完毕！")

print("\n" + "="*15)
print("所有场景的深度图均已自动渲染为彩色图像！")
print(f"请前往 {base_depth_dir} 的各个子文件夹下查看带 '_vis' 后缀的图片。")