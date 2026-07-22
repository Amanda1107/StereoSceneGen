import blenderproc as bproc
import numpy as np
import bpy
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent

bproc.init()
objs_path = PROJECT_ROOT / "assets" / "hidden_alley" / "ph_hidden_alley.blend"

objs = bproc.loader.load_blend(

    str(objs_path),
    obj_types=['MESH', 'CURVE', 'SURFACE', 'META', 'FONT', 'VOLUME', 'LIGHT', 'CAMERA', 'EMPTY'],
)

print(f"BlenderProc loaded {len(objs)} objects.")


# Restore collection visibility from the source scene.
with bpy.data.libraries.load(str(objs_path), link=False) as (data_from, data_to):
    if data_from.scenes:
        data_to.scenes = [data_from.scenes[0]]

if data_to.scenes and data_to.scenes[0]:
    orig_scene = data_to.scenes[0]
    hidden_collections = set()

    def find_hidden_collections(layer_coll):
        base_name = re.sub(r'\.\d{3}$', '', layer_coll.collection.name)

        if layer_coll.exclude or layer_coll.collection.hide_render:
            hidden_collections.add(base_name)
            
        for child in layer_coll.children:
            find_hidden_collections(child)

    find_hidden_collections(orig_scene.view_layers[0].layer_collection)
    print(f"Hidden collections loaded from the source scene: {hidden_collections}")

    for obj in bpy.data.objects:
        for coll in obj.users_collection:
            coll_base_name = re.sub(r'\.\d{3}$', '', coll.name)
            if coll_base_name in hidden_collections:
                obj.hide_render = True
                obj.hide_viewport = True
                break

    bpy.data.scenes.remove(orig_scene)

for obj in bpy.data.objects:
    if obj.hide_render:
        continue

    if obj.type == 'LIGHT':
        if hasattr(obj.data, 'use_nodes'):
            obj.data.use_nodes = True
        if hasattr(obj, 'visible_camera'):
            obj.visible_camera = True
            obj.visible_diffuse = True
            obj.visible_glossy = True
            obj.visible_transmission = True
            
    if obj.type == 'EMPTY' and obj.instance_type == 'COLLECTION':
        if obj.instance_collection:
            obj.instance_collection.hide_render = False

    for obj in bpy.data.objects:
        if not obj.hide_render:
            if any(kw in obj.name.lower() for kw in ['fog', 'atmosphere', 'volume', 'mist']):
                obj.hide_render = True
                print(f"Keyword filter matched; hidden object: {obj.name}")
    print("Visibility synchronization complete.")
with bpy.data.libraries.load(str(objs_path), link=False) as (data_from, data_to):
    data_to.worlds = data_from.worlds

for world in data_to.worlds:
    if world and world.use_nodes and "World" not in world.name: 
        bpy.context.scene.world = world
        print(f"Applied the source scene world: {world.name}")
        break
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
                        center_location=(0, -5, 5), center_rotation=(np.pi / 2, 0, 0)):
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
            
            cam_pose = bproc.math.build_transformation_mat(cam_loc, center_rotation)
            bproc.camera.add_camera_pose(cam_pose)

# Use the active scene camera, or fall back to the first available camera.
active_cam = bpy.context.scene.camera

if active_cam is None:
    for obj in bpy.data.objects:
        if obj.type == 'CAMERA':
            active_cam = obj
            break

if active_cam is None:
    raise ValueError("No camera was found in the .blend scene. Check the source file.")

dyn_location = [active_cam.location.x, active_cam.location.y, active_cam.location.z]
dyn_rotation = [active_cam.rotation_euler.x, active_cam.rotation_euler.y, active_cam.rotation_euler.z]
dyn_focal_length = active_cam.data.lens

print(f"Loaded parameters from scene camera [{active_cam.name}]:")
print(f"   - Location: {dyn_location}")
print(f"   - Rotation: {dyn_rotation}")
print(f"   - Focal length: {dyn_focal_length} mm")

create_camera_array(
    rows=2,
    cols=3,
    focal_length=dyn_focal_length,
    resolution=(1024, 1024), 
    gap_mm=37.5,
    center_location=dyn_location,
    center_rotation=dyn_rotation
)

bpy.context.scene.render.use_multiview = False

print("Stereo multiview rendering is disabled.")
import mathutils

# Place a red reference box in front of the source camera.
box = bproc.object.create_primitive("CUBE")

target_length = 0.3
target_width = 0.3
target_height = 0.8

box.set_scale([target_length / 2, target_width / 2, target_height / 2])

euler = mathutils.Euler(dyn_rotation, 'XYZ')
rot_mat = euler.to_matrix()
forward_vec_mathutils = rot_mat @ mathutils.Vector((0.0, 0.0, -1.0))
forward_vec = np.array(forward_vec_mathutils)

forward_xy = forward_vec[:2]
if np.linalg.norm(forward_xy) > 1e-6:
    forward_xy /= np.linalg.norm(forward_xy)
else:
    forward_xy = np.array([0.0, 1.0])

distance = 1.5
box_x = dyn_location[0] + forward_xy[0] * distance
box_y = dyn_location[1] + forward_xy[1] * distance

ground_z_level = 0.0 
box_z = ground_z_level + (target_height / 2)

box.set_location([box_x, box_y, box_z])

matrix = bproc.material.create("red_box_mat")
matrix.set_principled_shader_value("Base Color", [0.8, 0.2, 0.2, 1])
box.replace_materials(matrix)

print(f"Placed a red reference box {distance} m in front of the camera at [{box_x:.3f}, {box_y:.3f}, {box_z:.3f}].")
data = bproc.renderer.render()

output_dir = PROJECT_ROOT / "output" / "grid_scenario_test_1"
output_dir.mkdir(parents=True, exist_ok=True)
bproc.writer.write_hdf5(str(output_dir), data)
