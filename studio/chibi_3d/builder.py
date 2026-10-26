"""Blender scene builder and animator for 3D Chibi Pastel Animation.
This script is executed directly within Blender's Python runtime.
"""
import sys
import os
import json
import math

try:
    import bpy
    import mathutils
except ImportError:
    bpy = None


def make_material(name, color_rgba, roughness=0.35, specular=0.5):
    """Create or return an anti-aliased pastel Principled BSDF material."""
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        if "Base Color" in bsdf.inputs:
            bsdf.inputs["Base Color"].default_value = color_rgba
        if "Roughness" in bsdf.inputs:
            bsdf.inputs["Roughness"].default_value = roughness
        if "Specular IOR Level" in bsdf.inputs:
            bsdf.inputs["Specular IOR Level"].default_value = specular
        elif "Specular" in bsdf.inputs:
            bsdf.inputs["Specular"].default_value = specular
    return mat


def build_chibi_character(char_cfg, location=(0, 0, 0)):
    """Create a high-quality 3D Chibi character mesh with an animated Armature."""
    skin_mat = make_material("ChibiSkin_" + char_cfg["id"], char_cfg["skin_tone"], roughness=0.45)
    blush_mat = make_material("ChibiBlush_" + char_cfg["id"], char_cfg["cheek_blush"], roughness=0.6)
    hair_mat = make_material("ChibiHair_" + char_cfg["id"], char_cfg["hair_color"], roughness=0.5)
    dress_mat = make_material("ChibiDress_" + char_cfg["id"], char_cfg["dress_color"], roughness=0.35)
    eye_mat = make_material("ChibiEye_" + char_cfg["id"], char_cfg["eye_color"], roughness=0.1)
    sparkle_mat = make_material("ChibiSparkle", (1.0, 1.0, 1.0, 1.0), roughness=0.0)

    # 1. Create Armature
    bpy.ops.object.armature_add(location=location)
    arm_obj = bpy.context.active_object
    arm_obj.name = "Armature_" + char_cfg["id"]
    arm_data = arm_obj.data
    arm_data.name = "ArmData_" + char_cfg["id"]

    # Configure Armature Bones in Edit Mode
    bpy.ops.object.mode_set(mode='EDIT')
    bones = arm_data.edit_bones
    root_bone = bones[0]
    root_bone.name = "Root"
    root_bone.head = (0, 0, 0.8)
    root_bone.tail = (0, 0, 1.4)

    # Spine & Head
    head_bone = bones.new("Head")
    head_bone.head = (0, 0, 1.4)
    head_bone.tail = (0, 0, 2.6)
    head_bone.parent = root_bone

    # Left Arm
    arm_l = bones.new("Arm_L")
    arm_l.head = (-0.45, 0, 1.35)
    arm_l.tail = (-0.85, 0, 1.0)
    arm_l.parent = root_bone

    # Right Arm
    arm_r = bones.new("Arm_R")
    arm_r.head = (0.45, 0, 1.35)
    arm_r.tail = (0.85, 0, 1.0)
    arm_r.parent = root_bone

    # Left Leg
    leg_l = bones.new("Leg_L")
    leg_l.head = (-0.25, 0, 0.75)
    leg_l.tail = (-0.25, 0, 0.15)
    leg_l.parent = root_bone

    # Right Leg
    leg_r = bones.new("Leg_R")
    leg_r.head = (0.25, 0, 0.75)
    leg_r.tail = (0.25, 0, 0.15)
    leg_r.parent = root_bone

    bpy.ops.object.mode_set(mode='OBJECT')

    # Character Mesh Parts container
    parts = []

    # 2. Big Cute Head
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.88, location=(location[0], location[1], location[2] + 2.2))
    head = bpy.context.active_object
    head.name = f"{char_cfg['id']}_Head"
    head.scale = (1.06, 0.96, 0.94)
    head.data.materials.append(skin_mat)
    bpy.ops.object.shade_smooth()
    parts.append((head, "Head"))

    # Cheeks
    for side, x_off in [("L", -0.50), ("R", 0.50)]:
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.17, location=(location[0] + x_off, location[1] - 0.68, location[2] + 2.05))
        blush = bpy.context.active_object
        blush.name = f"{char_cfg['id']}_Blush_{side}"
        blush.scale = (1.0, 0.3, 0.55)
        blush.data.materials.append(blush_mat)
        bpy.ops.object.shade_smooth()
        parts.append((blush, "Head"))

    # Big Sparkling Eyes
    for side, x_off in [("L", -0.34), ("R", 0.34)]:
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.21, location=(location[0] + x_off, location[1] - 0.75, location[2] + 2.26))
        eye = bpy.context.active_object
        eye.name = f"{char_cfg['id']}_Eye_{side}"
        eye.scale = (1.0, 0.28, 1.25)
        eye.data.materials.append(eye_mat)
        bpy.ops.object.shade_smooth()
        parts.append((eye, "Head"))

        # Highlights
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.065, location=(location[0] + x_off + (0.05 if side == 'R' else -0.05), location[1] - 0.81, location[2] + 2.36))
        sp = bpy.context.active_object
        sp.name = f"{char_cfg['id']}_Sparkle_{side}"
        sp.scale = (1.0, 0.3, 1.0)
        sp.data.materials.append(sparkle_mat)
        parts.append((sp, "Head"))

    # Mouth for Lip-Sync
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.09, location=(location[0], location[1] - 0.78, location[2] + 1.88))
    mouth = bpy.context.active_object
    mouth.name = f"{char_cfg['id']}_Mouth"
    mouth.scale = (1.0, 0.25, 0.5)
    mouth.data.materials.append(blush_mat)
    bpy.ops.object.shade_smooth()
    parts.append((mouth, "Head"))

    # Hair Styles
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.96, location=(location[0], location[1] + 0.08, location[2] + 2.32))
    hair = bpy.context.active_object
    hair.name = f"{char_cfg['id']}_Hair"
    hair.scale = (1.08, 1.02, 0.98)
    hair.data.materials.append(hair_mat)
    bpy.ops.object.shade_smooth()
    parts.append((hair, "Head"))

    if char_cfg.get("hair_style") == "twin_buns":
        for side, x_off in [("L", -0.92), ("R", 0.92)]:
            bpy.ops.mesh.primitive_uv_sphere_add(radius=0.36, location=(location[0] + x_off, location[1] + 0.1, location[2] + 2.88))
            bun = bpy.context.active_object
            bun.name = f"{char_cfg['id']}_Bun_{side}"
            bun.data.materials.append(hair_mat)
            bpy.ops.object.shade_smooth()
            parts.append((bun, "Head"))
    elif char_cfg.get("hair_style") == "long_ears":
        for side, x_off in [("L", -0.35), ("R", 0.35)]:
            bpy.ops.mesh.primitive_uv_sphere_add(radius=0.22, location=(location[0] + x_off, location[1], location[2] + 3.2))
            ear = bpy.context.active_object
            ear.name = f"{char_cfg['id']}_Ear_{side}"
            ear.scale = (0.5, 0.4, 2.4)
            ear.data.materials.append(hair_mat)
            bpy.ops.object.shade_smooth()
            parts.append((ear, "Head"))

    # Body / Dress
    bpy.ops.mesh.primitive_cone_add(radius1=0.68, radius2=0.32, depth=1.05, location=(location[0], location[1], location[2] + 1.15))
    dress = bpy.context.active_object
    dress.name = f"{char_cfg['id']}_Body"
    dress.data.materials.append(dress_mat)
    bpy.ops.object.shade_smooth()
    parts.append((dress, "Root"))

    # Arms
    for side, bone_name, x_off, rot_y in [("L", "Arm_L", -0.52, -32), ("R", "Arm_R", 0.52, 32)]:
        bpy.ops.mesh.primitive_cylinder_add(radius=0.11, depth=0.55, location=(location[0] + x_off, location[1], location[2] + 1.25))
        arm = bpy.context.active_object
        arm.name = f"{char_cfg['id']}_ArmMesh_{side}"
        arm.rotation_euler = (0, math.radians(rot_y), 0)
        arm.data.materials.append(skin_mat)
        bpy.ops.object.shade_smooth()
        parts.append((arm, bone_name))

    # Legs
    for side, bone_name, x_off in [("L", "Leg_L", -0.24), ("R", "Leg_R", 0.24)]:
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.17, location=(location[0] + x_off, location[1], location[2] + 0.35))
        leg = bpy.context.active_object
        leg.name = f"{char_cfg['id']}_LegMesh_{side}"
        leg.scale = (0.9, 1.4, 0.9)
        leg.data.materials.append(dress_mat)
        bpy.ops.object.shade_smooth()
        parts.append((leg, bone_name))

    # Parent parts to Armature Bones
    for obj, bone_target in parts:
        obj.parent = arm_obj
        obj.parent_type = 'BONE'
        obj.parent_bone = bone_target

    return arm_obj, mouth


