from pathlib import Path

from openclaw_engineering.sculpt.engine import build_sculpt


def test_wing_loft_stl(tmp_path: Path):
    spec = {
        "sculpt_method": "wing_loft",
        "params": {"span_mm": 800, "chord_root_mm": 200, "chord_tip_mm": 120, "section_count": 6},
    }
    out = tmp_path / "wing.stl"
    build_sculpt(spec, {}, out)
    assert out.exists()
    assert out.stat().st_size > 500


def test_nozzle_stl(tmp_path: Path):
    spec = {
        "sculpt_method": "nozzle_axisymmetric",
        "params": {"length_mm": 200, "throat_radius_mm": 15, "exit_radius_mm": 40},
    }
    out = tmp_path / "nozzle.stl"
    build_sculpt(spec, {}, out)
    assert out.exists()
