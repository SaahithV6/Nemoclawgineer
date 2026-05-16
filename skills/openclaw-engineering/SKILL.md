---
name: openclaw-engineering
description: OpenClaw CAE backend — CAD, Gmsh, OpenFOAM, CalculiX. YOU infer the demo; the backend executes.
---

# OpenClaw Engineering (you are the planner)

**Platform:** OpenClaw only. This skill drives a local executor on Brev. There is no separate "nemoclaw" product or Discord bot for the user.

## Your job on every demo

1. **Infer** from the user's message (any vehicle, bracket, wing, hull, kit):
   - `discipline`: `fea` | `cfd`
   - `geometry_kind`: `rear_wing` | `downforce_kit` | (FEA: use `stl_deform` on upload)
   - `mode`: `optimize` | `analyze` | `generate` | `collab`
   - Objectives, constraints, loads, fluid (speed, downforce, elevation)
   - Whether to run speed sweep (`run_speed_sweep`) and wing FEA (`run_wing_fea`)
2. **Clarify** in Discord DM if critical numbers are missing:
   - **CFD:** speed mph, downforce/drag target, elevation
   - **FEA:** force (N), direction, allowable stress (MPa) or material, how the part is fixed
3. For **FEA**, infer loads from context when obvious (e.g. "bolted bracket" → tensile + fixed face) but **state assumptions** in `loads` or ask one question — never run with empty loads.
4. Build full **JobSpec JSON** yourself (see schema below). Do not rely on backend heuristics.
5. Call `openclaw_engineering_submit_job(spec_json, user_request)`.
6. Poll `openclaw_engineering_job_status` until `completed`.
7. Deliver `REPORT.md`, `result.stl`, attachments via **OpenClaw Gmail** + confirm in **Discord DM**.

## Iteration loop (executor ↔ you)

YAML flows in `flows/templates/` are **hardcoded**. Per job you only change:

- Simulation: `fluid`, `loads`, `constraints`, `boundary_conditions`
- CAD: `design_params`, `cad_params`, `input_stl` (accuracy to the real part)

Each optimization pass the executor sends you **reduced metrics**. You return `param_adjustments` (via gateway review) to tune the 3D CAD generator on the next pass. Set `agent_review_each_pass: true`.

## Geometry rules (you must enforce — any demo)

| User wants | `geometry_kind` | You must |
|------------|-----------------|----------|
| Wing, airfoil, spoiler | `rear_wing` | NACA-based extrusion only; parametric AoA, chord, span |
| Splitter, diffuser, louvres, venturi, "aero kit" | `downforce_kit` | Predefined kit components; no random blobs |
| Upload STL + optimize | FEA `optimize_fea.yaml` or CFD with deform | Use their file as `input_stl` |
| "Crazy" / organic shape | — | **Refuse**; offer NACA wing or kit or catalog reference |

Optional: include `grabcad_query` URL for user to download a reference STL; they can re-upload as `reference_stl`.

## Solvers (fixed stack)

- **OpenFOAM** — all CFD (including optimization passes and speed sweeps)
- **CalculiX** — FEA (brackets, wing stress)
- **Gmsh** — meshing
- **Build123d** — constrained CAD generation
- **Optuna** — always `false` in JobSpec

## JobSpec JSON (you produce this)

```json
{
  "mode": "optimize",
  "discipline": "cfd",
  "geometry_kind": "rear_wing",
  "user_request": "<verbatim user ask>",
  "flow_template": "cfd_wing_optimize.yaml",
  "objectives": [{"metric": "cd", "sense": "minimize"}],
  "constraints": [],
  "fluid": {
    "speed_mph": 40,
    "target_downforce_lbs": 200,
    "elevation": "sea_level",
    "density": 1.225,
    "vmax_stock_mph": 130,
    "speed_sweep_mph": [10,20,30,40,50,60,70,80,90,100,110,120,130]
  },
  "design_params": [
    {"name": "angle_of_attack_deg", "min": -2, "max": 16, "initial": 8},
    {"name": "chord_mm", "min": 180, "max": 450, "initial": 280}
  ],
  "run_speed_sweep": true,
  "run_wing_fea": true,
  "use_optuna": false,
  "agent_review_each_pass": true,
  "notify_email": "user@example.com"
}
```

## MCP tools

- `openclaw_engineering_submit_job(spec_json, user_request)`
- `openclaw_engineering_job_status(job_id)`
- `openclaw_engineering_list_artifacts(job_id)`
- `openclaw_engineering_fetch_artifact(job_id, name)`

## Example demos (same skill, you infer details)

- **914 rear wing:** CFD, rear_wing, speed sweep 10–130 mph, wing FEA, replace STL, email spec.
- **Bracket FEA:** discipline fea, `optimize_fea.yaml`, `loads.force_n`, `constraints` on `max_stress_mpa`, `design_params` e.g. `thickness_mm`; no wing CAD.
- **Downforce kit:** geometry_kind downforce_kit, CFD, kit components only.

## Keys (OpenClaw terminal / ~/.openclaw/.env)

- NVIDIA / gateway — from launchable `configure.sh`
- `DISCORD_BOT_TOKEN` — Discord channel
- Gmail — `openclaw webhooks gmail setup`
- OnShape — `ONSHAPE_*` in `~/.openclaw-engineering/.env` (executor only)
