from __future__ import annotations

import math


def naca4_coords(m: float, p: float, t: float, n: int = 80) -> list[tuple[float, float]]:
    """NACA 4-digit upper/lower surface coordinates (normalized chord 0..1)."""
    pts: list[tuple[float, float]] = []
    beta = [math.pi * i / (n - 1) for i in range(n)]
    for b in beta:
        x = (1 - math.cos(b)) / 2
        yt = 5 * t * (
            0.2969 * math.sqrt(x)
            - 0.1260 * x
            - 0.3516 * x**2
            + 0.2843 * x**3
            - 0.1015 * x**4
        )
        if x < p:
            yc = m / p**2 * (2 * p * x - x**2)
            dyc = 2 * m / p**2 * (p - x)
        else:
            yc = m / (1 - p) ** 2 * ((1 - 2 * p) + 2 * p * x - x**2)
            dyc = 2 * m / (1 - p) ** 2 * (p - x)
        theta = math.atan(dyc)
        xu = x - yt * math.sin(theta)
        yu = yc + yt * math.cos(theta)
        xl = x + yt * math.sin(theta)
        yl = yc - yt * math.cos(theta)
        pts.append((xu, yu))
    for b in reversed(beta):
        x = (1 - math.cos(b)) / 2
        yt = 5 * t * (
            0.2969 * math.sqrt(x)
            - 0.1260 * x
            - 0.3516 * x**2
            + 0.2843 * x**3
            - 0.1015 * x**4
        )
        if x < p:
            yc = m / p**2 * (2 * p * x - x**2)
            dyc = 2 * m / p**2 * (p - x)
        else:
            yc = m / (1 - p) ** 2 * ((1 - 2 * p) + 2 * p * x - x**2)
            dyc = 2 * m / (1 - p) ** 2 * (p - x)
        theta = math.atan(dyc)
        xl = x + yt * math.sin(theta)
        yl = yc - yt * math.cos(theta)
        pts.append((xl, yl))
    return pts
