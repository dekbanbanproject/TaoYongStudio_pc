"""3D Cinematic Cartoon Animation package."""

from .pipeline import render_cinematic_animation
from .presets import CINEMATIC_CHARACTERS, CINEMATIC_ENVIRONMENTS, DEFAULT_CINEMATIC_PROMPT

__all__ = [
    "render_cinematic_animation",
    "CINEMATIC_CHARACTERS",
    "CINEMATIC_ENVIRONMENTS",
    "DEFAULT_CINEMATIC_PROMPT",
]
