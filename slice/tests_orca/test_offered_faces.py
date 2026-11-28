"""The real Orca as the oracle of the faces the wizard offers. The wizard writes every face it
offers to lay each real part on as one pose (contracts/examples/placement/offered-faces/
real-parts.json, `make -C wizard offered-faces`); each pose is sliced here, through the HTTP
interface, as a plate of that one instance over the default set of profiles with supports off,
and every one must slice. All the poses are sliced: about 75 s in all on an aarch64 Linux
machine with 8 CPUs (slice/README-details.md, "The faces the wizard offers").

Protects: that the wizard offers no face the pinned Orca cannot slice (a hull face that bridges
a hollow, so that the part touches the plate only along edges, is refused,
slice.rests_on_an_edge). A new Orca, or a change to the wizard's rules, that breaks it fails
here; tests/test_offered_faces.py checks the slice service's own rule on the same poses without
Orca.
"""
import json
import time

import pytest

from helpers import CONTRACTS
from measure_plate import SUPPORTS_OFF
from test_orca import through_the_http_interface

OFFERED = json.loads((CONTRACTS / "examples" / "placement" / "offered-faces" / "real-parts.json").read_text())
REAL_PARTS = CONTRACTS / "examples" / "parts" / "real"
POSES = OFFERED["poses"]


def plate_of(pose):
    """The phase 2 plate configuration of the pose's one instance, over the default set, with
    supports off."""
    ref = pose["instance"]["ref"]
    return {"plate_id": "offered-faces", "submission_id": pose["id"], "parts": {ref: OFFERED["parts"][ref]},
            "instances": [pose["instance"]], "overrides": dict(SUPPORTS_OFF)}


def test_every_real_part_has_poses():
    assert {pose["instance"]["ref"] for pose in POSES} == set(OFFERED["parts"])


@pytest.mark.parametrize("pose", POSES, ids=[pose["id"] for pose in POSES])
def test_every_offered_face_slices(tmp_path, pose):
    ref = pose["instance"]["ref"]
    started = time.monotonic()
    _stages, report, data, summary = through_the_http_interface(tmp_path / "work", plate_of(pose),
                                                                [(REAL_PARTS / f"{ref}.stl").read_bytes()])
    error = json.dumps(report["error"])[:400] if report.get("error") else ""
    print(f"\n[orca] {pose['id']} ({pose['patch']['kind']}, {pose['patch']['area_mm2']} mm², area rank "
          f"{pose['area_rank']}, orient rank {pose['orient_rank']}): {report['state']} in "
          f"{time.monotonic() - started:.1f} s {error}")
    assert report["state"] == "done", report.get("error")
    assert data and summary["instances"] == 1
