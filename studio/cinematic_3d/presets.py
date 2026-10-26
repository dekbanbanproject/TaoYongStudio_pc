"""Presets, palettes, and environment definitions for 3D Cinematic Cartoon Animation."""

DEFAULT_CINEMATIC_PROMPT = (
    "Cute cinematic 3D animated animal characters, adorable expressive faces, big sparkling eyes, "
    "detailed soft fur, colorful tropical underwater world, beautiful beach environment, golden sunlight, "
    "volumetric lighting, highly detailed stylized 3D rendering, warm family animation atmosphere, "
    "smooth character motion, consistent character identities, cinematic camera movements, "
    "high-quality animated storybook style."
)

CINEMATIC_CHARACTERS = {
    "tropical_fish": {
        "id": "tropical_fish",
        "name": "ปลาน้อยนีโม่ (Tropical Clownfish)",
        "type": "fish",
        "primary_color": (1.0, 0.45, 0.15, 1.0),    # Vibrant Orange
        "secondary_color": (0.98, 0.98, 1.0, 1.0),  # Bright White Stripes
        "stripe_color": (0.12, 0.10, 0.15, 1.0),    # Thin Black Edges
        "eye_color": (0.15, 0.20, 0.35, 1.0),       # Deep Ocean Blue Eyes
        "fin_color": (1.0, 0.55, 0.25, 0.85),       # Semi-translucent Orange Fins
        "glow": (0.2, 0.8, 1.0),
        "scale": 1.0,
        "default_motion": "swimming",
    },
    "kitten": {
        "id": "kitten",
        "name": "ลูกแมวน้อยส้ม (Golden Furry Kitten)",
        "type": "quadruped",
        "primary_color": (0.95, 0.65, 0.30, 1.0),   # Warm Ginger Orange
        "secondary_color": (0.98, 0.95, 0.90, 1.0), # Cream Belly & Paws
        "stripe_color": (0.75, 0.40, 0.15, 1.0),
        "eye_color": (0.20, 0.70, 0.45, 1.0),       # Emerald Green Eyes
        "ear_inner": (1.0, 0.70, 0.75, 1.0),        # Rosy Pink Inner Ears
        "scale": 0.85,
        "default_motion": "walking",
    },
    "chick": {
        "id": "chick",
        "name": "ลูกเจี๊ยบปุกปุย (Fluffy Yellow Chick)",
        "type": "biped_bird",
        "primary_color": (1.0, 0.85, 0.25, 1.0),    # Sunshine Yellow Fluff
        "secondary_color": (1.0, 0.95, 0.60, 1.0),  # Soft Buttercream
        "beak_color": (1.0, 0.50, 0.10, 1.0),       # Bright Orange Beak
        "eye_color": (0.12, 0.10, 0.15, 1.0),
        "scale": 0.75,
        "default_motion": "jumping",
    },
    "bunny": {
        "id": "bunny",
        "name": "กระต่ายหิมะ (Cute Fluffy Bunny)",
        "type": "biped_animal",
        "primary_color": (0.96, 0.95, 0.98, 1.0),   # Soft White
        "secondary_color": (1.0, 0.80, 0.85, 1.0),  # Pastel Pink
        "eye_color": (0.80, 0.30, 0.50, 1.0),       # Ruby Gem Eyes
        "ear_inner": (1.0, 0.75, 0.82, 1.0),
        "scale": 0.85,
        "default_motion": "jumping",
    },
}

CINEMATIC_ENVIRONMENTS = {
    "underwater": {
        "id": "underwater",
        "name": "โลกใต้ทะเลสีคราม (Tropical Coral Reef)",
        "theme": "ocean",
        "water_color": (0.10, 0.45, 0.75, 1.0),
        "fog_color": (0.12, 0.50, 0.80, 1.0),
        "sand_color": (0.92, 0.85, 0.70, 1.0),
        "coral_colors": [
            (1.0, 0.40, 0.55, 1.0),  # Coral Pink
            (0.35, 0.85, 0.75, 1.0),  # Seafoam Turquoise
            (0.95, 0.80, 0.20, 1.0),  # Sun Coral Yellow
            (0.65, 0.40, 0.90, 1.0),  # Purple Sea Anemone
        ],
        "has_bubbles": True,
        "has_caustics": True,
        "lighting": "deep_ocean",
    },
    "beach": {
        "id": "beach",
        "name": "ชายหาดทรอปิคอล (Sunny Tropical Beach)",
        "theme": "beach",
        "sand_color": (0.96, 0.88, 0.72, 1.0),
        "water_color": (0.25, 0.70, 0.85, 0.8),
        "sky_color": (0.60, 0.82, 0.98, 1.0),
        "has_palms": True,
        "has_waves": True,
        "lighting": "golden_hour",
    },
    "sunlit_forest": {
        "id": "sunlit_forest",
        "name": "ป่าธรรมชาติแสงทอง (Sunlit Nature Forest)",
        "theme": "forest",
        "ground_color": (0.42, 0.65, 0.35, 1.0),
        "bark_color": (0.45, 0.32, 0.22, 1.0),
        "leaf_colors": [
            (0.40, 0.78, 0.35, 1.0),
            (0.55, 0.85, 0.30, 1.0),
            (0.85, 0.70, 0.25, 1.0),
        ],
        "has_volumetric_sun": True,
        "lighting": "volumetric_forest",
    },
}

CINEMATIC_LIGHTING = {
    "deep_ocean": {
        "sun_color": (0.35, 0.80, 1.0),
        "sun_energy": 3.5,
        "sun_rot": (0.45, 0.2, 0.6),
        "ambient_color": (0.08, 0.25, 0.45),
        "caustic_energy": 2.2,
    },
    "golden_hour": {
        "sun_color": (1.0, 0.82, 0.55),
        "sun_energy": 4.5,
        "sun_rot": (0.75, -0.3, 1.2),
        "ambient_color": (0.50, 0.40, 0.60),
    },
    "volumetric_forest": {
        "sun_color": (1.0, 0.92, 0.70),
        "sun_energy": 4.0,
        "sun_rot": (0.60, 0.25, 0.8),
        "ambient_color": (0.25, 0.40, 0.25),
    },
}
