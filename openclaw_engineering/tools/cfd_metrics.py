from __future__ import annotations

import math

RHO_SEA_LEVEL = 1.225  # kg/m^3


def mph_to_ms(mph: float) -> float:
    return mph * 0.44704


def lbs_to_n(lbs: float) -> float:
    return lbs * 4.44822


def estimate_aero_metrics(
    fluid: dict,
    cd: float,
    cl: float,
    reference_area_m2: float | None = None,
) -> dict[str, float]:
    """Derive downforce/drag in SI from Cl/Cd and user speed."""
    v = float(fluid.get("velocity_ms", fluid.get("speed_mph", 40) * 0.44704))
    if "speed_mph" in fluid and "velocity_ms" not in fluid:
        v = mph_to_ms(float(fluid["speed_mph"]))
    rho = float(fluid.get("density", RHO_SEA_LEVEL))
    if fluid.get("elevation") == "sea_level":
        rho = RHO_SEA_LEVEL
    area = reference_area_m2 or float(fluid.get("reference_area_m2", 0.35))
    q = 0.5 * rho * v * v
    drag_n = cd * q * area
    lift_n = cl * q * area
    downforce_n = -lift_n if lift_n < 0 else lift_n
    return {
        "cd": cd,
        "cl": cl,
        "velocity_ms": v,
        "drag_n": drag_n,
        "downforce_n": downforce_n,
        "dynamic_pressure_pa": q,
    }


def downforce_error(metrics: dict, target_lbs: float) -> float:
    target_n = lbs_to_n(target_lbs)
    actual = metrics.get("downforce_n", 0.0)
    return abs(actual - target_n) / max(target_n, 1.0)
