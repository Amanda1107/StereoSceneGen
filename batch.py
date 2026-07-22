import blenderproc as bproc
import numpy as np
import bpy
import re
import mathutils
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent


def project_path(relative_path):
    """Resolve a project-relative path independently of the working directory."""
    relative_path = Path(relative_path)
    if relative_path.is_absolute():
        raise ValueError(f"Use a path relative to the project root: {relative_path}")
    return PROJECT_ROOT / relative_path

# Blender requires frame_end to be an integer.
orig_setattr = bpy.types.Scene.__setattr__

def fixed_setattr(self, name, value):
    if name == "frame_end":
        value = int(value)
    return orig_setattr(self, name, value)

bpy.types.Scene.__setattr__ = fixed_setattr

def create_camera_array(rows=2, cols=3, focal_length=30.0, resolution=(1024, 1024), gap_mm=500.0,
                        center_location=(0, 0, 0), center_rotation=(0, 0, 0)):
    """Build a camera array in the center camera's local coordinate system."""
    gap = gap_mm / 1000.0
    bproc.camera.set_resolution(resolution[0], resolution[1])
    bproc.camera.set_intrinsics_from_blender_params(lens=focal_length, lens_unit="MILLIMETERS")
    
    col_offsets = [(c - (cols - 1)/2) * gap for c in range(cols)]
    row_offsets = [-(r - (rows - 1)/2) * gap for r in range(rows)]

    base_matrix = mathutils.Matrix.LocRotScale(
        mathutils.Vector(center_location),
        mathutils.Euler(center_rotation, 'XYZ'),
        None
    )
    
    frame_idx = 0
    
    for r in range(rows):
        for c in range(cols):
            # Apply row and column offsets in the camera's local coordinate system.
            local_translation = mathutils.Vector((col_offsets[c], row_offsets[r], 0.0))
            new_matrix = base_matrix @ mathutils.Matrix.Translation(local_translation)
            cam_pose = np.array(new_matrix)
            bproc.camera.add_camera_pose(cam_pose, frame=frame_idx)
            
            frame_idx += 1
            
    print(f"Built a local camera array with {frame_idx} poses and {gap} m spacing.")


scene_configs = [
    # Add or remove scene configurations here.
     {
         "blend_path": "./assets/hidden_alley/ph_hidden_alley.blend",
         "output_dir": "output/alley_scenario_test",
         "rows": 2,
         "cols": 3,
         "gap_mm": 37.5,
         "resolution": (1024, 1024),
         "focal_length": None,
         "center_location": None,
         "center_rotation": None
     },
     {
         "blend_path": "./assets/namaqualand/Namaqualand.blend",
         "output_dir": "output/namaqualand_scenario_test",
         "rows": 2,
         "cols": 3,
         "gap_mm": 37.5,
         "resolution": (1024, 1024),
         "focal_length": None,
         "center_location": None,
         "center_rotation": None
     },
     {
         "blend_path": "./assets/pine_forest/polyhaven_pine_fir_forest.blend",
         "output_dir": "output/pine_forest_scenario_test",
         "rows": 2,
         "cols": 3,
         "gap_mm": 37.5,
         "resolution": (1024, 1024),
         "focal_length": None,
         "center_location": None,
         "center_rotation": None
     },
    {
        "blend_path": "./assets/the_shed/the_shed.blend",
        "output_dir": "output/shed_scenario_test",
        "rows": 2,
        "cols": 3,
        "gap_mm": 37.5,
        "resolution": (1024, 1024),
        "focal_length": None,
        "center_location": None,
        "center_rotation": None
    }
]

bproc.init()
bproc.renderer.enable_distance_output(activate_antialiasing=False)
print("Distance output is enabled globally.")

for idx, config in enumerate(scene_configs):
    objs_path = project_path(config["blend_path"])
    out_dir = project_path(config["output_dir"])
    rows = config.get("rows", 2)
    cols = config.get("cols", 3)
    gap_mm = config.get("gap_mm", 37.5)
    resolution = config.get("resolution", (1024, 1024))
    
    print(f"\n" + "="*60)
    print(f"Processing scene ({idx+1}/{len(scene_configs)}): {objs_path}")
    print(f"="*60)
    
    bproc.clean_up()

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

    # Use the active scene camera, or fall back to the first available camera.
    active_cam = bpy.context.scene.camera

    if active_cam is None:
        for obj in bpy.data.objects:
            if obj.type == 'CAMERA':
                active_cam = obj
                break

    if active_cam is None:
        raise ValueError(f"No camera was found in scene {objs_path}. Check the source file.")

    dyn_location = [active_cam.location.x, active_cam.location.y, active_cam.location.z]
    dyn_rotation = [active_cam.rotation_euler.x, active_cam.rotation_euler.y, active_cam.rotation_euler.z]
    dyn_focal_length = active_cam.data.lens

    print(f"Loaded parameters from scene camera [{active_cam.name}]:")
    print(f"   - Location: {dyn_location}")
    print(f"   - Rotation: {dyn_rotation}")
    print(f"   - Focal length: {dyn_focal_length} mm")

    focal_length = config.get("focal_length")
    center_location = config.get("center_location")
    center_rotation = config.get("center_rotation")

    if focal_length is None:
        focal_length = dyn_focal_length
    if center_location is None:
        center_location = dyn_location
    if center_rotation is None:
        center_rotation = dyn_rotation

    print("Camera array parameters:")
    print(f"   - Array: {rows} rows x {cols} columns")
    print(f"   - Center location: {center_location}")
    print(f"   - Center rotation: {center_rotation}")
    print(f"   - Focal length: {focal_length} mm")
    print(f"   - Baseline: {gap_mm} mm")

    if active_cam.animation_data:
        active_cam.animation_data_clear()
        print("Cleared animation data from the source camera.")

    create_camera_array(
        rows=rows,
        cols=cols,
        focal_length=focal_length,
        resolution=resolution,
        gap_mm=gap_mm,
        center_location=center_location,
        center_rotation=center_rotation
    )

    bpy.context.scene.render.use_multiview = False
    print("Stereo multiview rendering is disabled.")

    frame_count = rows * cols
    bpy.context.scene.frame_start = 0
    bpy.context.scene.frame_end = frame_count
    print(f"Render frame range set to 0 through {frame_count - 1}.")

    print("Clearing material and object animation data...")
    for mat in bpy.data.materials:
        if mat.node_tree and mat.node_tree.animation_data:
            mat.node_tree.animation_data_clear()

    for obj in bpy.data.objects:
        if obj.type == 'CAMERA':
            continue 
        if obj.animation_data:
            obj.animation_data_clear()
            
    print("Scene animation is frozen; camera array poses are preserved.")

    print("Camera pose verification:")
    cam = bpy.context.scene.camera
    frame_start = bpy.context.scene.frame_start
    frame_end = bpy.context.scene.frame_end

    for frame in range(frame_start, frame_end):
        bpy.context.scene.frame_set(frame)
        bpy.context.view_layer.update()
        loc_x, loc_y, loc_z = cam.matrix_world.translation
        print(f"   - View (Frame {frame}): X = {loc_x:8.4f} | Y = {loc_y:8.4f} | Z = {loc_z:8.4f}")

    print(f"Rendering scene to: {out_dir}")

    data = bproc.renderer.render()
    
    out_dir.mkdir(parents=True, exist_ok=True)
    bproc.writer.write_hdf5(str(out_dir), data)
    print(f"Scene rendering complete. Data saved to: {out_dir}")

print("\n" + "="*30)
print("Batch rendering and data capture completed for all scenes.")
print("="*30)
