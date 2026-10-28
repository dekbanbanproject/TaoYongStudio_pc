"""Persistence helpers for ideas shown in the planner."""
import json
import os
import tempfile
from pathlib import Path


def delete_ideas(path, idea_ids):
    """Remove selected IDs from one idea file and return the number removed."""
    path = Path(path)
    ids = set(idea_ids)
    if not ids:
        return 0
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    items = data.get("ideas", [])
    kept = [item for item in items if item.get("id") not in ids]
    removed = len(items) - len(kept)
    if removed != len(ids):
        raise ValueError("ไม่พบไอเดียที่เลือกในไฟล์ต้นทาง กรุณารีเฟรชแล้วลองใหม่")
    data["ideas"] = kept
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                         prefix=path.name + ".", suffix=".tmp", delete=False) as output:
            temporary = Path(output.name)
            json.dump(data, output, ensure_ascii=False, indent=2)
            output.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return removed
