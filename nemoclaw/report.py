from __future__ import annotations

import shutil
from pathlib import Path

from nemoclaw.models import JobState
from nemoclaw.store import artifact_path, job_dir, list_artifacts


def write_report(state: JobState, stl_source: Path | None = None) -> Path:
    lines = [
        "# Nemoclaw Engineering Report",
        "",
        "## User request",
        state.spec.user_request,
        "",
        "## Job specification",
        f"- Mode: `{state.spec.mode.value}`",
        f"- Discipline: `{state.spec.discipline.value}`",
        f"- Flow template: `{state.spec.flow_template}`",
        "",
        "### Objectives",
    ]
    for o in state.spec.objectives:
        lines.append(f"- {o.sense} `{o.metric}`")
    lines.append("")
    lines.append("### Constraints")
    for c in state.spec.constraints:
        lines.append(f"- `{c.metric}` {c.op} {c.value} {c.unit}".strip())
    lines.append("")
    lines.append("### Design parameters")
    for dp in state.spec.design_params:
        lines.append(f"- `{dp.name}`: [{dp.min}, {dp.max}] initial={dp.initial} {dp.unit}")
    lines.append("")
    lines.append("## Optimization passes")
    lines.append("| Pass | Feasible | Objective | Key metrics | Params |")
    lines.append("|------|----------|-----------|-------------|--------|")
    for p in state.passes:
        m = ", ".join(f"{k}={v:.4g}" for k, v in list(p.metrics.items())[:4])
        pr = ", ".join(f"{k}={v:.3g}" for k, v in p.params.items())
        lines.append(
            f"| {p.pass_index} | {p.feasible} | {p.objective_value:.4g} | {m} | {pr} |"
        )
    lines.append("")
    lines.append(f"## Stop reason\n`{state.stop_reason or 'unknown'}`")
    lines.append("")
    lines.append("## Best design parameters")
    for k, v in state.best_params.items():
        lines.append(f"- `{k}`: {v}")
    lines.append("")
    lines.append("## Recommendation")
    if state.stop_reason == "converged":
        lines.append(
            "Further parametric changes yield diminishing returns (<2% objective improvement). "
            "The attached STL reflects the best feasible candidate from the bounded pass budget."
        )
    elif state.stop_reason == "constraints_met":
        lines.append("Constraints are satisfied on the best candidate; consider validating with a finer mesh.")
    else:
        lines.append("Review pass table and constraints; additional passes may help if budget allows.")

    report_path = artifact_path(state.job_id, "REPORT.md")
    report_path.write_text("\n".join(lines) + "\n")

    if stl_source and stl_source.exists():
        shutil.copy2(stl_source, artifact_path(state.job_id, "result.stl"))

    metrics_src = job_dir(state.job_id) / "work" / "metrics.json"
    if metrics_src.exists():
        shutil.copy2(metrics_src, artifact_path(state.job_id, "metrics.json"))

    return report_path


def finalize_artifacts(state: JobState, stl_path: Path) -> list[str]:
    write_report(state, stl_path)
    return list_artifacts(state.job_id)
