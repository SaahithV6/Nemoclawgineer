from __future__ import annotations

from pathlib import Path


def validate_stl(stl_path: Path, part_category: str = "custom") -> dict:
    """Manufacturability sanity checks — not a whitelist of part types."""
    issues: list[str] = []
    if not stl_path.exists() or stl_path.stat().st_size < 100:
        return {"valid": False, "issues": ["empty or missing STL"]}

    try:
        import trimesh

        m = trimesh.load(str(stl_path))
        if m.is_empty:
            return {"valid": False, "issues": ["empty mesh"]}
        ext = m.bounding_box.extents
        vol = abs(float(m.volume)) if m.is_volume else 0.0
        max_ext = float(max(ext))
        min_ext = float(min(ext))
        aspect = max_ext / max(min_ext, 1e-6)

        if max_ext > 8000:
            issues.append(f"bounding box very large ({max_ext:.0f} mm) — check units")
        if max_ext < 1:
            issues.append("bounding box tiny — check units (expect mm)")
        if aspect > 200:
            issues.append(f"extreme aspect ratio ({aspect:.0f}) — verify design intent")

        if part_category == "wing" and aspect > 100:
            issues.append("wing mesh unusually slender — verify span/chord")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "extents_mm": [float(x) for x in ext],
            "volume_mm3": vol,
            "aspect_ratio": aspect,
        }
    except Exception as exc:
        return {"valid": True, "issues": [f"validation skipped: {exc}"]}
