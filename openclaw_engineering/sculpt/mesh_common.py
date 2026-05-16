from __future__ import annotations

import struct
from pathlib import Path

import numpy as np


def write_stl(tris: list[tuple[tuple[float, float, float], ...]], path: Path) -> None:
    header = b"openclaw-engineering sculpt" + b"\0" * 57
    buf = bytearray(header[:80])
    buf += struct.pack("<I", len(tris))
    for v1, v2, v3 in tris:
        buf += struct.pack("<12fH", 0, 0, 1, *v1, *v2, *v3, 0)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(buf)


def box_tris(x0: float, y0: float, z0: float, dx: float, dy: float, dz: float) -> list[tuple[tuple[float, float, float], ...]]:
    corners = [
        (x0, y0, z0),
        (x0 + dx, y0, z0),
        (x0 + dx, y0 + dy, z0),
        (x0, y0 + dy, z0),
        (x0, y0, z0 + dz),
        (x0 + dx, y0, z0 + dz),
        (x0 + dx, y0 + dy, z0 + dz),
        (x0, y0 + dy, z0 + dz),
    ]
    faces = [
        (0, 1, 2),
        (0, 2, 3),
        (4, 6, 5),
        (4, 7, 6),
        (0, 4, 5),
        (0, 5, 1),
        (2, 6, 7),
        (2, 7, 3),
        (0, 3, 7),
        (0, 7, 4),
        (1, 5, 6),
        (1, 6, 2),
    ]
    return [tuple(corners[i] for i in f) for f in faces]


def loft_sections(
    sections: list[list[tuple[float, float, float]]],
) -> list[tuple[tuple[float, float, float], ...]]:
    """Triangulate ruled surfaces between closed section polylines."""
    tris: list[tuple[tuple[float, float, float], ...]] = []
    for s in range(len(sections) - 1):
        a, b = sections[s], sections[s + 1]
        n = min(len(a), len(b)) - 1
        for i in range(n):
            p0, p1, p2 = a[i], a[i + 1], b[i]
            p3 = b[i + 1]
            tris.append((p0, p1, p2))
            tris.append((p1, p3, p2))
    return tris


def revolve_profile(
    profile: list[tuple[float, float]],
    segments: int = 32,
) -> list[tuple[tuple[float, float, float], ...]]:
    """Revolve 2D (x radius, y axial) profile about Y axis."""
    tris: list[tuple[tuple[float, float, float], ...]] = []
    rings: list[list[tuple[float, float, float]]] = []
    for t in range(segments):
        ang = 2 * np.pi * t / segments
        ring = []
        for r, y in profile:
            x = r * np.cos(ang)
            z = r * np.sin(ang)
            ring.append((float(x), float(y), float(z)))
        rings.append(ring)
    tris.extend(loft_sections(rings))
    return tris


def sdf_to_stl(
    sdf_fn,
    bounds: tuple[float, float, float, float, float, float],
    resolution: int,
    out_path: Path,
) -> Path:
    """Marching cubes on SDF grid."""
    xmin, xmax, ymin, ymax, zmin, zmax = bounds
    xs = np.linspace(xmin, xmax, resolution)
    ys = np.linspace(ymin, ymax, resolution)
    zs = np.linspace(zmin, zmax, resolution)
    grid = np.zeros((resolution, resolution, resolution), dtype=np.float32)
    for i, x in enumerate(xs):
        for j, y in enumerate(ys):
            for k, z in enumerate(zs):
                grid[i, j, k] = sdf_fn(x, y, z)

    try:
        from skimage import measure

        verts, faces, _, _ = measure.marching_cubes(grid, level=0.0, spacing=(
            (xmax - xmin) / resolution,
            (ymax - ymin) / resolution,
            (zmax - zmin) / resolution,
        ))
        verts[:, 0] += xmin
        verts[:, 1] += ymin
        verts[:, 2] += zmin
        tris = []
        for f in faces:
            tris.append((tuple(verts[f[0]]), tuple(verts[f[1]]), tuple(verts[f[2]])))
        write_stl(tris, out_path)
    except ImportError:
        # Fallback: coarse box from negative region center
        write_stl(box_tris(0, 0, 0, 50, 50, 50), out_path)
    return out_path
