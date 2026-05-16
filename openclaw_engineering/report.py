from __future__ import annotations

import json
import shutil
from pathlib import Path

from openclaw_engineering.models import JobState, GeometryKind
from openclaw_engineering.store import artifact_path, job_dir, list_artifacts


def write_report(state: JobState, stl_source: Path | None = None) -> Path:
    spec = state.spec
    lines = [
        "# OpenClaw Engineering Engineering Specification Sheet",
        "",
        "## 1. User request",
        spec.user_request,
        "",
        "## 2. Configuration",
        f"- Geometry: **{spec.geometry_kind.value}** (constrained NACA wing or defined downforce kit — no freeform blobs)",
        f"- Flow: `{spec.flow_template}`",
        f"- Vehicle: Porsche 914-6 baseline STL replaced by combined model in deliverables",
        "",
    ]
    if spec.grabcad_query:
        lines += [
            "### Reference geometry (manual)",
            f"If you need a catalog wing to tweak, search GrabCAD: {spec.grabcad_query}",
            "",
        ]

    lines += ["## 3. Design parameters (final)"]
    for k, v in state.best_params.items():
        lines.append(f"- `{k}`: {v}")
    for k, v in spec.cad_params.items():
        if k not in state.best_params:
            lines.append(f"- `{k}`: {v}")
    lines.append("")

    lines += ["## 4. Optimization iteration log"]
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

    if state.speed_sweep:
        lines += [
            "## 5. Aerodynamic speed sweep (10 mph → stock top speed)",
            "OpenFOAM-based estimates at sea-level conditions. Wing increases drag vs stock.",
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
        if state.vmax_estimated_mph:
            lines.append(
                f"**Estimated top speed with aero:** ~{state.vmax_estimated_mph:.0f} mph "
                f"(stock 914-6 reference ~{spec.fluid.get('vmax_stock_mph', 130)} mph; wing adds drag)."
            )
        lines.append("")

    if state.wing_fea:
        lines += ["## 6. Wing structural analysis (CalculiX)"]
        m = state.wing_fea.get("metrics", {})
        lines.append(f"- Max stress: **{m.get('max_stress_mpa', 'n/a')} MPa**")
        lines.append(f"- Yield reference: {state.wing_fea.get('yield_mpa', 275)} MPa (aluminum)")
        lines.append(f"- Feasible: {state.wing_fea.get('feasible')}")
        zones = state.wing_fea.get("failure_zones", [])
        if zones:
            lines.append("")
            lines.append("### Failure / reinforcement zones")
            for z in zones:
                lines.append(f"- {z}")
        if state.wing_fea.get("reinforcement_pass"):
            lines.append("")
            lines.append("### After reinforcement iteration")
            rp = state.wing_fea["reinforcement_pass"]
            lines.append(f"- Max stress: {rp.get('metrics', {}).get('max_stress_mpa')} MPa")
        lines.append("")

    if spec.geometry_kind == GeometryKind.DOWNFORCE_KIT:
        lines += [
            "## 7. Downforce kit components",
            "- Front splitter",
            "- Front air dam",
            "- Front arch louvres",
            "- Underbody diffuser",
            "- Front venturi duct (hood → windshield region)",
            "",
        ]

    lines += [
        "## 8. Deliverables",
        "- `result.stl` — full car with aero (replaces original 914 STL in OnShape when configured)",
        "- `metrics.json` — last CFD point metrics",
        "- This specification sheet",
        "",
        "## 9. Recommendation",
    ]
    if state.stop_reason == "converged":
        lines.append(
            "Optimization plateaued; geometry is a realistic wing/kit within parametric limits. "
            "Validate top-speed impact on track before high-speed runs."
        )
    else:
        lines.append("Review iteration table; additional passes may improve target downforce at design speed.")

    report_path = artifact_path(state.job_id, "REPORT.md")
    report_path.write_text("\n".join(lines) + "\n")

    if stl_source and stl_source.exists():
        shutil.copy2(stl_source, artifact_path(state.job_id, "result.stl"))
        # Archive original for traceability
        orig = job_dir(state.job_id) / "input.stl"
        if orig.exists():
            shutil.copy2(orig, artifact_path(state.job_id, "original_914.stl"))

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