def build_environment(env_cfg, palette):
    """Build a charming 3D pastel environment."""
    env_id = env_cfg["id"]

    # Ground terrain
    ground_mat = make_material("GroundMat", palette["ground"], roughness=0.8)
    bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, 0.05))
    ground = bpy.context.active_object
    ground.name = "Env_Ground"
    ground.data.materials.append(ground_mat)

    # Background pastel props according to theme
    if env_id in ("garden_house", "fantasy_town"):
        # Cozy House in the background
        house_mat = make_material("HouseWall", palette["secondary"], roughness=0.5)
        roof_mat = make_material("HouseRoof", palette["primary"], roughness=0.4)

        bpy.ops.mesh.primitive_cube_add(size=3.0, location=(0, 6.0, 1.5))
        house = bpy.context.active_object
        house.name = "House_Body"
        house.data.materials.append(house_mat)

        # Roof
        bpy.ops.mesh.primitive_cone_add(radius1=2.8, depth=1.8, location=(0, 6.0, 3.8))
        roof = bpy.context.active_object
        roof.name = "House_Roof"
        roof.rotation_euler = (0, 0, math.radians(45))
        roof.data.materials.append(roof_mat)

        # Cute trees
        tree_leaf = make_material("TreeLeaf", (0.75, 0.94, 0.82, 1.0), roughness=0.6)
        tree_trunk = make_material("TreeTrunk", (0.65, 0.50, 0.40, 1.0), roughness=0.8)
        for tx, ty in [(-4.5, 4.0), (4.5, 4.2), (-6.0, 1.5), (6.0, 2.0)]:
            bpy.ops.mesh.primitive_cylinder_add(radius=0.25, depth=2.0, location=(tx, ty, 1.0))
            trunk = bpy.context.active_object
            trunk.data.materials.append(tree_trunk)

            bpy.ops.mesh.primitive_uv_sphere_add(radius=1.2, location=(tx, ty, 2.6))
            leaves = bpy.context.active_object
            leaves.data.materials.append(tree_leaf)
            bpy.ops.object.shade_smooth()

    elif env_id == "fairy_forest":
        # Enchanted Pastel Forest
        mush_cap = make_material("MushCap", palette["primary"], roughness=0.3)
        mush_stem = make_material("MushStem", (0.95, 0.95, 0.90, 1.0), roughness=0.5)
        for mx, my, sz in [(-2.5, 2.5, 1.0), (2.8, 3.2, 0.8), (3.5, 1.2, 0.6)]:
            bpy.ops.mesh.primitive_cylinder_add(radius=0.18 * sz, depth=1.2 * sz, location=(mx, my, 0.6 * sz))
            stem = bpy.context.active_object
            stem.data.materials.append(mush_stem)

            bpy.ops.mesh.primitive_uv_sphere_add(radius=0.7 * sz, location=(mx, my, 1.2 * sz))
            cap = bpy.context.active_object
            cap.scale = (1.0, 1.0, 0.6)
            cap.data.materials.append(mush_cap)
            bpy.ops.object.shade_smooth()

    # Soft Pastel Sky World Background
    world = bpy.context.scene.world
    if not world:
        world = bpy.data.worlds.new("PastelWorld")
        bpy.context.scene.world = world
    world.use_nodes = True
    bg_node = world.node_tree.nodes.get("Background")
    if bg_node:
        bg_node.inputs["Color"].default_value = palette["sky"]
        bg_node.inputs["Strength"].default_value = 1.2


