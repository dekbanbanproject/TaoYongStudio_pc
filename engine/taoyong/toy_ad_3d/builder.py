"""Blender 4.2 LTS headless script for Cute Toy Product Ad Animation."""

import json
import math
import os
import sys
from pathlib import Path

import bpy

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.append(str(SCRIPT_DIR))

from presets import TOY_CHARACTERS, TOY_ENVIRONMENTS


def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if not bpy.data.scenes:
        bpy.ops.scene.new(type='EMPTY')


def create_material(name, color=(1, 1, 1, 1), roughness=0.15, specular=0.8, metallic=0.0):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Roughness"].default_value = roughness
        if "Specular IOR Level" in bsdf.inputs:
            bsdf.inputs["Specular IOR Level"].default_value = specular
        elif "Specular" in bsdf.inputs:
            bsdf.inputs["Specular"].default_value = specular
        if "Metallic" in bsdf.inputs:
            bsdf.inputs["Metallic"].default_value = metallic
    return mat


def create_image_material(name, image_path):
    """Create a material using an image texture for product display."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    bsdf = nodes.get("Principled BSDF")
    if bsdf and os.path.exists(image_path):
        try:
            img_node = nodes.new(type='ShaderNodeTexImage')
            img = bpy.data.images.load(image_path)
            img_node.image = img
            links.new(img_node.outputs['Color'], bsdf.inputs['Base Color'])
            bsdf.inputs['Roughness'].default_value = 0.2
            if "Specular IOR Level" in bsdf.inputs:
                bsdf.inputs["Specular IOR Level"].default_value = 0.6
        except Exception:
            pass
    return mat


def build_vinyl_toy_figure(char_cfg, location=(-1.1, 0, 0)):
    """Build a glossy Pop Mart / vinyl collectible miniature figure."""
    col_primary = char_cfg.get("primary_color", (0.92, 0.78, 0.88, 1.0))
    col_belly = char_cfg.get("belly_color", (0.98, 0.95, 0.92, 1.0))
    roughness = char_cfg.get("roughness", 0.12)
    specular = char_cfg.get("specular", 0.85)

    mat_vinyl = create_material("Vinyl_Main", col_primary, roughness=roughness, specular=specular)
    mat_belly = create_material("Vinyl_Belly", col_belly, roughness=roughness, specular=specular)
    mat_black = create_material("Vinyl_Eye", (0.05, 0.05, 0.07, 1.0), roughness=0.08, specular=0.95)
    mat_blush = create_material("Vinyl_Blush", (1.0, 0.55, 0.65, 1.0), roughness=0.3)
    mat_gold = create_material("Vinyl_Gold", (0.98, 0.78, 0.25, 1.0), roughness=0.2, specular=0.9, metallic=0.7)

    # 1. Big Cute Head
    head_z = location[2] + 1.25
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=16, radius=0.62, location=(location[0], location[1], head_z))
    head = bpy.context.active_object
    head.name = "Toy_Head"
    head.scale = (1.0, 0.95, 0.95)
    bpy.ops.object.shade_smooth()
    head.data.materials.append(mat_vinyl)

    # 2. Round Ears
    for side in (-1, 1):
        ear_x = location[0] + side * 0.48
        ear_z = head_z + 0.45
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.22, location=(ear_x, location[1], ear_z))
        ear = bpy.context.active_object
        ear.scale = (0.7, 0.4, 0.7)
        ear.data.materials.append(mat_vinyl)
        ear.parent = head

        # Inner ear
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.14, location=(ear_x, location[1] + 0.05, ear_z))
        i_ear = bpy.context.active_object
        i_ear.scale = (0.6, 0.2, 0.6)
        i_ear.data.materials.append(mat_belly)
        i_ear.parent = head

    # 3. Bead Eyes & Rosy Cheeks
    for side in (-1, 1):
        eye_x = location[0] + side * 0.24
        eye_y = location[1] + 0.52
        eye_z = head_z + 0.02
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.085, location=(eye_x, eye_y, eye_z))
        eye = bpy.context.active_object
        eye.data.materials.append(mat_black)
        eye.parent = head

        # Eye shine
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.028, location=(eye_x + side * 0.02, eye_y + 0.06, eye_z + 0.025))
        hl = bpy.context.active_object
        hl.data.materials.append(create_material("Eye_HL", (1, 1, 1, 1), roughness=0.05))
        hl.parent = head

        # Blush
        bpy.ops.mesh.primitive_cylinder_add(radius=0.11, depth=0.02, location=(eye_x + side * 0.12, eye_y - 0.04, eye_z - 0.15))
        blush = bpy.context.active_object
        blush.rotation_euler = (math.radians(85), 0, 0)
        blush.data.materials.append(mat_blush)
        blush.parent = head

    # Snout & Nose
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.16, location=(location[0], location[1] + 0.54, head_z - 0.10))
    snout = bpy.context.active_object
    snout.scale = (1.0, 0.6, 0.8)
    snout.data.materials.append(mat_belly)
    snout.parent = head

    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.045, location=(location[0], location[1] + 0.63, head_z - 0.06))
    nose = bpy.context.active_object
    nose.data.materials.append(mat_black)
    nose.parent = head

    # 4. Body
    body_z = location[2] + 0.55
    bpy.ops.mesh.primitive_uv_sphere_add(segments=20, ring_count=14, radius=0.45, location=(location[0], location[1], body_z))
    body = bpy.context.active_object
    body.name = "Toy_Body"
    body.scale = (0.85, 0.8, 1.05)
    bpy.ops.object.shade_smooth()
    body.data.materials.append(mat_vinyl)

    # Belly Oval
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.30, location=(location[0], location[1] + 0.28, body_z))
    belly = bpy.context.active_object
    belly.scale = (0.8, 0.3, 1.0)
    belly.data.materials.append(mat_belly)
    belly.parent = body

    # 5. Arms
    arm_l = None
    arm_r = None
    for side in (-1, 1):
        ax = location[0] + side * 0.44
        ay = location[1]
        az = body_z + 0.20
        bpy.ops.mesh.primitive_cylinder_add(radius=0.10, depth=0.35, location=(ax, ay, az))
        arm = bpy.context.active_object
        arm.name = f"Toy_Arm_{'L' if side < 0 else 'R'}"
        arm.rotation_euler = (math.radians(20), math.radians(side * 25), 0)
        arm.data.materials.append(mat_vinyl)
        arm.parent = body
        if side < 0:
            arm_l = arm
        else:
            arm_r = arm

    # 6. Legs
    for side in (-1, 1):
        lx = location[0] + side * 0.22
        lz = location[2] + 0.18
        bpy.ops.mesh.primitive_cylinder_add(radius=0.12, depth=0.32, location=(lx, location[1], lz))
        leg = bpy.context.active_object
        leg.data.materials.append(mat_vinyl)
        leg.parent = body

    # Armature Rig
    bpy.ops.object.armature_add(location=location)
    rig = bpy.context.active_object
    rig.name = "Toy_Rig"

    bpy.ops.object.mode_set(mode='EDIT')
    eb = rig.data.edit_bones
    bone_root = eb[0]
    bone_root.name = "Root"
    bone_root.head = (location[0], location[1], location[2])
    bone_root.tail = (location[0], location[1], body_z)

    bone_head = eb.new("Head")
    bone_head.head = (location[0], location[1], body_z)
    bone_head.tail = (location[0], location[1], head_z + 0.3)
    bone_head.parent = bone_root

    bpy.ops.object.mode_set(mode='OBJECT')

    body.parent = rig
    body.parent_type = 'BONE'
    body.parent_bone = "Root"

    head.parent = rig
    head.parent_type = 'BONE'
    head.parent_bone = "Head"

    return rig, arm_r


def build_product_showcase_turntable(location=(0.95, 0, 0), product_img_path=None):
    """Build an elegant 3D rotating product turntable with actual product display."""
    mat_white = create_material("Pedestal_Base", (0.98, 0.98, 1.0, 1.0), roughness=0.15, specular=0.8)
    mat_gold = create_material("Pedestal_Gold", (0.98, 0.78, 0.25, 1.0), roughness=0.2, specular=0.9, metallic=0.7)

    # 1. Base Ring
    bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=0.95, depth=0.12, location=(location[0], location[1], location[2] + 0.06))
    base_ring = bpy.context.active_object
    base_ring.data.materials.append(mat_gold)

    # 2. Main Turntable Cylinder
    bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=0.88, depth=0.35, location=(location[0], location[1], location[2] + 0.24))
    pedestal = bpy.context.active_object
    pedestal.name = "Product_Turntable"
    pedestal.data.materials.append(mat_white)

    # 3. Product on Display
    prod_z = location[2] + 0.42 + 0.45
    if product_img_path and os.path.exists(product_img_path):
        # Build 3D Product Box / Display Card with image
        mat_prod = create_image_material("Product_Image_Mat", product_img_path)
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(location[0], location[1], prod_z))
        prod_box = bpy.context.active_object
        prod_box.name = "Showcase_Product_Hero"
        prod_box.scale = (0.75, 0.12, 0.95)
        prod_box.data.materials.append(mat_prod)
        prod_box.parent = pedestal
    else:
        # Elegant 3D Gift Box with Ribbon
        mat_gift = create_material("Gift_Box", (0.98, 0.85, 0.88, 1.0), roughness=0.25, specular=0.6)
        bpy.ops.mesh.primitive_cube_add(size=0.85, location=(location[0], location[1], prod_z))
        gift = bpy.context.active_object
        gift.name = "Showcase_Product_Gift"
        gift.data.materials.append(mat_gift)
        gift.parent = pedestal

        # Gold Ribbon
        bpy.ops.mesh.primitive_torus_add(major_radius=0.46, minor_radius=0.04, location=(location[0], location[1], prod_z))
        rib = bpy.context.active_object
        rib.data.materials.append(mat_gold)
        rib.parent = pedestal

    return pedestal


def build_desk_studio_environment(env_cfg):
    """Build cozy desk studio with soft lighting and blurred background props."""
    desk_col = env_cfg.get("desk_color", (0.88, 0.80, 0.70, 1.0))
    wall_col = env_cfg.get("wall_color", (0.95, 0.92, 0.96, 1.0))

    mat_desk = create_material("Desk_Wood", desk_col, roughness=0.4, specular=0.4)
    mat_wall = create_material("Studio_Wall", wall_col, roughness=0.8)
    mat_pot = create_material("Plant_Pot", (0.98, 0.98, 0.98, 1.0), roughness=0.3)
    mat_plant = create_material("Plant_Green", (0.35, 0.75, 0.40, 1.0), roughness=0.4)

    # 1. Desk Surface
    bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, 0))
    desk = bpy.context.active_object
    desk.data.materials.append(mat_desk)

    # 2. Back Wall (Blurred in background)
    bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 5.0, 4.0))
    wall = bpy.context.active_object
    wall.rotation_euler = (math.radians(90), 0, 0)
    wall.data.materials.append(mat_wall)

    # 3. Desk Plant Prop
    bpy.ops.mesh.primitive_cylinder_add(radius=0.25, depth=0.35, location=(-2.4, 1.2, 0.18))
    pot = bpy.context.active_object
    pot.data.materials.append(mat_pot)

    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.35, location=(-2.4, 1.2, 0.48))
    plant = bpy.context.active_object
    plant.data.materials.append(mat_plant)


def setup_commercial_lighting():
    """Setup bright commercial lighting with soft key, fill and rim lights."""
    # Key Window Light (Warm, bright daylight)
    bpy.ops.object.light_add(type='SUN', location=(-3, -3, 6))
    sun = bpy.context.active_object
    sun.name = "Key_Window_Light"
    sun.data.color = (1.0, 0.96, 0.92)
    sun.data.energy = 4.2
    sun.rotation_euler = (math.radians(45), math.radians(15), math.radians(-30))

    # Product Spotlight (Directly on product pedestal)
    bpy.ops.object.light_add(type='POINT', location=(0.95, -1.0, 2.5))
    spot = bpy.context.active_object
    spot.name = "Product_Spotlight"
    spot.data.color = (1.0, 1.0, 1.0)
    spot.data.energy = 55.0

    # Soft Fill Light
    bpy.ops.object.light_add(type='POINT', location=(-2.0, -1.5, 2.2))
    fill = bpy.context.active_object
    fill.name = "Mascot_Fill_Light"
    fill.data.color = (0.95, 0.90, 1.0)
    fill.data.energy = 40.0


def setup_commercial_camera(aspect_ratio="9:16", frame_count=72, res_x=None, res_y=None):
    """Setup camera with commercial product reveal dolly zoom."""
    scene = bpy.context.scene

    if aspect_ratio == "9:16":
        scene.render.resolution_x = int(res_x) if res_x else 720
        scene.render.resolution_y = int(res_y) if res_y else 1280
        cam_loc = (0.2, -4.6, 1.5)
    else:  # 16:9
        scene.render.resolution_x = int(res_x) if res_x else 1280
        scene.render.resolution_y = int(res_y) if res_y else 720
        cam_loc = (0.2, -3.8, 1.35)

    bpy.ops.object.camera_add(location=cam_loc)
    cam = bpy.context.active_object
    cam.name = "Product_Camera"
    cam.rotation_euler = (math.radians(82), 0, 0)
    cam.data.lens = 55
    scene.camera = cam

    # Enable Depth of Field (DoF) for shallow commercial blur
    cam.data.dof.use_dof = True
    cam.data.dof.focus_distance = 3.6
    cam.data.dof.aperture_fstop = 2.4

    # Commercial tracking motion
    for f in range(1, frame_count + 1):
        scene.frame_set(f)
        pct = f / frame_count
        # Gentle push-in dolly zoom
        cam.location.x = cam_loc[0] + math.sin(pct * math.pi) * 0.15
        cam.location.y = cam_loc[1] + pct * 0.5
        cam.location.z = cam_loc[2] + math.sin(pct * math.pi * 2) * 0.04
        cam.keyframe_insert(data_path="location", frame=f)


def animate_product_commercial(turntable_obj, rig_obj, arm_r_obj, frame_count=72):
    """Animate product rotation and mascot enthusiastic gestures."""
    p_bones = rig_obj.pose.bones
    b_root = p_bones.get("Root")
    b_head = p_bones.get("Head")

    for f in range(1, frame_count + 1):
        bpy.context.scene.frame_set(f)
        t = (f / 24.0)

        # 1. Product Turntable Spins smoothly 360 degrees
        rot_deg = (f / frame_count) * math.radians(360)
        turntable_obj.rotation_euler.z = rot_deg
        turntable_obj.keyframe_insert(data_path="rotation_euler", frame=f)

        # 2. Toy Mascot Gestures & Welcomes
        if b_head:
            b_head.rotation_euler.z = math.radians(-15) + math.sin(t * 3.0) * 0.12
            b_head.rotation_euler.x = math.sin(t * 2.5) * 0.08
            b_head.keyframe_insert(data_path="rotation_euler", frame=f)

        if b_root:
            b_root.location.z = abs(math.sin(t * 3.5)) * 0.06
            b_root.keyframe_insert(data_path="location", frame=f)

        if arm_r_obj:
            # Waving arm introducing product
            arm_r_obj.rotation_euler.x = math.radians(110) + math.sin(t * 4.5) * 0.35
            arm_r_obj.rotation_euler.z = math.radians(20) + math.sin(t * 4.5) * 0.30
            arm_r_obj.keyframe_insert(data_path="rotation_euler", frame=f)


def run_toy_ad_pipeline(spec_file_path):
    """Main entrypoint called by Blender for Toy Ad."""
    with open(spec_file_path, "r", encoding="utf-8") as f:
        spec = json.load(f)

    clear_scene()

    duration = float(spec.get("duration", 6.0))
    fps = int(spec.get("fps", 24))
    total_frames = int(duration * fps)
    aspect = spec.get("aspect", "9:16")
    res_x = spec.get("res_x", 720)
    res_y = spec.get("res_y", 1280)
    product_img = spec.get("product_image")

    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = total_frames
    scene.render.fps = fps

    char_id = spec.get("character", "vinyl_bear")
    char_cfg = TOY_CHARACTERS.get(char_id, TOY_CHARACTERS["vinyl_bear"])

    env_id = spec.get("environment", "cozy_desk")
    env_cfg = TOY_ENVIRONMENTS.get(env_id, TOY_ENVIRONMENTS["cozy_desk"])

    # 1. Build Scene
    rig_obj, arm_r = build_vinyl_toy_figure(char_cfg, location=(-1.0, 0, 0))
    turntable = build_product_showcase_turntable(location=(0.95, 0, 0), product_img_path=product_img)
    build_desk_studio_environment(env_cfg)
    setup_commercial_lighting()
    setup_commercial_camera(aspect_ratio=aspect, frame_count=total_frames, res_x=res_x, res_y=res_y)

    # 2. Animate
    animate_product_commercial(turntable, rig_obj, arm_r, frame_count=total_frames)

    # 3. Configure Fast NPR Render Settings
    render_engine = spec.get("render_engine", "BLENDER_WORKBENCH")
    scene.render.engine = render_engine

    if render_engine == "BLENDER_WORKBENCH":
        scene.display.shading.light = 'STUDIO'
        scene.display.shading.color_type = 'TEXTURE' if hasattr(scene.display.shading, 'color_type') else 'MATERIAL'
        scene.display.shading.show_shadows = True
        scene.display.shading.show_cavity = True
        scene.display.render_aa = 'FXAA'
    elif render_engine == "BLENDER_EEVEE_NEXT":
        if hasattr(scene.eevee, "taa_render_samples"):
            scene.eevee.taa_render_samples = 16

    output_pattern = spec["output_frames_pattern"]
    scene.render.filepath = output_pattern
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'

    print(f"STARTING_TOY_AD_RENDER total_frames={total_frames} engine={render_engine}")
    bpy.ops.render.render(animation=True)
    print("TOY_AD_RENDER_COMPLETE")


if __name__ == "__main__":
    if "--spec" in sys.argv:
        idx = sys.argv.index("--spec")
        spec_path = sys.argv[idx + 1]
        run_toy_ad_pipeline(spec_path)
