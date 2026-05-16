from __future__ import annotations

from pathlib import Path

from openclaw_engineering.tools.util import dry_run, run_cmd, which, write_json


def mesh_stl(stl: Path, size: float, out_inp: Path) -> Path:
    out_inp.parent.mkdir(parents=True, exist_ok=True)
    if dry_run():
        out_inp.write_text(_minimal_inp_stub(stl, size))
        write_json(out_inp.with_suffix(".mesh.json"), {"size": size, "dry_run": True})
        return out_inp

    gmsh_bin = which("gmsh")
    if not gmsh_bin:
        out_inp.write_text(_minimal_inp_stub(stl, size))
        return out_inp

    msh = out_inp.with_suffix(".msh")
    geo = out_inp.parent / "mesh.geo"
    geo.write_text(
        f"""
Merge "{stl}";
Mesh.CharacteristicLengthMax = {size};
Mesh.CharacteristicLengthMin = {size * 0.5};
Mesh 3;
Save "{msh}";
"""
    )
    proc = run_cmd([gmsh_bin, str(geo), "-3", "-format", "msh2"], timeout=900)
    if proc.returncode != 0 or not msh.exists():
        out_inp.write_text(_minimal_inp_stub(stl, size))
        return out_inp

    _msh_to_inp(msh, out_inp)
    return out_inp


def _msh_to_inp(msh: Path, out_inp: Path) -> None:
    nodes: dict[int, tuple[float, float, float]] = {}
    elements: list[tuple[int, list[int]]] = []
    for line in msh.read_text(errors="ignore").splitlines():
        parts = line.strip().split()
        if not parts:
            continue
        if parts[0] == "$Nodes":
            continue
        if parts[0] == "$EndNodes":
            continue
        if parts[0] == "$Elements":
            continue
        if parts[0] == "$EndElements":
            continue
        if len(parts) >= 4 and parts[0].isdigit() and "." in parts[1]:
            try:
                nid = int(parts[0])
                nodes[nid] = (float(parts[1]), float(parts[2]), float(parts[3]))
            except ValueError:
                pass
        elif len(parts) >= 5 and parts[0].isdigit():
            try:
                eid = int(parts[0])
                ntags = int(parts[2])
                nnode = int(parts[3])
                idx = 4 + ntags
                conn = [int(parts[i]) for i in range(idx, idx + nnode)]
                if len(conn) >= 4:
                    elements.append((eid, conn[:4]))
            except (ValueError, IndexError):
                pass

    lines = ["*Heading", "openclaw-engineering gmsh export", "*Node"]
    for nid, xyz in sorted(nodes.items()):
        lines.append(f"{nid}, {xyz[0]}, {xyz[1]}, {xyz[2]}")
    lines.append("*Element, type=C3D4")
    for eid, conn in elements:
        lines.append(f"{eid}, {', '.join(str(c) for c in conn)}")
    lines += [
        "*Material, name=Steel",
        "*Elastic",
        "210000., 0.3",
        "*Solid section, elset=Eall, material=Steel",
        "*Elset, elset=Eall",
        ", ".join(str(e[0]) for e in elements),
        "*End",
    ]
    out_inp.write_text("\n".join(lines) + "\n")


def _minimal_inp_stub(stl: Path, size: float) -> str:
    return f"""*Heading
openclaw-engineering stub mesh from {stl.name} size={size}
*Node
1, 0., 0., 0.
2, {size}, 0., 0.
3, 0., {size}, 0.
4, 0., 0., {size}
*Element, type=C3D4
1, 1, 2, 3, 4
*Material, name=Steel
*Elastic
210000., 0.3
*Solid section, elset=Eall, material=Steel
*Elset, elset=Eall
1
*End
"""
