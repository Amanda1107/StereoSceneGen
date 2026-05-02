import blenderproc as bproc
import numpy as np
import os
import bpy
import re
import mathutils

# ================= 修复 Blender 的 frame_end 属性限制 =================
orig_setattr = bpy.types.Scene.__setattr__

def fixed_setattr(self, name, value):
    if name == "frame_end":
        value = int(value)
    return orig_setattr(self, name, value)

bpy.types.Scene.__setattr__ = fixed_setattr
# ======================================================================

def create_camera_array(rows=2, cols=3, focal_length=30.0, resolution=(1024, 1024), gap_mm=500.0,
                        center_location=[0, 0, 0], center_rotation=[0, 0, 0]):
    """使用 mathutils 和本地坐标系构建相机阵列"""
    gap = gap_mm / 1000.0
    bproc.camera.set_resolution(resolution[0], resolution[1])
    bproc.camera.set_intrinsics_from_blender_params(lens=focal_length, lens_unit="MILLIMETERS")
    
    # 计算列与行的偏移量分布
    col_offsets = [(c - (cols - 1)/2) * gap for c in range(cols)]
    row_offsets = [-(r - (rows - 1)/2) * gap for r in range(rows)]
    
    # 1. 构建主相机中心的 4x4 基础变换矩阵
    base_matrix = mathutils.Matrix.LocRotScale(
        mathutils.Vector(center_location),
        mathutils.Euler(center_rotation, 'XYZ'),
        None
    )
    
    # ================= 核心逻辑：显式帧控制 =================
    frame_idx = 0  # 从第 0 帧开始对齐
    
    for r in range(rows):
        for c in range(cols):
            # 2. 在相机的本地坐标系下设定偏移量
            # X 轴控制水平偏移，Y 轴控制垂直偏移 (Blender 本地坐标系)，Z 轴为 0 保持深度不变
            local_translation = mathutils.Vector((col_offsets[c], row_offsets[r], 0.0))
            
            # 3. 矩阵相乘：基础位姿与本地偏移结合，计算绝对世界坐标矩阵
            new_matrix = base_matrix @ mathutils.Matrix.Translation(local_translation)
            
            # 4. 转换为 numpy 数组以供 BlenderProc 调用
            cam_pose = np.array(new_matrix)
            
            # 5. 传入 frame 参数，将位姿写入特定帧
            bproc.camera.add_camera_pose(cam_pose, frame=frame_idx)
            
            frame_idx += 1
            
    print(f"成功构建本地相机阵列。共 {frame_idx} 个机位，阵列间距: {gap} 米")


# ================= 批量处理配置 =================
scene_configs = [
    # 可在此处添加或移除场景配置字典以控制批量渲染队列
     {
         "blend_path": "./assets/alley/ph_hidden_alley.blend",
         "output_dir": "output/alley_scenario_test",
         "gap_mm": 37.5
     },
     {
         "blend_path": "./assets/Namaqualand/Namaqualand.blend",
         "output_dir": "output/namaqualand_scenario_test",
         "gap_mm": 37.5
     },
     {
         "blend_path": "./assets/pine_forest/polyhaven_pine_fir_forest.blend",
         "output_dir": "output/pine_forest_scenario_test",
         "gap_mm": 37.5
     },
    {
        "blend_path": "./assets/the_shed/the_shed.blend",
        "output_dir": "output/shed_scenario_test",
        "gap_mm": 37.5
    }
]
# ================================================

