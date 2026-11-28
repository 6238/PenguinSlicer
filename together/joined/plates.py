"""Plate configurations as the wizard makes them (contracts/plate-configuration.md, "From a
profile to a plate configuration"): the parts by name, hash and units, the instances where
the Layout step put them, the chosen profile's three names and its overrides."""

from dataclasses import dataclass

from .page import local_time, new_id
from .paths import REAL_PARTS

#: Real parts of the Popcorn Penguins' robot (contracts/examples/parts/real/), in millimetres.
CLAMP_PLATE = REAL_PARTS / "clamp-plate-inner.stl"    # 4.762 x 50.8 x 50.8 mm, 437,884 bytes
PULLEY = REAL_PARTS / "pulley-v3.stl"                 # 17.78 x 19.05 x 19.05 mm, 230,484 bytes
ELEVATOR_TOP = REAL_PARTS / "elevator-top-inner.stl"  # 50.8 x 25.4 x 57.15 mm, 969,684 bytes


@dataclass
class Placed:
    """One part on the plate: its key, its name, its record from the upload, and where each
    of its instances sits, `(orientation, angle, x, y)`."""

    key: str
    name: str
    record: dict
    instances: list


def first_profile(configuration):
    """The configuration's first filament's first profile, as the Settings step offers it."""
    return configuration["filaments"][0]["profiles"][0]


def plate(placed, profile, *, plate_id=None, submission_id=None, overrides=None):
    """The plate configuration of `placed` (Placed, …) sliced with `profile`."""
    merged = dict(profile.get("overrides") or {})
    merged.update(overrides or {})
    configuration = {
        "plate_id": plate_id or new_id(),
        "submission_id": submission_id or new_id(),
        "parts": {p.key: {"name": p.name, "sha256": p.record["sha256"], "units": p.record["units"]}
                  for p in placed},
        "instances": [{"ref": p.key, "orientation": orientation, "angle": angle, "x": x, "y": y}
                      for p in placed for orientation, angle, x, y in p.instances],
        "printer": profile["printer"],
        "filament": profile["filament"],
        "process": profile["process"],
        "local_time": local_time(),
    }
    if merged:
        configuration["overrides"] = merged
    return configuration


def clamp_plate(page, *, x=100.0, y=100.0, **changes):
    """The clamp plate uploaded and laid flat once on a plate of its own, with the first
    profile of the configuration the page reads: the plate configuration."""
    profile = first_profile(page.configuration()["configuration"])
    record = page.upload(CLAMP_PLATE)
    return plate([Placed("clamp", "Clamp Plate Inner", record, [("+x", 0, x, y)])], profile,
                 **changes)


def upload_missing(page, refusal):
    """What the page does on `slice.part_missing` with `missing_parts`: upload each listed
    part again from the browser's storage, with its units. Gives the keys uploaded."""
    by_key = {"clamp": CLAMP_PLATE, "pulley": PULLEY, "elevator": ELEVATOR_TOP}
    report = refusal.report
    assert report["code"] == "slice.part_missing" and report["action"] == "refresh_parts"
    keys = []
    for missing in report["where"]["missing_parts"]:
        record = page.upload(by_key[missing["key"]], units=missing["units"])
        assert record["sha256"] == missing["sha256"]
        keys.append(missing["key"])
    return keys


def again(configuration, *, submission_id=None):
    """The same plate submitted again, as Slice again and the page's own submitting again
    do: the same `plate_id`, a new `submission_id`."""
    return dict(configuration, submission_id=submission_id or new_id())
