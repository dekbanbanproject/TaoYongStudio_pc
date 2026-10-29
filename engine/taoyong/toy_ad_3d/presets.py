"""Presets, materials, and environment definitions for Cute Toy Product Ad Animation."""

DEFAULT_TOY_AD_PROMPT = (
    "Cute kawaii 3D toy product commercial, adorable collectible miniature figures, glossy vinyl toy material, "
    "playful pastel colors, cozy desk studio, soft natural window lighting, shallow depth of field, "
    "clean commercial product composition, charming miniature characters, highly detailed 3D rendering, "
    "engaging social media advertising visuals, smooth animated camera movements."
)

TOY_CHARACTERS = {
    "vinyl_bear": {
        "id": "vinyl_bear",
        "name": "น้องหมีไวนิลพาสเทล (Glossy Vinyl Bear)",
        "type": "figure",
        "primary_color": (0.92, 0.78, 0.88, 1.0),   # Glossy Pastel Lilac/Pink
        "belly_color": (0.98, 0.95, 0.92, 1.0),    # Soft Cream Belly
        "snout_color": (0.98, 0.90, 0.85, 1.0),
        "eye_color": (0.10, 0.08, 0.12, 1.0),      # Glossy Black Bead Eyes
        "roughness": 0.12,                          # High Gloss Vinyl
        "specular": 0.85,
        "accessory": "golden_chain",
    },
    "vinyl_bunny": {
        "id": "vinyl_bunny",
        "name": "น้องกระต่ายป๊อปมาร์ท (Pop Vinyl Bunny)",
        "type": "figure",
        "primary_color": (0.85, 0.95, 0.92, 1.0),   # Glossy Mint
        "belly_color": (0.98, 0.88, 0.92, 1.0),    # Pastel Pink Accents
        "eye_color": (0.12, 0.10, 0.15, 1.0),
        "roughness": 0.10,
        "specular": 0.90,
        "accessory": "bow_tie",
    },
    "vinyl_cat": {
        "id": "vinyl_cat",
        "name": "น้องแมวกวักนำโชค (Lucky Vinyl Cat)",
        "type": "figure",
        "primary_color": (1.0, 0.88, 0.60, 1.0),    # Glossy Warm Buttercup
        "belly_color": (1.0, 1.0, 1.0, 1.0),
        "eye_color": (0.10, 0.10, 0.10, 1.0),
        "roughness": 0.12,
        "specular": 0.85,
        "accessory": "bell_collar",
    },
}

TOY_ENVIRONMENTS = {
    "cozy_desk": {
        "id": "cozy_desk",
        "name": "โต๊ะสตูดิโอแสงธรรมชาติ (Cozy Desk Studio)",
        "desk_color": (0.88, 0.80, 0.70, 1.0),     # Natural Light Wood Desk
        "wall_color": (0.95, 0.92, 0.96, 1.0),     # Soft Pastel Wall
        "pedestal_color": (1.0, 1.0, 1.0, 1.0),    # Clean White Glossy Turntable
        "pedestal_trim": (0.95, 0.75, 0.35, 1.0),   # Gold Trim
        "has_plant": True,
        "has_lamp": True,
        "dof_blur": True,
    },
    "pastel_room": {
        "id": "pastel_room",
        "name": "ห้องพาสเทลมินิมอล (Pastel Minimal Room)",
        "desk_color": (0.95, 0.90, 0.92, 1.0),
        "wall_color": (0.88, 0.92, 0.98, 1.0),
        "pedestal_color": (0.98, 0.85, 0.90, 1.0),
        "pedestal_trim": (0.85, 0.80, 0.98, 1.0),
        "has_plant": True,
        "has_lamp": False,
        "dof_blur": True,
    },
}
