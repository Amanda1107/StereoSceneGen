import blenderproc as bproc
import numpy as np
import os
import itertools
import bpy
import re

bproc.init()
# ================= 1. 加载场景数据 =================
objs_path = './assets/alley/ph_hidden_alley.blend'

# 加载所有可能的数据类型
objs = bproc.loader.load_blend(

    objs_path,
    obj_types=['MESH', 'CURVE', 'SURFACE', 'META', 'FONT', 'VOLUME', 'LIGHT', 'CAMERA', 'EMPTY'],
)

print(f"bproc 初始加载了 {len(objs)} 个物体")


# ================= 2. 基于原始可见性与集合继承的修复 =================

# 步骤 A：同步原文件的 Collection（集合）层级可见性
with bpy.data.libraries.load(objs_path, link=False) as (data_from, data_to):
    if data_from.scenes:
        data_to.scenes = [data_from.scenes[0]]

if data_to.scenes and data_to.scenes[0]:
    orig_scene = data_to.scenes[0]
    hidden_collections = set()

    # 递归查找原场景 View Layer 中被关闭的 Collection
    def find_hidden_collections(layer_coll):
        # 获取集合名称（过滤掉 Blender 导入时自动加的 .001 等后缀）
        base_name = re.sub(r'\.\d{3}$', '', layer_coll.collection.name)
        
        # 如果集合在视图层被排除(Exclude)，或者被禁用了渲染(hide_render)
        if layer_coll.exclude or layer_coll.collection.hide_render:
            hidden_collections.add(base_name)
            
        for child in layer_coll.children:
            find_hidden_collections(child)

    find_hidden_collections(orig_scene.view_layers[0].layer_collection)
    print(f"从原场景成功读取到隐藏集合黑名单: {hidden_collections}")

    # 将黑名单应用到当前场景的所有物体
    for obj in bpy.data.objects:
        for coll in obj.users_collection:
            coll_base_name = re.sub(r'\.\d{3}$', '', coll.name)
            if coll_base_name in hidden_collections:
                obj.hide_render = True
                obj.hide_viewport = True
                break # 属于隐藏集合的物体直接跳过
                
    # 删除临时加载的原场景数据，释放内存
    bpy.data.scenes.remove(orig_scene)


# 步骤 B：执行底层的精确唤醒
for obj in bpy.data.objects:
    # 如果物体在原场景自身被隐藏，或者刚才被集合黑名单屏蔽了，直接跳过
    if obj.hide_render:
        continue
        
    # 针对灯光 (LIGHT) 的特殊处理，防止着色器丢失
    if obj.type == 'LIGHT':
        if hasattr(obj.data, 'use_nodes'):
            obj.data.use_nodes = True
        if hasattr(obj, 'visible_camera'):
            obj.visible_camera = True
            obj.visible_diffuse = True
            obj.visible_glossy = True
            obj.visible_transmission = True
            
    # 针对空物体 (EMPTY) / 集合实例的修复
    if obj.type == 'EMPTY' and obj.instance_type == 'COLLECTION':
        if obj.instance_collection:
            obj.instance_collection.hide_render = False

    # 步骤 C：通过关键字隐藏体积雾气
    for obj in bpy.data.objects:
        if not obj.hide_render:
            # 检查是否包含雾气相关关键字
            if any(kw in obj.name.lower() for kw in ['fog', 'atmosphere', 'volume', 'mist']):
                obj.hide_render = True
                print(f"触发关键字隐藏，已隐藏疑似雾气物体: {obj.name}")
    print(f"可见性状态继承与修复完成")
# ======================================================================

# ================= 3. 恢复原场景的世界环境光 =================
with bpy.data.libraries.load(objs_path, link=False) as (data_from, data_to):
    data_to.worlds = data_from.worlds

for world in data_to.worlds:
    # 找到原作者配置好节点的世界环境
    if world and world.use_nodes and "World" not in world.name: 
        bpy.context.scene.world = world
        print(f"成功提取并恢复了原场景的世界环境光: {world.name}")
        break
# ======================================================================



# Create a point light above the scene
#light = bproc.types.Light()
#light.set_location([2, -2, 10])
#light.set_energy(300)


def construct_camera_rotation_list(angle_step):
    camera_rotations = []
    for angle in np.arange(0, 2 * np.pi, angle_step):
        camera_rotations.append([-np.pi/2, 0, angle])
    return camera_rotations

def construct_camera_location_list(x_start, x_end, step_num_x, y_start, y_end, step_num_y, z_start, z_end, step_num_z):
    camera_locations = []
    for x in np.linspace(x_start, x_end, step_num_x):
        for y in np.linspace(y_start, y_end, step_num_y):
            for z in np.linspace(z_start, z_end, step_num_z):
                camera_locations.append([x, y, z])
    return camera_locations

