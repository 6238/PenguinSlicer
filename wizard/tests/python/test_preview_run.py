"""wizard/trials/preview/run.py, the layer preview trial's measuring script: the parts that need
no browser (the machine's figures, the verdict on each method and plate, the choice of method
and the report page)."""
import json

import pytest

from trials.preview import run


def test_the_processors_are_the_cgroups_quota_over_its_period():
    assert run.cgroup_cpus("800000 100000\n") == 8.0
    assert run.cgroup_cpus("150000 100000") == 1.5
    assert run.cgroup_cpus("max 100000") is None
    assert run.cgroup_cpus("") is None


def test_the_memory_is_the_cgroups_limit_in_gigabytes():
    assert run.cgroup_memory_gb("12884901888\n") == 12.0
    assert run.cgroup_memory_gb("max") is None


def measured(fps_turn=12.0, fps_layers=11.0, hold=120.0, load_hold=90.0, covered=0.3, groups_seen=4, groups_present=4,
             changes=0.2, redrawn=True):
    return {
        "turn": {"fps_typical": fps_turn, "longest_hold_ms": hold},
        "layers": {"fps_typical": fps_layers, "longest_hold_ms": hold},
        "load": {"longest_hold_ms": load_hold},
        "look": {"covered": covered, "groups_seen": groups_seen, "groups_present": groups_present,
                 "changes_with_layer": changes, "draws_after_context_lost": redrawn},
    }


def test_a_plate_passes_at_10_frames_typical_holds_within_250_ms_and_the_coarse_look():
    assert run.verdict(measured())["passes"] is True


@pytest.mark.parametrize("change, failed", [
    ({"fps_turn": 9.9}, "frames"), ({"fps_layers": 9.0}, "frames"), ({"hold": 251.0}, "hold"),
    ({"load_hold": 400.0}, "hold"), ({"covered": 0.01}, "look"), ({"groups_seen": 3}, "look"),
    ({"changes": 0.0}, "look"), ({"redrawn": False}, "look"),
])
def test_each_part_of_passing_can_fail_it(change, failed):
    v = run.verdict(measured(**change))
    assert v["passes"] is False
    assert v[failed] is False


def test_a_plate_without_supports_need_not_show_their_colour():
    assert run.verdict(measured(groups_seen=3, groups_present=3))["passes"] is True


def results_of(**fps):
    """{method: {plate: measured}} with each method's frame rate on every plate."""
    return {m: {p: measured(fps_turn=f, fps_layers=f) for p in ("a", "b", "c")} for m, f in fps.items()}


def test_the_fastest_method_that_passes_on_every_plate_is_chosen():
    results = results_of(A=0.5, B=11.0, C=14.0)
    results["C"]["b"]["turn"]["longest_hold_ms"] = 900.0          # C misses on one plate
    chosen = run.choose(results)
    assert chosen == {"method": "B", "passes": True}


def test_when_none_passes_the_fastest_is_chosen_and_the_target_is_missed():
    chosen = run.choose(results_of(A=0.5, B=6.0, C=8.0))
    assert chosen == {"method": "C", "passes": False}


def test_the_report_shows_every_method_and_plate_side_by_side_with_their_renders(tmp_path):
    results = results_of(A=0.5, C=14.0)
    for method in results.values():
        for plate in method.values():
            plate["renders"] = ["default.png"]
    page = run.report_html(results, run.choose(results), {"cpus": 8.0, "memory_gb": 12.0, "browser": "Chromium 1"},
                           render_dir=lambda m, p: f"results/{m}/{p}")
    for name in ("A", "C", ">a<", ">b<", ">c<", "results/C/b/default.png", "8.0 processors", "12.0 GB"):
        assert name in page, name
    assert "C passes" in page
    json.dumps(results)                                       # the figures are plain JSON
