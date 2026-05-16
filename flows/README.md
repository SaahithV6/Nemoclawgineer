# Hardcoded execution flows

Pipeline **topology is fixed** in this directory. Per job, only these change:

| Variable | Set by | Examples |
|----------|--------|----------|
| Simulation constraints | OpenClaw agent in JobSpec | OpenFOAM `fluid`, FEA `loads`, `constraints` |
| CAD parameters | Agent + feedback loop | AoA, chord, span, thickness |
| Input geometry | User STL / OnShape | `input.stl` — anchors model to real part |

## Templates

| File | Pipeline |
|------|----------|
| `cfd_wing_optimize.yaml` | CAD → attach body → Gmsh → OpenFOAM → metrics |
| `optimize_fea.yaml` | deform STL → Gmsh → CalculiX → metrics |
| `analyze_cfd.yaml` | deform → OpenFOAM → metrics |

Steps and tool bindings do not change between demos.
