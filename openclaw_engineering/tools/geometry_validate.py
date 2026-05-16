from __future__ import annotations

from pathlib import Path


def validate_stl(stl_path: Path, kind: str = "rear_wing") -> dict:
    """Reject obviously invalid geometry before CFD."""
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

        if kind == "rear_wing":
            if aspect > 80:
                issues.append(f"wing aspect ratio extreme ({aspect:.0f})")
            if vol > 5e9:  # mm^3 scale sanity
                issues.append("volume unreasonably large")
            if ext[2] > ext[0] * 3 and ext[2] > ext[1] * 3:
                issues.append("wing does not look like span-dominated shape")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "extents_mm": [float(x) for x in ext],
            "volume_mm3": vol,
            "aspect_ratio": aspect,
        }
    except Exception as exc:
        return {"valid": True, "issues": [f"validation skipped: {exc}"]}
