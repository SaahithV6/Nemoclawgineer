---
name: openclaw-engineering
description: OpenClaw dynamic sculpt + FEA/CFD on Brev. Nemotron calls sculpt tools; executor builds optimizable geometry.
---

# OpenClaw Engineering

**Platform:** OpenClaw only (Discord, Gmail, Nemotron). This skill drives the Brev executor via MCP.

## Autonomous operation (Brev)

Run the full job loop without user CLI: clarify in Discord → submit → poll status → deliver REPORT/STL via hook. User setup: `docs/OPENCLAW_START.md` on the instance.

**Mount reality:** When a body STL exists, never exceed span/chord that fits the car. Extreme downforce → tune `camber_bias`, AoA, twist — not unlimited `span_mm`.

## You do NOT sculpt meshes directly

1. Call `openclaw_engineering_list_sculpt_methods`.
2. Pick a method (or infer from user: wing → `wing_loft`, hull → `hull_loft`, nozzle → `nozzle_axisymmetric`, etc.).
3. Call `openclaw_engineering_sculpt_method_schema(method_id)` and ask the user for **every** important param in Discord.
4. Optional: `openclaw_engineering_preview_sculpt` with draft `geometry_spec`.
5. Submit `openclaw_engineering_submit_job` with full JobSpec.

## geometry_spec (required)

```json
{
  "sculpt_method": "wing_loft",
  "params": {
    "span_mm": 1200,
    "chord_root_mm": 320,
    "chord_tip_mm": 180,
    "twist_tip_deg": -2,
    "camber_bias": 0.1,
    "thickness_bias": 0
  }
}
```

No fixed part categories — any method in the registry is valid. Add `sdf_compose` for novel organic shapes.

Optional **PicoGK** (`picogk_field`): call `openclaw_engineering_picogk_status` first; requires `OPENCLAW_ENGINEERING_PICOGK_ENABLED=1` on Brev.

## JobSpec essentials

| Field | Notes |
|-------|--------|
| `deliverable_scope` | `addon_only` = part file only (e.g. wing-only STL) |
| `geometry_spec` | `sculpt_method` + `params` |
| `manufacturing` | material, tolerance_mm, machining_notes |
| `discipline` | `fea` or `cfd` |
| `agent_review_each_pass` | true |
| `run_parallel_physics` | true (CFD + FEA in parallel on Brev) |

## Proactive Discord (ask before submit)

- Sculpt method and params (from schema)
- Deliverable scope
- Material / tolerance / machining
- FEA loads or CFD speed/downforce/elevation
- Email

If executor returns `needs_clarification`, relay the next question in DM.

## Optimization loop

Executor runs CAD → Gmsh → OpenFOAM/CalculiX → returns metrics → you return `param_adjustments` on **sculpt params** (e.g. `camber_bias`, `draft_mm`, `exit_radius_mm`).

## Deliverables

`REPORT.md`, `result.stl`, `part.stl`, `geometry_spec.json` — via OpenClaw Gmail + Discord confirmation.

See `docs/SCULPT_ENGINE.md` on the executor host.
