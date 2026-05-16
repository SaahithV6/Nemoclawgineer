from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class SculptMethod:
    id: str
    name: str
    description: str
    physics: list[str]
    param_schema: dict[str, Any]
    builder: str  # module path


SCULPT_METHODS: dict[str, SculptMethod] = {}


def register(method: SculptMethod) -> None:
    SCULPT_METHODS[method.id] = method


def _register_defaults() -> None:
    register(
        SculptMethod(
            id="wing_loft",
            name="Wing / airfoil loft sculpt",
            description=(
                "Deformable multi-section loft for wings and blades. "
                "Optimize camber, thickness, twist, and section shape per span station."
            ),
            physics=["cfd", "fea"],
            param_schema={
                "span_mm": {"type": "number", "default": 1200},
                "chord_root_mm": {"type": "number", "default": 320},
                "chord_tip_mm": {"type": "number", "default": 180},
                "twist_tip_deg": {"type": "number", "default": -2},
                "profile": {"type": "string", "default": "naca2412"},
                "section_count": {"type": "integer", "default": 12},
                "camber_bias": {"type": "number", "default": 0.0, "description": "Sculpt: -1..1 shifts camber"},
                "thickness_bias": {"type": "number", "default": 0.0},
            },
            builder="openclaw_engineering.sculpt.methods.wing_loft",
        )
    )
    register(
        SculptMethod(
            id="hull_loft",
            name="Boat hull / hydrodynamic loft",
            description=(
                "Waterline stations lofted along length. "
                "Tune beam, draft, rocker, and bow/stern fullness for hydrodynamic CFD."
            ),
            physics=["cfd"],
            param_schema={
                "length_mm": {"type": "number", "default": 2000},
                "beam_mm": {"type": "number", "default": 600},
                "draft_mm": {"type": "number", "default": 280},
                "station_count": {"type": "integer", "default": 16},
                "bow_fullness": {"type": "number", "default": 0.6},
                "stern_fullness": {"type": "number", "default": 0.5},
                "rocker_mm": {"type": "number", "default": 40},
            },
            builder="openclaw_engineering.sculpt.methods.hull_loft",
        )
    )
    register(
        SculptMethod(
            id="nozzle_axisymmetric",
            name="Rocket nozzle / duct (axisymmetric sculpt)",
            description=(
                "Revolved contour from throat to exit for compressible flow / "
                "constant-pressure-style nozzle design. Optimize area distribution."
            ),
            physics=["cfd"],
            param_schema={
                "length_mm": {"type": "number", "default": 400},
                "throat_radius_mm": {"type": "number", "default": 25},
                "exit_radius_mm": {"type": "number", "default": 80},
                "contour_points": {"type": "integer", "default": 24},
                "divergence_deg": {"type": "number", "default": 15},
                "wall_thickness_mm": {"type": "number", "default": 4},
            },
            builder="openclaw_engineering.sculpt.methods.nozzle_axisymmetric",
        )
    )
    register(
        SculptMethod(
            id="sdf_compose",
            name="Implicit SDF sculpt (field-driven CSG)",
            description=(
                "Compose spheres, boxes, and blends via signed-distance fields; "
                "march to mesh. For organic transitions and spatially varying thickness."
            ),
            physics=["fea", "cfd", "general"],
            param_schema={
                "resolution": {"type": "integer", "default": 48},
                "primitives": {
                    "type": "array",
                    "description": "List of {shape, center, size, blend_radius}",
                },
            },
            builder="openclaw_engineering.sculpt.methods.sdf_compose",
        )
    )
    register(
        SculptMethod(
            id="mesh_displacement",
            name="Displacement-field sculpt on mesh",
            description="Deform an input STL with a radial or directional displacement field (tunable amplitude).",
            physics=["fea", "cfd"],
            param_schema={
                "input_stl": {"type": "string"},
                "amplitude_mm": {"type": "number", "default": 5},
                "frequency": {"type": "number", "default": 1.0},
                "direction": {"type": "array", "default": [0, 0, 1]},
            },
            builder="openclaw_engineering.sculpt.methods.mesh_displacement",
        )
    )
    register(
        SculptMethod(
            id="picogk_field",
            name="PicoGK field / lattice (optional)",
            description=(
                "LEAP71 PicoGK: voxel booleans, spheres, beams, STL import. "
                "Requires .NET 9 + OPENCLAW_ENGINEERING_PICOGK_ENABLED=1. "
                "Falls back to SDF if runtime unavailable."
            ),
            physics=["fea", "cfd", "general"],
            param_schema={
                "voxel_size_mm": {"type": "number", "default": 0.5},
                "operations": {
                    "type": "array",
                    "description": "PicoGK ops: sphere, beam, stl_import, cube; boolean add|subtract|intersect",
                },
                "spheres": {"type": "array", "description": "Shorthand: [{center, radius_mm, boolean}]"},
                "beams": {"type": "array", "description": "Shorthand: [{a, b, radius_mm}]"},
            },
            builder="openclaw_engineering.sculpt.methods.picogk_field",
        )
    )
    register(
        SculptMethod(
            id="bracket_parametric",
            name="Bracket / structural parametric sculpt",
            description="L/T brackets, gussets, holes — optimizable legs, angles, organic blends.",
            physics=["fea"],
            param_schema={
                "style": {"type": "string", "default": "L"},
                "leg_a_mm": {"type": "number", "default": 80},
                "leg_b_mm": {"type": "number", "default": 60},
                "thickness_mm": {"type": "number", "default": 8},
                "bend_angle_deg": {"type": "number", "default": 90},
                "join_pattern": {"type": "string", "default": "organic_blend"},
            },
            builder="openclaw_engineering.sculpt.methods.bracket_parametric",
        )
    )


_register_defaults()


def infer_sculpt_method(user_request: str, discipline: str = "") -> str:
    t = user_request.lower()
    if any(k in t for k in ("nozzle", "rocket", "throat", "combustion chamber")):
        return "nozzle_axisymmetric"
    if any(k in t for k in ("hull", "boat", "hydrodynamic", "displacement hull", "keel")):
        return "hull_loft"
    if any(k in t for k in ("wing", "airfoil", "spoiler", "blade")):
        return "wing_loft"
    if any(k in t for k in ("bracket", "mount", "gusset")):
        return "bracket_parametric"
    if discipline == "fea":
        return "bracket_parametric"
    if discipline == "cfd":
        return "wing_loft"
    return "sdf_compose"
