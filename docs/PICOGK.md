# PicoGK integration (optional)

[LEAP71 PicoGK](https://picogk.org) is a compact **voxel / lattice / implicit** geometry kernel (OpenVDB-based). OpenClaw Engineering calls it when `sculpt_method` is `picogk_field` and PicoGK is enabled.

## Platform support (read this)

| Platform | Official support | Brev Ubuntu 24.04 x64 |
|----------|------------------|------------------------|
| Windows x64 | Yes (NuGet) | N/A |
| macOS Apple Silicon | Yes (NuGet) | N/A |
| Linux x64 | Community / build [PicoGKRuntime](https://github.com/leap71/PicoGKRuntime) | Try `dotnet` + NuGet; known STL/TBB issues — use `xvfb-run` |

If PicoGK fails on Brev, the executor **automatically falls back** to internal `sdf_compose` (similar implicit workflow, no PicoGK binary).

## Enable on Brev

```bash
# .NET 9 SDK (setup.sh may already install)
sudo apt-get install -y dotnet-sdk-9.0 xvfb

# ~/.openclaw-engineering/.env
OPENCLAW_ENGINEERING_PICOGK_ENABLED=1
# If you built PicoGKRuntime locally:
# PICOGK_RUNTIME_PATH=/path/to/libPicoGK.so
```

```bash
cd ~/openclaw-engineering/picogk_driver
dotnet build -c Release
openclaw-engineering-doctor   # shows picogk.ready
```

## Pipeline: job.json → STL

The driver (`picogk_driver/`) runs headless:

```bash
xvfb-run -a dotnet run --project picogk_driver -c Release -- job.json out.stl
```

### Job schema

```json
{
  "voxel_size_mm": 0.5,
  "operations": [
    {"type": "stl_import", "path": "/path/body.stl", "boolean": "add"},
    {"type": "sphere", "center": [0, 0, 120], "radius": 35, "boolean": "add"},
    {"type": "beam", "a": [0, 0, 100], "b": [80, 0, 140], "radius": 5, "boolean": "add"},
    {"type": "sphere", "center": [20, 0, 130], "radius": 15, "boolean": "subtract"}
  ]
}
```

### Operation types

| type | PicoGK API | Fields |
|------|------------|--------|
| `sphere` | `Voxels.voxSphere` | `center` [x,y,z], `radius` mm, `boolean` |
| `beam` | `Lattice.AddBeam` → `Voxels` | `a`, `b` points, `radius` mm |
| `stl_import` | `Mesh.mshFromStlFile` → `Voxels` | `path`, `scale`, `boolean` |
| `cube` | `Utils.voxCube` | `center`, `size` mm |

### Boolean mode (`boolean` on each op)

| Value | PicoGK |
|-------|--------|
| `add`, `union`, `+` | `voxA + voxB` |
| `subtract`, `sub`, `-` | `voxA - voxB` |
| `intersect`, `&` | `voxA & voxB` |

Export: `Mesh msh = new Mesh(voxels); msh.SaveToStlFile(path, EStlUnit.MM)`.

## JobSpec / Nemotron

```json
{
  "geometry_spec": {
    "sculpt_method": "picogk_field",
    "params": {
      "voxel_size_mm": 0.5,
      "spheres": [{"center": [0, 0, 50], "radius_mm": 30, "boolean": "add"}],
      "beams": [{"a": [0,0,0], "b": [100,0,0], "radius_mm": 4, "boolean": "add"}]
    }
  }
}
```

MCP: `openclaw_engineering_picogk_status`, `openclaw_engineering_list_sculpt_methods`.

## Python bindings (alternative)

[pycogk](https://pypi.org/project/pycogk/) wraps PicoGK with bundled runtimes for **win-x64** and **osx-arm64** only. Set `PICOGK_RUNTIME_PATH` for custom Linux builds. The executor tries pycogk first, then `dotnet` driver.

## ShapeKernel / TPMS (advanced)

[LEAP71_ShapeKernel](https://github.com/leap71/LEAP71_ShapeKernel) builds on PicoGK for higher-level frames and lattices. Future sculpt ops can add C# references or separate driver tasks; for now use `operations[]` or fall back to `sdf_compose`.

## References

- https://picogk.org/doc/setup.html  
- https://github.com/leap71/PicoGK  
- https://github.com/leap71/PicoGK_Examples (BooleanShowCase → STL export)  
- Discussion #83 — Linux STL / TBB issues  
