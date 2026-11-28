"""The faces the wizard offers on the real parts (contracts/examples/placement/offered-faces/
real-parts.json, written by the wizard): none is a pose on which the slice service would say the
instance rests on no face of its own (slice.rests_on_an_edge), measured with the service's own
code and the default process's first layer. The wizard applies the same rule with the same
figures; this is the fast half of the agreement, without Orca. The real Orca slices every pose in
tests_orca/test_offered_faces.py.
"""
import json

import pytest

from helpers import CONTRACTS
from penguin_slice.mesh import contact_area_mm2, first_layer_section, read_binary_stl
from penguin_slice.plate import turn_matrix, turn_of
from penguin_slice.plate_configuration import FIRST_LAYER_MM, FIRST_LINE_MM, REST_AREA_MM2

OFFERED = json.loads((CONTRACTS / "examples" / "placement" / "offered-faces" / "real-parts.json").read_text())
REAL_PARTS = CONTRACTS / "examples" / "parts" / "real"


@pytest.fixture(scope="module")
def meshes():
    return {ref: read_binary_stl((REAL_PARTS / f"{ref}.stl").read_bytes(), part["name"])
            for ref, part in OFFERED["parts"].items()}


def test_the_wizard_offers_no_pose_the_slice_service_says_rests_on_an_edge(meshes):
    resting = []
    for pose in OFFERED["poses"]:
        instance = pose["instance"]
        mesh, matrix = meshes[instance["ref"]], turn_matrix(turn_of(instance))
        if (contact_area_mm2(mesh, matrix) < REST_AREA_MM2
                and first_layer_section(mesh, matrix, FIRST_LAYER_MM / 2).buffer(-FIRST_LINE_MM / 2).is_empty):
            resting.append(pose["id"])
    assert resting == []