# 初始化 BlenderProc
bproc.init()
# ================= 全局开启深度图渲染 =================
bproc.renderer.enable_distance_output(activate_antialiasing=False)
print("已全局开启深度图 (Distance) 渲染通道。")
# ===================================================================
# 遍历并处理配置中的场景
for idx, config in enumerate(scene_configs):
    objs_path = config["blend_path"]
    out_dir = config["output_dir"]
    gap_mm = config["gap_mm"]
    
    print(f"\n" + "="*60)
    print(f"开始处理场景 ({idx+1}/{len(scene_configs)}): {objs_path}")
    print(f"="*60)
    
    # 清理上一场景遗留的物体和数据，确保状态隔离
    bproc.clean_up()
    
    # ================= 1. 加载场景资产 =================
    objs = bproc.loader.load_blend(
        objs_path,
        obj_types=['MESH', 'CURVE', 'SURFACE', 'META', 'FONT', 'VOLUME', 'LIGHT', 'CAMERA', 'EMPTY'],
    )
    print(f"BlenderProc 初始加载了 {len(objs)} 个物体。")

    # ================= 2. 基于原始可见性与集合继承的物体状态同步 =================

    # 步骤 A：同步原文件的 Collection 层级可见性，防止隐藏对象渲染
    with bpy.data.libraries.load(objs_path, link=False) as (data_from, data_to):
        if data_from.scenes:
            data_to.scenes = [data_from.scenes[0]]

    if data_to.scenes and data_to.scenes[0]:
        orig_scene = data_to.scenes[0]
        hidden_collections = set()

        # 递归查找原场景 View Layer 中被关闭的 Collection
        def find_hidden_collections(layer_coll):
            # 获取集合基础名称（移除 Blender 导入时自动添加的数字后缀）
            base_name = re.sub(r'\.\d{3}$', '', layer_coll.collection.name)
            
            # 如果集合在视图层被排除，或被禁用了渲染
            if layer_coll.exclude or layer_coll.collection.hide_render:
                hidden_collections.add(base_name)
                
            for child in layer_coll.children:
                find_hidden_collections(child)

        find_hidden_collections(orig_scene.view_layers[0].layer_collection)
        print(f"从原场景成功读取隐藏集合名单: {hidden_collections}")

        # 将隐藏设置应用到当前场景的所有关联物体
        for obj in bpy.data.objects:
            for coll in obj.users_collection:
                coll_base_name = re.sub(r'\.\d{3}$', '', coll.name)
                if coll_base_name in hidden_collections:
                    obj.hide_render = True
                    obj.hide_viewport = True
                    break  # 若物体属于隐藏集合，则隐藏并跳出检查
                    
        # 移除临时加载的原场景数据以释放内存
        bpy.data.scenes.remove(orig_scene)


    # 步骤 B：精确同步未隐藏物体的状态
    for obj in bpy.data.objects:
        # 1. 跳过在原场景中被隐藏或处于隐藏集合中的物体
        if obj.hide_render:
            continue
            
        # 2. 恢复灯光 (LIGHT) 物体的节点及可见性设置
        if obj.type == 'LIGHT':
            if hasattr(obj.data, 'use_nodes'):
                obj.data.use_nodes = True
            if hasattr(obj, 'visible_camera'):
                obj.visible_camera = True
                obj.visible_diffuse = True
                obj.visible_glossy = True
                obj.visible_transmission = True
                
        # 3. 恢复集合实例 (EMPTY) 的可见性设置
        if obj.type == 'EMPTY' and obj.instance_type == 'COLLECTION':
            if obj.instance_collection:
                obj.instance_collection.hide_render = False


    # 步骤 C：基于关键字过滤体积雾气等非必要渲染对象
    for obj in bpy.data.objects:
        if not obj.hide_render:
            # 过滤常用于体积雾气的对象名称
            if any(kw in obj.name.lower() for kw in ['fog', 'atmosphere', 'volume', 'mist']):
                obj.hide_render = True
                print(f"触发关键字过滤，已隐藏目标物体: {obj.name}")

    print("可见性状态同步完成。")
    # ==============================================================================


    # ================= 3. 恢复场景原始世界环境光 =================
    with bpy.data.libraries.load(objs_path, link=False) as (data_from, data_to):
        data_to.worlds = data_from.worlds

    for world in data_to.worlds:
        # 寻找并应用配置了节点的世界环境
        if world and world.use_nodes and "World" not in world.name: 
            bpy.context.scene.world = world
            print(f"成功提取并应用原场景世界环境: {world.name}")
            break

    # ================= 4. 提取场景主相机位姿 =================
    active_cam = bpy.context.scene.camera

    # 若未指定活跃相机，则使用场景中的首个相机对象
    if active_cam is None:
        for obj in bpy.data.objects:
            if obj.type == 'CAMERA':
                active_cam = obj
                break

    if active_cam is None:
        raise ValueError(f"错误：在场景 {objs_path} 中未找到相机对象，请检查原始文件。")

    dyn_location = [active_cam.location.x, active_cam.location.y, active_cam.location.z]
    dyn_rotation = [active_cam.rotation_euler.x, active_cam.rotation_euler.y, active_cam.rotation_euler.z]
    dyn_focal_length = active_cam.data.lens

    print(f"成功提取场景相机 [{active_cam.name}] 参数:")
    print(f"   - 位置: {dyn_location}")
    print(f"   - 旋转: {dyn_rotation}")
    print(f"   - 焦距: {dyn_focal_length} mm")

    # 清除原相机的动画数据，防止干扰静态阵列位姿
    if active_cam.animation_data:
        active_cam.animation_data_clear()
        print("已清除原相机的动画数据。")

    # 生成相机阵列
    create_camera_array(
        rows=2,
        cols=3,
        focal_length=dyn_focal_length,
        resolution=(1024, 1024), 
        gap_mm=gap_mm, # 使用配置项中的间距参数
        center_location=dyn_location,
        center_rotation=dyn_rotation
    )

    # 禁用多视图（立体）渲染
    bpy.context.scene.render.use_multiview = False
    print("已禁用双目立体渲染功能。")

    # 设置渲染帧范围
    bpy.context.scene.frame_start = 0
    bpy.context.scene.frame_end = 6
    print("已设置渲染帧范围: 0 到 5。")

    # ================= 5. 冻结全局环境动画 =================
    print("正在清除材质与物体的动画数据...")
    for mat in bpy.data.materials:
        if mat.node_tree and mat.node_tree.animation_data:
            mat.node_tree.animation_data_clear()

    for obj in bpy.data.objects:
        if obj.type == 'CAMERA':
            continue 
        if obj.animation_data:
            obj.animation_data_clear()
            
    print("环境动画已冻结，保留相机阵列位姿。")

    # ================= 6. 输出阵列相机位姿信息 =================
    print("提取并验证渲染相机位姿坐标:")
    cam = bpy.context.scene.camera
    frame_start = bpy.context.scene.frame_start
    frame_end = bpy.context.scene.frame_end

    for frame in range(frame_start, frame_end):
        bpy.context.scene.frame_set(frame)
        bpy.context.view_layer.update()
        loc_x, loc_y, loc_z = cam.matrix_world.translation
        print(f"   - 视角 (Frame {frame}): X = {loc_x:8.4f} | Y = {loc_y:8.4f} | Z = {loc_z:8.4f}")

    print(f"即将开始渲染场景至: {out_dir}")

    # ================= 7. 渲染与保存 =================
    
    data = bproc.renderer.render()
    
    os.makedirs(out_dir, exist_ok=True)
    bproc.writer.write_hdf5(out_dir, data)
    print(f"场景渲染完毕，数据已保存至: {out_dir}")

# 批量处理结束，输出完成提示
print("\n" + "="*30)
print("所有场景的批量渲染与采集任务已完成。")
print("="*30)