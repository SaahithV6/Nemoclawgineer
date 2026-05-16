from nemoclaw.planner import _heuristic_plan


def test_heuristic_fea_optimize():
    spec = _heuristic_plan("Lighten bracket max stress 200 MPa 500 N load", "input.stl")
    assert spec.discipline.value == "fea"
    assert spec.loads.get("force_n") == 500.0
    assert any(c.metric == "max_stress_mpa" for c in spec.constraints)


def test_heuristic_cfd():
    spec = _heuristic_plan("Report drag and lift at 15 m/s", None)
    assert spec.discipline.value == "cfd"
