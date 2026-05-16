from pathlib import Path

from openclaw_engineering.feasibility import (
    apply_feasibility_to_spec,
    clamp_wing_params_to_envelope,
    mount_envelope_from_body,
)


def test_clamp_span_to_body():
    body = {
        "xmin": 0,
        "ymin": -400,
        "zmin": 0,
        "xmax": 4000,
        "ymax": 400,
        "zmax": 1200,
        "xspan": 4000,
        "yspan": 800,
        "zspan": 1200,
    }
    env = mount_envelope_from_body(body)
    p, notes = clamp_wing_params_to_envelope({"span_mm": 5000, "chord_root_mm": 900}, env, body)
    assert p["span_mm"] <= env["max_span_mm"] + 1
    assert p["chord_root_mm"] <= env["max_chord_mm"] + 1
    assert notes
