#!/usr/bin/env python3
"""Generate tests/fixtures/sample_bracket.stl (simple L-bracket)."""
import struct
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "sample_bracket.stl"


def tri(a, b, c):
    return struct.pack("<12fH", 0, 0, 1, *a, *b, *c, 0)


def main():
    # L-shaped bracket from two boxes (triangulated quads as 2 tris each)
    tris = []
    # bottom plate z=0..2
    for x0, x1, y0, y1 in [(0, 20, 0, 10)]:
        z0, z1 = 0, 2
        corners = [
            (x0, y0, z0),
            (x1, y0, z0),
            (x1, y1, z0),
            (x0, y1, z0),
            (x0, y0, z1),
            (x1, y0, z1),
            (x1, y1, z1),
            (x0, y1, z1),
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
        for f in faces:
            tris.append(tri(corners[f[0]], corners[f[1]], corners[f[2]]))
    # vertical leg
    for x0, x1, y0, y1 in [(0, 5, 10, 30)]:
        z0, z1 = 0, 15
        corners = [
            (x0, y0, z0),
            (x1, y0, z0),
            (x1, y1, z0),
            (x0, y1, z0),
            (x0, y0, z1),
            (x1, y0, z1),
            (x1, y1, z1),
            (x0, y1, z1),
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
        for f in faces:
            tris.append(tri(corners[f[0]], corners[f[1]], corners[f[2]]))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    buf = bytearray(b"nemoclaw sample bracket" + b"\0" * 56)
    buf += struct.pack("<I", len(tris))
    for t in tris:
        buf += t
    OUT.write_bytes(buf)
    print("Wrote", OUT, "triangles:", len(tris))


if __name__ == "__main__":
    main()