def setup_pastel_lighting(palette):
    """Setup 3-point soft cinematic pastel lighting."""
    # Key Light (Sun)
    bpy.ops.object.light_add(type='SUN', location=(5, -6, 7))
    sun = bpy.context.active_object
    sun.data.energy = 3.6
    sun.data.color = palette["sunlight"]

    # Fill Light (Ambient)
    bpy.ops.object.light_add(type='POINT', location=(-5, -3, 3.5))
    fill = bpy.context.active_object
    fill.data.energy = 160.0
    fill.data.color = palette["ambient"]

    # Rim Light
    bpy.ops.object.light_add(type='POINT', location=(0, 4.5, 4.5))
    rim = bpy.context.active_object
    rim.data.energy = 240.0
    rim.data.color = (1.0, 0.90, 0.85)


def setup_camera(aspect_ratio="9:16", frame_count=72, res_x=None, res_y=None):
    """Setup camera with smooth framing and aspect ratio."""
    scene = bpy.context.scene
    if aspect_ratio == "9:16":
        scene.render.resolution_x = int(res_x) if res_x else 720
        scene.render.resolution_y = int(res_y) if res_y else 1280
        cam_loc = (0, -5.6, 1.9)
    elif aspect_ratio == "1:1":
        scene.render.resolution_x = int(res_x) if res_x else 1080
        scene.render.resolution_y = int(res_y) if res_y else 1080
        cam_loc = (0, -5.0, 1.85)
    else:  # 16:9
        scene.render.resolution_x = int(res_x) if res_x else 1280
        scene.render.resolution_y = int(res_y) if res_y else 720
        cam_loc = (0, -4.5, 1.8)

    bpy.ops.object.camera_add(location=cam_loc)
    cam = bpy.context.active_object
    cam.name = "Chibi_Cinematic_Camera"
    cam.rotation_euler = (math.radians(85), 0, 0)
    cam.data.lens = 45
    scene.camera = cam

    # Animate gentle camera tracking/drift
    for f in range(1, frame_count + 1):
        scene.frame_set(f)
        pct = f / frame_count
        cam.location.x = math.sin(pct * math.pi) * 0.3
        cam.location.z = cam_loc[2] + math.sin(pct * math.pi * 2) * 0.08
        cam.keyframe_insert(data_path="location", frame=f)

    return cam


