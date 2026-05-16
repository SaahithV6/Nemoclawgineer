# Dynamic sculpt engine (OpenClaw Engineering)

Nemotron on **OpenClaw** does not sculpt meshes itself. It calls **MCP tools** that run field- and loft-based geometry on Brev (LEAP71 / nTop-inspired workflow).

## Research basis

| Approach | Idea | Our implementation |
|----------|------|-------------------|
| [LEAP71 computational engineering](https://leap71.com/computationalengineering/) | Algorithms encode design space; many valid parts from one process | `sculpt_method` + optimizable `params` + FEA/CFD loop |
| [nTop field-driven design](https://www.ntop.com/field-driven-design/) | Spatially varying thickness, blends, implicit geometry | `sdf_compose`, `camber_bias`, organic join patterns |
| [PicoGK / ShapeKernel](https://github.com/leap71/LEAP71_ShapeKernel) | Low-level kernels + high-level engineering functions | `openclaw_engineering/sculpt/methods/*` plugins |

## MCP tools (Nemotron)

| Tool | Purpose |
|------|---------|
| `openclaw_engineering_list_sculpt_methods` | Discover methods (wing, hull, nozzle, SDF, …) |
| `openclaw_engineering_sculpt_method_schema` | Param schema for a method |
| `openclaw_engineering_preview_sculpt` | Fast STL preview |
| `openclaw_engineering_submit_job` | Full CAD → mesh → OpenFOAM/CalculiX → optimize |

## geometry_spec (JobSpec)

```json
{
  "sculpt_method": "hull_loft",
  "params": {
    "length_mm": 2400,
    "beam_mm": 700,
    "draft_mm": 320,
    "bow_fullness": 0.65
  }
}
```

Optimization passes adjust `params` via `param_adjustments` (same keys).

## Registered methods

| ID | Use case |
|----|----------|
| `wing_loft` | New wing profiles, twist, camber sculpt |
| `hull_loft` | Boat / hydrodynamic hull stations |
| `nozzle_axisymmetric` | Rocket nozzles, ducts (area-rule style contour) |
| `sdf_compose` | Implicit blends, organic transitions |
| `mesh_displacement` | Sculpt on uploaded STL |
| `bracket_parametric` | Structural brackets, gussets, angles |
| `picogk_field` | **Optional** [LEAP71 PicoGK](PICOGK.md) lattice/voxel booleans → STL |

Add new methods by registering in `openclaw_engineering/sculpt/registry.py` and implementing `build(params, out_stl)` in `sculpt/methods/`.

## PicoGK (optional)

See **[PICOGK.md](PICOGK.md)** — `OPENCLAW_ENGINEERING_PICOGK_ENABLED=1`, .NET 9, `scripts/install_picogk.sh`, MCP `openclaw_engineering_picogk_status`.

## Compute on Brev

- SDF marching uses `scikit-image` marching cubes (tunable `resolution`; increase for finer sculpts).
- Parallel optimization passes use CPU pool (see `config/openclaw-engineering.defaults.yaml`).
