---
name: nemoclaw
description: Submit and monitor CAE jobs (FEA/CFD) on the Nemoclaw orchestrator.
---

# Nemoclaw skill

Use MCP tools from server **nemoclaw**:

- `nemoclaw_submit_job(spec_json, user_request)` — start a job; `spec_json` follows JobSpec (mode, discipline, objectives, constraints, design_params, flow_template).
- `nemoclaw_job_status(job_id)` — poll status, passes, artifacts.
- `nemoclaw_list_artifacts(job_id)` — list `REPORT.md`, `result.stl`, `metrics.json`.
- `nemoclaw_fetch_artifact(job_id, name)` — download URL for an artifact.

## Defaults

- Structural optimization: `flow_template` = `optimize_fea.yaml`, discipline `fea`, mode `optimize`.
- CFD analysis: `analyze_cfd.yaml`, discipline `cfd`, mode `analyze`.
- Credit budget: max 3 optimization passes; stops when improvement &lt; 2% for 2 passes.

## Example spec_json

```json
{
  "mode": "optimize",
  "discipline": "fea",
  "user_request": "Minimize mass with max stress <= 200 MPa under 500 N tensile load",
  "objectives": [{"metric": "mass_kg", "sense": "minimize"}],
  "constraints": [{"metric": "max_stress_mpa", "op": "le", "value": 200}],
  "loads": {"force_n": 500},
  "design_params": [{"name": "thickness_mm", "min": 2, "max": 12, "initial": 6}],
  "flow_template": "optimize_fea.yaml"
}
```

After submit, poll status until `completed`, then fetch `REPORT.md` and `result.stl`.