def apply_action_animation(arm_obj, mouth_obj, action_name="wave", start_frame=1, end_frame=72):
    """Keyframe character actions (walk, run, wave, talk, jump, idle)."""
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode='POSE')
    pose = arm_obj.pose

    root = pose.bones.get("Root")
    head = pose.bones.get("Head")
    arm_l = pose.bones.get("Arm_L")
    arm_r = pose.bones.get("Arm_R")
    leg_l = pose.bones.get("Leg_L")
    leg_r = pose.bones.get("Leg_R")

    for f in range(start_frame, end_frame + 1):
        bpy.context.scene.frame_set(f)
        t = ((f - start_frame) / 24.0) * math.pi * 2.0

        # Natural Idle Rhythm
        if root:
            root.location.z = math.sin(t * 2) * 0.03
            root.keyframe_insert(data_path="location", frame=f)

        if head:
            head.rotation_euler.z = math.sin(t * 1.2) * 0.12
            head.rotation_euler.y = math.sin(t * 1.8) * 0.06
            head.keyframe_insert(data_path="rotation_euler", frame=f)

        # Action specific pose logic
        if action_name in ("wave", "talk", "greet"):
            # Waving right arm
            if arm_r:
                arm_r.rotation_euler.x = math.radians(110) + math.sin(t * 4) * 0.35
                arm_r.rotation_euler.z = math.sin(t * 4) * 0.4
                arm_r.keyframe_insert(data_path="rotation_euler", frame=f)
            if arm_l:
                arm_l.rotation_euler.x = math.sin(t * 1.5) * 0.1
                arm_l.keyframe_insert(data_path="rotation_euler", frame=f)

        elif action_name in ("walk", "move"):
            # Walking cycle
            if root:
                root.location.y = -0.05 * (f - start_frame) / 24.0
                root.location.z = abs(math.sin(t * 2)) * 0.06
                root.keyframe_insert(data_path="location", frame=f)
            if leg_l:
                leg_l.rotation_euler.x = math.sin(t * 2) * 0.5
                leg_l.keyframe_insert(data_path="rotation_euler", frame=f)
            if leg_r:
                leg_r.rotation_euler.x = -math.sin(t * 2) * 0.5
                leg_r.keyframe_insert(data_path="rotation_euler", frame=f)
            if arm_l:
                arm_l.rotation_euler.x = -math.sin(t * 2) * 0.4
                arm_l.keyframe_insert(data_path="rotation_euler", frame=f)
            if arm_r:
                arm_r.rotation_euler.x = math.sin(t * 2) * 0.4
                arm_r.keyframe_insert(data_path="rotation_euler", frame=f)

        elif action_name in ("jump", "happy", "cheer"):
            # Celebratory bounce / jump
            jump_h = abs(math.sin(t * 3)) * 0.25
            if root:
                root.location.z = jump_h
                root.keyframe_insert(data_path="location", frame=f)
            if arm_l and arm_r:
                arm_l.rotation_euler.x = math.radians(140) + math.sin(t * 3) * 0.2
                arm_r.rotation_euler.x = math.radians(140) + math.sin(t * 3) * 0.2
                arm_l.keyframe_insert(data_path="rotation_euler", frame=f)
                arm_r.keyframe_insert(data_path="rotation_euler", frame=f)

        else: # idle
            if arm_l:
                arm_l.rotation_euler.x = math.sin(t) * 0.1
                arm_l.keyframe_insert(data_path="rotation_euler", frame=f)
            if arm_r:
                arm_r.rotation_euler.x = -math.sin(t) * 0.1
                arm_r.keyframe_insert(data_path="rotation_euler", frame=f)

        # Mouth Lip Sync / Talking flap
        if mouth_obj:
            is_talking = action_name in ("talk", "greet", "wave") or (f % 12 < 8)
            mouth_open = (0.5 + 0.5 * math.sin(t * 5)) if is_talking else 0.2
            mouth_obj.scale.z = 0.3 + 0.6 * mouth_open
            mouth_obj.keyframe_insert(data_path="scale", frame=f)

    bpy.ops.object.mode_set(mode='OBJECT')


