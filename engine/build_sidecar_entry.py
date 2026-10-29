"""Entry point used to freeze the TaoYongStudio engine into a Windows executable.

    pyinstaller --noconfirm engine/build_sidecar.spec

Produces `engine/dist/taoyong-engine/taoyong-engine.exe`, a single-folder build that
the Tauri shell spawns instead of `python -m taoyong.service`.
"""
import sys
from pathlib import Path

# The engine resolves its workspace root from TAOYONG_ROOT (set by the Rust side)
# and falls back to walking up from this file.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from taoyong.service import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
