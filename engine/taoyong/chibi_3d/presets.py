"""Style presets, color palettes, and environment definitions for 3D Chibi Pastel Animation."""

PASTEL_PALETTES = {
    "sweet_candy": {
        "name": "Sweet Candy (ชมพู + มิ้นต์)",
        "primary": (0.98, 0.82, 0.88, 1.0),      # Pastel Pink #FAD2E1
        "secondary": (0.85, 0.95, 0.86, 1.0),    # Pastel Mint #D8F3DC
        "accent": (0.85, 0.81, 0.97, 1.0),       # Pastel Lavender #D8CEF8
        "peach": (0.99, 0.89, 0.82, 1.0),        # Pastel Peach #FDE2D2
        "sunlight": (1.0, 0.96, 0.90),
        "ambient": (0.92, 0.88, 1.0),
        "ground": (0.80, 0.94, 0.84, 1.0),
        "sky": (0.82, 0.90, 0.98, 1.0),
    },
    "lavender_dream": {
        "name": "Lavender Dream (ม่วงพาสเทล + พีช)",
        "primary": (0.85, 0.81, 0.97, 1.0),      # Pastel Lavender #D8CEF8
        "secondary": (0.99, 0.89, 0.82, 1.0),    # Pastel Peach #FDE2D2
        "accent": (0.98, 0.82, 0.88, 1.0),       # Pastel Pink #FAD2E1
        "peach": (1.0, 0.92, 0.85, 1.0),
        "sunlight": (0.98, 0.94, 1.0),
        "ambient": (0.88, 0.82, 0.98),
        "ground": (0.86, 0.82, 0.95, 1.0),
        "sky": (0.89, 0.85, 0.98, 1.0),
    },
    "warm_sunshine": {
        "name": "Warm Sunshine (พีช + มิ้นต์อบอุ่น)",
        "primary": (0.99, 0.89, 0.82, 1.0),      # Pastel Peach #FDE2D2
        "secondary": (0.85, 0.95, 0.86, 1.0),    # Pastel Mint #D8F3DC
        "accent": (1.0, 0.94, 0.80, 1.0),        # Soft Buttercup
        "peach": (0.99, 0.89, 0.82, 1.0),
        "sunlight": (1.0, 0.98, 0.92),
        "ambient": (0.96, 0.92, 0.88),
        "ground": (0.82, 0.92, 0.82, 1.0),
        "sky": (0.85, 0.93, 0.98, 1.0),
    },
}

CHIBI_CHARACTERS = {
    "khao_hom": {
        "id": "khao_hom",
        "name": "น้องข้าวหอม",
        "gender": "girl",
        "skin_tone": (1.0, 0.91, 0.86, 1.0),
        "hair_color": (0.32, 0.20, 0.16, 1.0),
        "hair_style": "twin_buns",
        "dress_color": (0.98, 0.76, 0.84, 1.0),   # Pastel Pink Dress
        "cheek_blush": (1.0, 0.52, 0.62, 1.0),
        "eye_color": (0.15, 0.10, 0.18, 1.0),
        "accessory": "flower_pin",
    },
    "ton_kla": {
        "id": "ton_kla",
        "name": "น้องต้นกล้า",
        "gender": "boy",
        "skin_tone": (0.99, 0.90, 0.84, 1.0),
        "hair_color": (0.24, 0.18, 0.15, 1.0),
        "hair_style": "parted_bangs",
        "dress_color": (0.75, 0.88, 0.96, 1.0),   # Pastel Sky Blue Shirt
        "pants_color": (0.85, 0.81, 0.97, 1.0),   # Pastel Lavender Shorts
        "cheek_blush": (1.0, 0.56, 0.62, 1.0),
        "eye_color": (0.12, 0.10, 0.16, 1.0),
        "accessory": "backpack",
    },
    "bunny": {
        "id": "bunny",
        "name": "ปุยฝ้าย (กระต่ายพาสเทล)",
        "gender": "creature",
        "skin_tone": (0.98, 0.97, 1.0, 1.0),      # Soft White Fur
        "hair_color": (0.98, 0.82, 0.88, 1.0),   # Inner Pink Ears
        "hair_style": "long_ears",
        "dress_color": (0.98, 0.82, 0.88, 1.0),
        "cheek_blush": (1.0, 0.60, 0.70, 1.0),
        "eye_color": (0.25, 0.15, 0.20, 1.0),
        "accessory": "bow_tie",
    },
    "bear": {
        "id": "bear",
        "name": "โกโก้ (หมีน้อยพาสเทล)",
        "gender": "creature",
        "skin_tone": (0.85, 0.72, 0.62, 1.0),     # Soft Pastel Caramel
        "hair_color": (0.75, 0.60, 0.50, 1.0),
        "hair_style": "round_ears",
        "dress_color": (0.85, 0.95, 0.86, 1.0),   # Pastel Mint Vest
        "cheek_blush": (1.0, 0.58, 0.62, 1.0),
        "eye_color": (0.18, 0.12, 0.10, 1.0),
        "accessory": "pocket",
    },
}

CHIBI_ENVIRONMENTS = {
    "garden_house": {
        "id": "garden_house",
        "name": "บ้านสวนพาสเทล (Pastel Garden House)",
        "description": "บ้านไม้หลังเล็กสีพาสเทล รั้วขาว ดอกไม้กลมหลากสี และเนินเขาหญ้ามิ้นต์",
        "lighting": "warm_sunshine",
    },
    "fairy_forest": {
        "id": "fairy_forest",
        "name": "ป่าเวทมนตร์น่ารัก (Cute Fairy Forest)",
        "description": "ต้นไม้แฟนตาซีทรงพุ่มกลมนุ่ม เห็ดพาสเทล และหิ่งห้อยเรืองแสงละมุน",
        "lighting": "lavender_dream",
    },
    "school_classroom": {
        "id": "school_classroom",
        "name": "โรงเรียนแสนสนุก (Fun Kindergarten)",
        "description": "ห้องเรียนสีพาสเทล โต๊ะเก้าอี้ไม้กลมมน บอร์ดวาดรูป และของเล่นบล็อกไม้",
        "lighting": "sweet_candy",
    },
    "fantasy_town": {
        "id": "fantasy_town",
        "name": "เมืองแฟนตาซีพาสเทล (Pastel Fantasy Town)",
        "description": "บ้านหลังเล็กหลังคาสีลูกกวาด โคมไฟวินเทจ และถนนหินโค้งมน",
        "lighting": "sweet_candy",
    },
}