def run_pipeline(spec_json_path):
    """Main entrypoint called via Blender command-line."""
    with open(spec_json_path, "r", encoding="utf-8") as f:
        spec = json.load(f)

    # 1. Reset scene
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene

    duration_sec = spec.get("duration", 5.0)
    fps = spec.get("fps", 24)
    total_frames = int(duration_sec * fps)
    scene.frame_start = 1
    scene.frame_end = total_frames
    scene.render.fps = fps

    aspect = spec.get("aspect", "9:16")
    preset_name = spec.get("preset", "sweet_candy")
    try:
        from .presets import PASTEL_PALETTES, CHIBI_CHARACTERS, CHIBI_ENVIRONMENTS
    except Exception:
        from pathlib import Path
        import sys
        sys.path.insert(0, str(Path(__file__).parent))
        from presets import PASTEL_PALETTES, CHIBI_CHARACTERS, CHIBI_ENVIRONMENTS

    palette = PASTEL_PALETTES.get(preset_name, PASTEL_PALETTES["sweet_candy"])
    char_id = spec.get("character", "khao_hom")
    char_cfg = CHIBI_CHARACTERS.get(char_id, CHIBI_CHARACTERS["khao_hom"])
    env_id = spec.get("environment", "garden_house")
    env_cfg = CHIBI_ENVIRONMENTS.get(env_id, CHIBI_ENVIRONMENTS["garden_house"])

    # 2. Build Assets
    arm_obj, mouth_obj = build_chibi_character(char_cfg, location=(0, 0, 0))
    build_environment(env_cfg, palette)
    setup_pastel_lighting(palette)
    setup_camera(aspect_ratio=aspect, frame_count=total_frames, res_x=spec.get("res_x"), res_y=spec.get("res_y"))

    # 3. Animate Action
    action = spec.get("action", "wave")
    apply_action_animation(arm_obj, mouth_obj, action_name=action, start_frame=1, end_frame=total_frames)

    # 4. Configure Fast NPR Render Settings
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

    print(f"STARTING_CHIBI_RENDER total_frames={total_frames} engine={render_engine}")
    bpy.ops.render.render(animation=True)
    print("CHIBI_RENDER_COMPLETE")


if __name__ == "__main__":
    if "--spec" in sys.argv:
        idx = sys.argv.index("--spec")
        spec_path = sys.argv[idx + 1]
        run_pipeline(spec_path)
