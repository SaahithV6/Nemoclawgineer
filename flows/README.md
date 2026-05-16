# Hardcoded execution flows

Pipeline **topology is fixed** in this directory. Per job, only these change:

| Variable | Set by | Examples |
|----------|--------|----------|
| Simulation constraints | OpenClaw agent in JobSpec | OpenFOAM `fluid`, FEA `loads`, `constraints` |
| **`geometry_spec`** | Agent after Discord Q&A | bracket legs, join_pattern, wing span, holes |
| **`deliverable_scope`** | User + agent | `addon_only` = part file only; `full_assembly` = merge body |
| Optimizer tweaks | Nemotron per pass | `param_adjustments` on feature dimensions |
| Input geometry | User STL / OnShape | optional body for assembly CFD |

## Templates

| File | Pipeline |
|------|----------|
| `cfd_wing_optimize.yaml` | CAD → attach body → Gmsh → OpenFOAM → metrics |
| `optimize_fea.yaml` | deform STL → Gmsh → CalculiX → metrics |
| `analyze_cfd.yaml` | deform → OpenFOAM → metrics |

Steps and tool bindings do not change between demos.
