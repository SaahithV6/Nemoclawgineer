# OpenClaw Engineering CAE I/O Standards

Nemotron (via OpenClaw) plans jobs once; the executor runs YAML flows and returns **reduced feedback** between passes.

## JobSpec (planner output)

See `openclaw_engineering/models.py`. Key fields:

| Field | Purpose |
|-------|---------|
| `mode` | optimize, analyze, generate, collab |
| `discipline` | fea, cfd |
| `cad_backend` | build123d, cadquery, freecad, stl_deform |
| `flow_template` | YAML under `flows/templates/` |
| `design_params` | Optuna / pass-loop variables |
| `fluid` | speed_mph, density, target_downforce_lbs, elevation |
| `onshape` | document_id, workspace_id, element_id |
| `needs_clarification` | Discord/user Q&A before run |

## Flow templates

| Template | Pipeline |
|----------|----------|
| `optimize_fea.yaml` | deform STL → Gmsh → CalculiX → metrics |
| `analyze_cfd.yaml` | deform → OpenFOAM → CFD metrics |
| `cfd_wing_optimize.yaml` | Build123d wing → attach to body STL → mesh → OpenFOAM |

## Reduced agent feedback (between passes)

```json
{
  "pass_index": 2,
  "metrics": {"cd": 0.31, "cl": 0.42, "downforce_n": 890, "drag_n": 120},
  "feasible": true,
  "constraint_violations": [],
  "recommendation": "Increase AoA 1-2 deg to reach downforce target",
  "suggest_stop": false,
  "param_adjustments": {"angle_of_attack_deg": 9.5}
}
```

## CFD user inputs (wing demo)

| User says | Maps to |
|-----------|---------|
| 40 mph | `fluid.speed_mph` = 40 |
| 200 lbs downforce | `fluid.target_downforce_lbs` = 200 |
| sea level | `fluid.elevation` = sea_level, `density` = 1.225 |

Derived metrics (always SI in feedback):

- `downforce_n`, `drag_n`, `cd`, `cl`, `velocity_ms`, `dynamic_pressure_pa`

## FEA metrics

- `max_stress_mpa`, `max_displacement_mm`, `mass_kg`

## Artifacts per job

- `REPORT.md` — spec sheet + pass table
- `result.stl` — final geometry
- `metrics.json` — last solver metrics
- `flow.snapshot.json` — executed flow

## OpenFOAM CLI convention

Cases live under `jobs/<id>/work/openfoam/`. With ESI/OpenFOAM on PATH:

```bash
cd jobs/<id>/work/openfoam
simpleFoam
```

OpenClaw Engineering writes `system/controlDict` and `constant/*` from `fluid` dict.

## OnShape

- **Pull:** export Part Studio → `input_onshape.stl`
- **Push:** upload `result.stl` (same filename when configured)
- Requires `ONSHAPE_*` in `~/.openclaw_engineering/.env`

## Delivery (Discord + Gmail)

OpenClaw Engineering does **not** send email directly. It writes `DELIVERY.json` and POSTs to OpenClaw `/hooks/agent`. The OpenClaw agent delivers via **Discord channel** and **Gmail integration**.

OnShape push remains in openclaw-engineering (`ONSHAPE_*` keys).