def create_camera_array(rows=2, cols=3, focal_length=30.0, resolution=(1024, 1024), gap_mm=3.75,
                        center_location=[0, -5, 5], center_rotation=[np.pi / 2, 0, 0]):
    gap = gap_mm / 1000.0
    bproc.camera.set_resolution(resolution[0], resolution[1])
    bproc.camera.set_intrinsics_from_blender_params(lens=focal_length, lens_unit="MILLIMETERS")
    
    col_offsets = [(c - (cols - 1)/2) * gap for c in range(cols)]
    row_offsets = [-(r - (rows - 1)/2) * gap for r in range(rows)]
    
    for r in range(rows):
        for c in range(cols):
            cam_loc = [
                center_location[0] + col_offsets[c],
                center_location[1],
                center_location[2] + row_offsets[r]
            ]
            
            # 使用 Blender 原生坐标构建矩阵
            cam_pose = bproc.math.build_transformation_mat(cam_loc, center_rotation)
            bproc.camera.add_camera_pose(cam_pose)

# ================= 4. 动态提取场景相机位姿 =================

# 尝试获取场景中当前的活跃主相机
active_cam = bpy.context.scene.camera

# 如果场景没有设置活跃相机，则寻找场景中的第一个相机实体
if active_cam is None:
    for obj in bpy.data.objects:
        if obj.type == 'CAMERA':
            active_cam = obj
            break

if active_cam is None:
    raise ValueError("致命错误：在该 .blend 场景中没有找到任何相机！请检查原文件。")

# 提取核心参数：位置 (x, y, z)、旋转欧拉角 (弧度制) 和 焦距 (毫米)
dyn_location = [active_cam.location.x, active_cam.location.y, active_cam.location.z]
dyn_rotation = [active_cam.rotation_euler.x, active_cam.rotation_euler.y, active_cam.rotation_euler.z]
dyn_focal_length = active_cam.data.lens

print(f"成功提取场景相机 [{active_cam.name}] 参数:")
print(f"   - 位置: {dyn_location}")
print(f"   - 旋转: {dyn_rotation}")
print(f"   - 焦距: {dyn_focal_length} mm")

# 使用提取到的动态参数生成相机阵列
create_camera_array(
    rows=2,
    cols=3,
    focal_length=dyn_focal_length,   # 动态继承原场景焦距
    resolution=(1024, 1024), 
    gap_mm=37.5,
    center_location=dyn_location,    # 动态继承原场景位置
    center_rotation=dyn_rotation     # 动态继承原场景角度
)
# ======================================================================

# ================= 4. 强制关闭立体/双目渲染 =================
# 关闭全局多视图渲染（阻止生成 _L 和 _R 后缀）
bpy.context.scene.render.use_multiview = False

print("已强制关闭原场景的双目立体渲染功能！")
# ===============================================================================

# ================= 5. 在相机前方放置一个地面参照物 =================
import mathutils

# 创建一个基础物体 (CUBE)
box = bproc.object.create_primitive("CUBE")

# 设置长方体的实际尺寸 (米)
target_length = 0.3  # X轴长度: 0.3米
target_width = 0.3   # Y轴宽度: 0.3米
target_height = 0.8  # Z轴高度: 0.8米

box.set_scale([target_length / 2, target_width / 2, target_height / 2])

# 计算相机的水平前方向向量
euler = mathutils.Euler(dyn_rotation, 'XYZ')
rot_mat = euler.to_matrix()
forward_vec_mathutils = rot_mat @ mathutils.Vector((0.0, 0.0, -1.0))
forward_vec = np.array(forward_vec_mathutils)

# 提取水平方向 (XY平面) 并归一化
forward_xy = forward_vec[:2]
if np.linalg.norm(forward_xy) > 1e-6:
    forward_xy /= np.linalg.norm(forward_xy)
else:
    forward_xy = np.array([0.0, 1.0])

# 计算最终落地位置
# 距离设定为 1.5 米
box_x = dyn_location[0] + forward_xy[0] * distance
box_y = dyn_location[1] + forward_xy[1] * distance

ground_z_level = 0.0 
box_z = ground_z_level + (target_height / 2)

box.set_location([box_x, box_y, box_z])

# 给长方体一个醒目的材质（红色）
matrix = bproc.material.create("red_box_mat")
matrix.set_principled_shader_value("Base Color", [0.8, 0.2, 0.2, 1])
box.replace_materials(matrix)

print(f"已在相机前方 {distance}m 处的地面放置红色长方体: [{box_x:.3f}, {box_y:.3f}, {box_z:.3f}]")
# ======================================================================

# 渲染场景
data = bproc.renderer.render()

# 保存
output_dir = f"output/grid_scenario_test_1/"
os.makedirs(output_dir, exist_ok=True)
bproc.writer.write_hdf5(output_dir, data)