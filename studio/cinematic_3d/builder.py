"""Blender 4.2 LTS headless script for 3D Cinematic Cartoon Animation."""

import json
import math
import os
import sys
from pathlib import Path

import bpy

# Add directory to sys.path to import presets
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.append(str(SCRIPT_DIR))

from presets import (
    CINEMATIC_CHARACTERS,
    CINEMATIC_ENVIRONMENTS,
    CINEMATIC_LIGHTING,
    DEFAULT_CINEMATIC_PROMPT,
)


def clear_scene():
    """Wipe all existing objects, materials, and collections."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if not bpy.data.scenes:
        bpy.ops.scene.new(type='EMPTY')


def create_material(name, color=(1, 1, 1, 1), roughness=0.3, specular=0.5, metallic=0.0):
    """Create a clean stylized material."""
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


def build_tropical_fish(char_cfg, location=(0, 0, 1.2)):
    """Build a cute cinematic 3D tropical clownfish with rigged fins."""
    col_primary = char_cfg.get("primary_color", (1.0, 0.45, 0.15, 1.0))
    col_secondary = char_cfg.get("secondary_color", (0.98, 0.98, 1.0, 1.0))
    col_stripe = char_cfg.get("stripe_color", (0.12, 0.10, 0.15, 1.0))
    col_eye = char_cfg.get("eye_color", (0.15, 0.20, 0.35, 1.0))
    col_fin = char_cfg.get("fin_color", (1.0, 0.55, 0.25, 0.85))

    mat_body = create_material("Fish_Body", col_primary, roughness=0.25, specular=0.6)
    mat_white = create_material("Fish_White", col_secondary, roughness=0.3, specular=0.5)
    mat_stripe = create_material("Fish_Stripe", col_stripe, roughness=0.4, specular=0.3)
    mat_fin = create_material("Fish_Fin", col_fin, roughness=0.2, specular=0.7)
    mat_eye = create_material("Fish_Eye", col_eye, roughness=0.1, specular=0.9)
    mat_eye_white = create_material("Fish_Eye_White", (1.0, 1.0, 1.0, 1.0), roughness=0.1, specular=0.9)
    mat_highlight = create_material("Fish_Eye_HL", (1.0, 1.0, 1.0, 1.0), roughness=0.05, specular=1.0)

    # 1. Main Fish Body (Smooth teardrop/ellipsoid)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=16, radius=0.65, location=location)
    body = bpy.context.active_object
    body.name = "Fish_Main_Body"
    body.scale = (0.75, 1.45, 0.95)
    bpy.ops.object.shade_smooth()
    body.data.materials.append(mat_body)

    # 2. White Stripes on Body
    # Front Stripe
    bpy.ops.mesh.primitive_torus_add(major_radius=0.55, minor_radius=0.08, location=(location[0], location[1] + 0.15, location[2]))
    stripe1 = bpy.context.active_object
    stripe1.scale = (0.8, 1.0, 1.1)
    stripe1.rotation_euler = (0, math.radians(90), 0)
    stripe1.data.materials.append(mat_white)
    stripe1.parent = body

    # Mid Stripe
    bpy.ops.mesh.primitive_torus_add(major_radius=0.48, minor_radius=0.07, location=(location[0], location[1] - 0.25, location[2]))
    stripe2 = bpy.context.active_object
    stripe2.scale = (0.75, 1.0, 1.0)
    stripe2.rotation_euler = (0, math.radians(90), 0)
    stripe2.data.materials.append(mat_white)
    stripe2.parent = body

    # 3. Big Sparkling Eyes
    for side in (-1, 1):
        eye_x = location[0] + side * 0.38
        eye_y = location[1] + 0.55
        eye_z = location[2] + 0.12

        # Eye socket base
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.18, location=(eye_x, eye_y, eye_z))
        s_base = bpy.context.active_object
        s_base.scale = (0.8, 1.0, 1.0)
        s_base.data.materials.append(mat_eye_white)
        s_base.parent = body

        # Iris
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.12, location=(eye_x + side * 0.05, eye_y + 0.08, eye_z))
        iris = bpy.context.active_object
        iris.scale = (0.7, 0.8, 0.9)
        iris.data.materials.append(mat_eye)
        iris.parent = body

        # Eye Highlight (Sparkle)
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.045, location=(eye_x + side * 0.08, eye_y + 0.14, eye_z + 0.04))
        hl = bpy.context.active_object
        hl.data.materials.append(mat_highlight)
        hl.parent = body

    # 4. Caudal Tail Fin (Fan shape)
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.45, depth=0.04, location=(location[0], location[1] - 1.15, location[2]))
    tail = bpy.context.active_object
    tail.name = "Fish_Tail_Fin"
    tail.scale = (0.2, 0.8, 1.1)
    tail.rotation_euler = (math.radians(90), 0, 0)
    tail.data.materials.append(mat_fin)

    # 5. Dorsal Fin (Top fin)
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.35, depth=0.04, location=(location[0], location[1] - 0.1, location[2] + 0.65))
    dorsal = bpy.context.active_object
    dorsal.name = "Fish_Dorsal_Fin"
    dorsal.scale = (0.15, 0.9, 0.6)
    dorsal.rotation_euler = (0, math.radians(90), 0)
    dorsal.data.materials.append(mat_fin)
    dorsal.parent = body

    # 6. Pectoral Fins (Left & Right chest fins)
    pectoral_l = None
    pectoral_r = None
    for side in (-1, 1):
        fx = location[0] + side * 0.48
        fy = location[1] + 0.1
        fz = location[2] - 0.12
        bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.22, depth=0.03, location=(fx, fy, fz))
        pfin = bpy.context.active_object
        pfin.name = f"Fish_Pectoral_{'L' if side < 0 else 'R'}"
        pfin.scale = (0.6, 0.9, 0.15)
        pfin.rotation_euler = (math.radians(20), math.radians(side * 45), math.radians(side * 25))
        pfin.data.materials.append(mat_fin)
        pfin.parent = body
        if side < 0:
            pectoral_l = pfin
        else:
            pectoral_r = pfin

    # 7. Create Armature Rig for Fish Swimming Animation
    bpy.ops.object.armature_add(location=location)
    arm = bpy.context.active_object
    arm.name = "Fish_Armature"

    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm.data.edit_bones
    bone_root = eb[0]
    bone_root.name = "Root"
    bone_root.head = (location[0], location[1] + 0.5, location[2])
    bone_root.tail = (location[0], location[1], location[2])

    bone_mid = eb.new("Spine_Mid")
    bone_mid.head = (location[0], location[1], location[2])
    bone_mid.tail = (location[0], location[1] - 0.6, location[2])
    bone_mid.parent = bone_root

    bone_tail = eb.new("Tail_Fin")
    bone_tail.head = (location[0], location[1] - 0.6, location[2])
    bone_tail.tail = (location[0], location[1] - 1.25, location[2])
    bone_tail.parent = bone_mid

    bpy.ops.object.mode_set(mode='OBJECT')

    body.parent = arm
    body.parent_type = 'BONE'
    body.parent_bone = "Root"

    tail.parent = arm
    tail.parent_type = 'BONE'
    tail.parent_bone = "Tail_Fin"

    return arm, body, pectoral_l, pectoral_r


def build_underwater_environment(env_cfg):
    """Build a vibrant tropical coral reef environment with corals and bubbles."""
    sand_col = env_cfg.get("sand_color", (0.92, 0.85, 0.70, 1.0))
    coral_cols = env_cfg.get("coral_colors", [(1.0, 0.4, 0.5, 1.0), (0.35, 0.85, 0.75, 1.0)])

    mat_sand = create_material("Sea_Sand", sand_col, roughness=0.8, specular=0.2)
    mat_bubble = create_material("Bubble_Glass", (0.85, 0.95, 1.0, 0.6), roughness=0.05, specular=1.0)

    # 1. Ocean Floor Sand Plane
    bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0, -1.2))
    sand = bpy.context.active_object
    sand.name = "Ocean_Floor"
    sand.data.materials.append(mat_sand)

    # 2. Corals and Sea Anemones
    coral_positions = [
        (-2.2, -0.8, -0.8, 0),
        (2.4, -0.5, -0.8, 1),
        (-1.8, 2.2, -0.8, 2),
        (2.1, 1.8, -0.8, 3),
        (-3.0, 0.8, -0.7, 1),
        (3.2, 0.2, -0.7, 0),
    ]

    for i, (cx, cy, cz, c_idx) in enumerate(coral_positions):
        mat_c = create_material(f"Coral_Mat_{i}", coral_cols[c_idx % len(coral_cols)], roughness=0.35, specular=0.5)
        # Coral base mound
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.55, location=(cx, cy, cz))
        c_mound = bpy.context.active_object
        c_mound.scale = (1.0, 1.0, 0.65)
        c_mound.data.materials.append(mat_c)

        # Coral branches
        for b in range(4):
            ang = b * (math.pi / 2) + 0.3
            bx = cx + math.cos(ang) * 0.3
            by = cy + math.sin(ang) * 0.3
            bz = cz + 0.45
            bpy.ops.mesh.primitive_cylinder_add(radius=0.12, depth=0.6, location=(bx, by, bz))
            branch = bpy.context.active_object
            branch.rotation_euler = (math.sin(ang) * 0.25, math.cos(ang) * 0.25, 0)
            branch.data.materials.append(mat_c)

    # 3. Floating Bubbles (Animated later or static sparkles)
    bubble_coords = [
        (-0.8, 0.5, 0.2), (0.9, -0.3, 0.8), (-1.2, -0.8, 1.4),
        (0.6, 1.2, 1.6), (-0.4, 1.8, 0.9), (1.4, 0.8, 0.3),
        (-1.5, 0.2, 2.1), (0.3, -1.0, 1.8),
    ]
    for idx, (bx, by, bz) in enumerate(bubble_coords):
        r = 0.04 + (idx % 4) * 0.02
        bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=(bx, by, bz))
        b_obj = bpy.context.active_object
        b_obj.name = f"Bubble_{idx}"
        b_obj.data.materials.append(mat_bubble)


def build_beach_or_forest_environment(env_cfg):
    """Build beach or forest environment when chosen."""
    theme = env_cfg.get("theme", "beach")
    if theme == "beach":
        mat_sand = create_material("Beach_Sand", (0.96, 0.88, 0.72, 1.0), roughness=0.7)
        mat_water = create_material("Sea_Water", (0.25, 0.70, 0.85, 0.8), roughness=0.1, specular=0.9)
        mat_palm = create_material("Palm_Trunk", (0.50, 0.38, 0.25, 1.0), roughness=0.8)
        mat_leaves = create_material("Palm_Leaves", (0.35, 0.75, 0.25, 1.0), roughness=0.5)

        bpy.ops.mesh.primitive_plane_add(size=25, location=(0, 0, 0))
        sand = bpy.context.active_object
        sand.data.materials.append(mat_sand)

        bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 4.0, -0.05))
        water = bpy.context.active_object
        water.data.materials.append(mat_water)

        # Palm tree
        bpy.ops.mesh.primitive_cylinder_add(radius=0.2, depth=3.0, location=(-3.0, 1.0, 1.5))
        trunk = bpy.context.active_object
        trunk.rotation_euler = (0, math.radians(12), 0)
        trunk.data.materials.append(mat_palm)

        bpy.ops.mesh.primitive_uv_sphere_add(radius=1.2, location=(-2.4, 1.0, 3.2))
        canopy = bpy.context.active_object
        canopy.scale = (1.5, 1.5, 0.4)
        canopy.data.materials.append(mat_leaves)

    else:  # forest
        mat_ground = create_material("Forest_Ground", (0.42, 0.65, 0.35, 1.0), roughness=0.8)
        mat_bark = create_material("Tree_Bark", (0.45, 0.32, 0.22, 1.0), roughness=0.8)
        mat_leaves = create_material("Tree_Leaves", (0.40, 0.78, 0.35, 1.0), roughness=0.5)

        bpy.ops.mesh.primitive_plane_add(size=25, location=(0, 0, 0))
        ground = bpy.context.active_object
        ground.data.materials.append(mat_ground)

        for tx, ty in [(-2.5, 1.5), (2.8, 1.2), (-1.8, 3.0), (2.0, 3.2)]:
            bpy.ops.mesh.primitive_cylinder_add(radius=0.25, depth=2.8, location=(tx, ty, 1.4))
            tree = bpy.context.active_object
            tree.data.materials.append(mat_bark)
            bpy.ops.mesh.primitive_uv_sphere_add(radius=1.1, location=(tx, ty, 3.0))
            leaves = bpy.context.active_object
            leaves.data.materials.append(mat_leaves)


def setup_cinematic_lighting(light_cfg):
    """Setup multi-point cinematic lighting with warm sun and ambient fill."""
    sun_col = light_cfg.get("sun_color", (0.35, 0.80, 1.0))
    sun_energy = light_cfg.get("sun_energy", 3.5)
    sun_rot = light_cfg.get("sun_rot", (0.45, 0.2, 0.6))

    bpy.ops.object.light_add(type='SUN', location=(0, 0, 8))
    sun = bpy.context.active_object
    sun.name = "Cinematic_Key_Sun"
    sun.data.color = sun_col
    sun.data.energy = sun_energy
    sun.rotation_euler = sun_rot

    # Ambient / Caustic fill light
    bpy.ops.object.light_add(type='POINT', location=(1.5, -2.0, 2.5))
    fill = bpy.context.active_object
    fill.name = "Cinematic_Fill_Point"
    fill.data.color = (0.6, 0.9, 1.0)
    fill.data.energy = 45.0

    # Back / Rim Light
    bpy.ops.object.light_add(type='POINT', location=(-2.0, 2.5, 3.0))
    rim = bpy.context.active_object
    rim.name = "Cinematic_Rim_Light"
    rim.data.color = (1.0, 0.9, 0.7)
    rim.data.energy = 60.0


def setup_cinematic_camera(aspect_ratio="16:9", frame_count=72, res_x=None, res_y=None):
    """Configure cinematic tracking camera with smooth orbit/pan."""
    scene = bpy.context.scene

    if aspect_ratio == "9:16":
        scene.render.resolution_x = int(res_x) if res_x else 720
        scene.render.resolution_y = int(res_y) if res_y else 1280
        cam_loc = (0, -4.8, 1.4)
    else:  # 16:9
        scene.render.resolution_x = int(res_x) if res_x else 1280
        scene.render.resolution_y = int(res_y) if res_y else 720
        cam_loc = (0, -3.8, 1.3)

    bpy.ops.object.camera_add(location=cam_loc)
    cam = bpy.context.active_object
    cam.name = "Cinematic_Camera"
    cam.rotation_euler = (math.radians(82), 0, 0)
    cam.data.lens = 50
    scene.camera = cam

    # Animate gentle cinematic camera pan & orbit
    for f in range(1, frame_count + 1):
        scene.frame_set(f)
        pct = f / frame_count
        # Smooth orbital drift
        angle = math.sin(pct * math.pi) * 0.4
        cam.location.x = math.sin(angle) * 3.8
        cam.location.y = -math.cos(angle) * 3.8
        cam.location.z = cam_loc[2] + math.sin(pct * math.pi * 2) * 0.12
        cam.rotation_euler.z = angle * 0.7
        cam.keyframe_insert(data_path="location", frame=f)
        cam.keyframe_insert(data_path="rotation_euler", frame=f)


def animate_fish_swimming(arm_obj, pectoral_l, pectoral_r, frame_count=72, speed=3.5):
    """Animate natural harmonic undulating swimming motion for tropical fish."""
    p_bones = arm_obj.pose.bones
    bone_root = p_bones.get("Root")
    bone_mid = p_bones.get("Spine_Mid")
    bone_tail = p_bones.get("Tail_Fin")

    for f in range(1, frame_count + 1):
        bpy.context.scene.frame_set(f)
        t = (f / 24.0) * speed

        # 1. Forward / curved path with gentle bobbing
        if bone_root:
            bone_root.location.x = math.sin(t * 0.4) * 0.35
            bone_root.location.y = math.cos(t * 0.4) * 0.25
            bone_root.location.z = math.sin(t * 1.8) * 0.08
            bone_root.rotation_euler.z = math.cos(t * 0.4) * 0.25
            bone_root.rotation_euler.x = math.sin(t * 1.8) * 0.05
            bone_root.keyframe_insert(data_path="location", frame=f)
            bone_root.keyframe_insert(data_path="rotation_euler", frame=f)

        # 2. Spine Wave (Undulation)
        if bone_mid:
            bone_mid.rotation_euler.z = math.sin(t * 2.0) * 0.32
            bone_mid.keyframe_insert(data_path="rotation_euler", frame=f)

        # 3. Tail Fin Whip (Phase shifted wave)
        if bone_tail:
            bone_tail.rotation_euler.z = math.sin(t * 2.0 - 0.9) * 0.55
            bone_tail.keyframe_insert(data_path="rotation_euler", frame=f)

        # 4. Pectoral Fin Flapping for stabilization
        if pectoral_l:
            pectoral_l.rotation_euler.z = math.radians(-25) + math.sin(t * 2.0) * 0.25
            pectoral_l.keyframe_insert(data_path="rotation_euler", frame=f)
        if pectoral_r:
            pectoral_r.rotation_euler.z = math.radians(25) - math.sin(t * 2.0) * 0.25
            pectoral_r.keyframe_insert(data_path="rotation_euler", frame=f)


def run_cinematic_pipeline(spec_file_path):
    """Main entrypoint called by Blender."""
    with open(spec_file_path, "r", encoding="utf-8") as f:
        spec = json.load(f)

    clear_scene()

    duration = float(spec.get("duration", 6.0))
    fps = int(spec.get("fps", 24))
    total_frames = int(duration * fps)
    aspect = spec.get("aspect", "16:9")
    res_x = spec.get("res_x", 1280)
    res_y = spec.get("res_y", 720)

    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = total_frames
    scene.render.fps = fps

    # 1. Resolve Configs
    char_id = spec.get("character", "tropical_fish")
    char_cfg = CINEMATIC_CHARACTERS.get(char_id, CINEMATIC_CHARACTERS["tropical_fish"])

    env_id = spec.get("environment", "underwater")
    env_cfg = CINEMATIC_ENVIRONMENTS.get(env_id, CINEMATIC_ENVIRONMENTS["underwater"])

    light_id = env_cfg.get("lighting", "deep_ocean")
    light_cfg = CINEMATIC_LIGHTING.get(light_id, CINEMATIC_LIGHTING["deep_ocean"])

    # 2. Build 3D Models
    arm_obj, body_obj, pec_l, pec_r = build_tropical_fish(char_cfg, location=(0, 0, 1.2))

    if env_cfg.get("theme") == "ocean":
        build_underwater_environment(env_cfg)
    else:
        build_beach_or_forest_environment(env_cfg)

    setup_cinematic_lighting(light_cfg)
    setup_cinematic_camera(aspect_ratio=aspect, frame_count=total_frames, res_x=res_x, res_y=res_y)

    # 3. Animate
    motion = spec.get("action", char_cfg.get("default_motion", "swimming"))
    animate_fish_swimming(arm_obj, pec_l, pec_r, frame_count=total_frames, speed=3.2)

    # 4. Render Engine Configuration
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

    print(f"STARTING_CINEMATIC_RENDER total_frames={total_frames} engine={render_engine}")
    bpy.ops.render.render(animation=True)
    print("CINEMATIC_RENDER_COMPLETE")


if __name__ == "__main__":
    if "--spec" in sys.argv:
        idx = sys.argv.index("--spec")
        spec_path = sys.argv[idx + 1]
        run_cinematic_pipeline(spec_path)
