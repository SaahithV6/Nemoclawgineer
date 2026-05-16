from __future__ import annotations

import json
import shutil
from pathlib import Path

from openclaw_engineering.models import DeliverableScope, JobState, PartCategory
from openclaw_engineering.store import artifact_path, job_dir, list_artifacts


def write_report(state: JobState, stl_source: Path | None = None) -> Path:
    spec = state.spec
    lines = [
        "# OpenClaw Engineering — Build & Analysis Specification",
        "",
        "## 1. User request",
        spec.user_request,
        "",
        "## 2. Configuration",
        f"- Part category: **{spec.part_category.value}**",
        f"- Deliverable: **{spec.deliverable_scope.value}**",
        f"- Flow: `{spec.flow_template}`",
        "",
        "### Mount / feasibility (reality check)",
        "",
    ]
    if spec.feasibility:
        lines.append(f"- Envelope: `{json.dumps(spec.feasibility.get('envelope', {}))}`")
        for note in spec.feasibility.get("checks", []):
            lines.append(f"- {note}")
        lines.append("")
    lines += [
        "### Geometry specification (for fabrication)",
        "```json",
        json.dumps(spec.geometry_spec, indent=2),
        "```",
        "",
    ]

    mfg = spec.manufacturing or {}
    if mfg or spec.geometry_spec.get("material"):
        lines += [
            "## 3. Manufacturing & ordering",
            f"- Material: {mfg.get('material') or spec.geometry_spec.get('material', '—')}",
            f"- Tolerance target: {mfg.get('tolerance_mm', spec.geometry_spec.get('tolerance_mm', '—'))} mm",
            f"- Notes: {mfg.get('machining_notes') or spec.geometry_spec.get('machining_notes', '—')}",
            "",
            "Use `result.stl` (and `part.stl` when present) for CAM, quoting, or OnShape import.",
            "",
        ]

    lines += ["## 4. Design parameters (final)"]
    for k, v in state.best_params.items():
        lines.append(f"- `{k}`: {v}")
    for k, v in spec.cad_params.items():
        if k not in state.best_params:
            lines.append(f"- `{k}`: {v}")
    lines.append("")

    lines += ["## 5. Optimization iteration log"]
    lines.append("| Pass | Feasible | Objective | Metrics | Params | Agent note |")
    lines.append("|------|----------|-----------|---------|--------|------------|")
    for p in state.passes:
        m = ", ".join(f"{k}={v:.4g}" for k, v in list(p.metrics.items())[:5])
        pr = ", ".join(f"{k}={v:.3g}" for k, v in p.params.items())
        note = (p.agent_note or "")[:80].replace("|", "/")
        lines.append(
            f"| {p.pass_index} | {p.feasible} | {p.objective_value:.4g} | {m} | {pr} | {note} |"
        )
    lines.append("")
    lines.append(f"**Stop reason:** `{state.stop_reason or 'unknown'}`")
    lines.append("")

    sec = 6
    if state.speed_sweep:
        lines += [
            f"## {sec}. Aerodynamic speed sweep",
            "",
            "| mph | Cd | Cl | Downforce (lbs) | Drag (lbs) |",
            "|-----|----|----|-----------------|------------|",
        ]
        for r in state.speed_sweep:
            lines.append(
                f"| {r.speed_mph:.0f} | {r.cd or 0:.3f} | {r.cl or 0:.3f} | "
                f"{r.downforce_lbs or 0:.1f} | {r.drag_lbs or 0:.1f} |"
            )
        lines.append("")
        sec += 1

    if state.wing_fea:
        lines += [f"## {sec}. Structural analysis (CalculiX)", ""]
        m = state.wing_fea.get("metrics", {})
        lines.append(f"- Max stress: **{m.get('max_stress_mpa', 'n/a')} MPa**")
        lines.append(f"- Feasible: {state.wing_fea.get('feasible')}")
        lines.append("")
        sec += 1

    lines += [
        f"## {sec}. Deliverables",
        f"- `result.stl` — per **{spec.deliverable_scope.value}**",
        "- `part.stl` — generated part only (when optimization ran)",
        "- `geometry_spec.json` — full build recipe",
        "- This specification sheet",
        "",
        "## Recommendation",
    ]
    lines.append(
        "Geometry was generated from your clarified `geometry_spec` and tuned against simulation metrics. "
        "Verify tolerances and tool access before production."
    )

    report_path = artifact_path(state.job_id, "REPORT.md")
    report_path.write_text("\n".join(lines) + "\n")

    spec_json = artifact_path(state.job_id, "geometry_spec.json")
    spec_json.write_text(json.dumps(spec.geometry_spec, indent=2))

    if stl_source and stl_source.exists():
        shutil.copy2(stl_source, artifact_path(state.job_id, "result.stl"))
        part_src = job_dir(state.job_id) / "work" / "addon.stl"
        if part_src.exists():
            shutil.copy2(part_src, artifact_path(state.job_id, "part.stl"))
        orig = job_dir(state.job_id) / "input.stl"
        if orig.exists() and spec.deliverable_scope == DeliverableScope.FULL_ASSEMBLY:
            shutil.copy2(orig, artifact_path(state.job_id, "original_body.stl"))

    sweep_p = job_dir(state.job_id) / "work" / "speed_sweep" / "speed_sweep.json"
    if sweep_p.exists():
        shutil.copy2(sweep_p, artifact_path(state.job_id, "speed_sweep.json"))
    fea_p = job_dir(state.job_id) / "work" / "wing_fea" / "wing_fea.json"
    if fea_p.exists():
        shutil.copy2(fea_p, artifact_path(state.job_id, "wing_fea.json"))
    metrics_src = job_dir(state.job_id) / "work" / "metrics.json"
    if metrics_src.exists():
        shutil.copy2(metrics_src, artifact_path(state.job_id, "metrics.json"))

    return report_path


def finalize_artifacts(state: JobState, stl_path: Path) -> list[str]:
    write_report(state, stl_path)
    return list_artifacts(state.job_id)
