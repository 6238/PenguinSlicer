#!/usr/bin/env python3
"""Slice the reference plates with the real Orca and record time and peak memory, so the
memory model in penguin_slice/limits.py can be refitted.

Standard library, numpy and the slice service's package. One plate at a time, each run
through the code that ships (plate_3mf.py writes the plate, slicer.slice_plate slices it,
the name guard reads it back); the peak is the slice service's memory watchdog's reading of
Orca's processes (the rows in slice/README-details.md before Fri 2026-11-20 used Orca's ru_maxrss from
wait4; on the spacer plates of that day the two read the same), and the watchdog stops a slice that passes MEASURE_STOP_MB (3 GB).

    uv run --project slice python slice/scripts/measure_plate.py --list
    uv run --project slice python slice/scripts/measure_plate.py --plate organic-1 --out results.jsonl
    uv run --project slice python slice/scripts/measure_plate.py --fit results.jsonl

Each measurement prints one line and, with --out, appends one JSON object to the file:
plate, instances, triangles, volume_cm3 (the memory model's volume), supports, estimate_mb
(the model's estimate), peak_mb, seconds, cpu_s, sliced_bytes, verdict (ok, failed, over:
stopped at the stop rule). --fit reads such a file and prints the least-squares fit of
MEMORY_BASE_MB, MEMORY_PER_INSTANCE_MB and MEMORY_PER_CM3_MB over the rows with supports off,
and MEMORY_SUPPORTS_FACTOR from the rows with supports on.

The parts are synthetic and deterministic: a hub (a 40 x 20 mm ring with a 12 mm bore and
3 mm fillets, revolved into near-square facets, as a finely tessellated exported part is),
a tube spacer, a flat gusset, a box, and a lumpy closed "organic" body about 110 x 90 x
100 mm (about the Stanford bunny's size and volume), all watertight.
"""
import argparse
import json
import math
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

from penguin_slice import limits
from penguin_slice.mesh import analyse, orientation_footprints, read_binary_stl
from penguin_slice.plate_3mf import write_plate_3mf
from penguin_slice.print_config import validate_overrides, write_process_with_overrides
from penguin_slice.slicer import (DEFAULT_PROFILES, MEMORY_STOP_REASON as STOPPED_AT_CEILING, SliceError,
                                  SliceProfiles, plate_object_names, slice_plate)

HUB_OUTER_MM = 20.0        # radius: 40 mm across
HUB_BORE_MM = 6.0          # radius: a 12 mm bore
HUB_HEIGHT_MM = 20.0
HUB_FILLET_MM = 3.0
PITCH_MM = 50.0            # grid pitch: a 10 mm gap between 40 mm hubs
GRID_ORIGIN_MM = 40.0
GRID_COLUMNS = 6           # 6 x 5 covers FULL_SMALL_HUBS on the 340 x 320 mm plate
FULL_SMALL_HUBS = 25       # the full-small plate: the old cap of 25 instances, kept so the rows stay comparable
# Supports on and off as the measurements were made: Orca's automatic tree supports.
SUPPORTS_ON = {"enable_support": "1", "support_type": "tree(auto)"}
SUPPORTS_OFF = {"enable_support": "0"}


def _hub_profile():
    """The hub's cross-section in (r, z): a rounded rectangle, as a dense closed polyline
    running bottom, outer wall, top, bore, and its total length."""
    r0, r1, h, f = HUB_BORE_MM, HUB_OUTER_MM, HUB_HEIGHT_MM, HUB_FILLET_MM
    corners = [((r1 - f, f), -math.pi / 2), ((r1 - f, h - f), 0.0),
               ((r0 + f, h - f), math.pi / 2), ((r0 + f, f), math.pi)]
    points = []
    for (cr, cz), a0 in corners:
        for t in np.linspace(a0, a0 + math.pi / 2, 64):
            points.append((cr + f * math.cos(t), cz + f * math.sin(t)))
    points.append(points[0])
    poly = np.array(points)
    seg = np.hypot(*np.diff(poly, axis=0).T)
    return poly, np.concatenate([[0.0], np.cumsum(seg)])


def _revolve(r, z, segments):
    """A closed surface of revolution of the closed (r, z) loop: vertices, faces."""
    profile = len(r)
    angles = np.linspace(0.0, 2.0 * np.pi, segments, endpoint=False)
    vertices = np.stack([np.outer(r, np.cos(angles)), np.outer(r, np.sin(angles)),
                         np.repeat(np.asarray(z)[:, None], segments, axis=1)], axis=2).reshape(-1, 3)
    i = np.arange(profile)[:, None]
    j = np.arange(segments)[None, :]
    a = i * segments + j
    b = ((i + 1) % profile) * segments + j
    c = ((i + 1) % profile) * segments + (j + 1) % segments
    d = i * segments + (j + 1) % segments
    faces = np.concatenate([np.stack([a, c, b], axis=-1).reshape(-1, 3),
                            np.stack([a, d, c], axis=-1).reshape(-1, 3)])
    return vertices, faces


def hub_mesh(triangles):
    """A closed hub mesh of at most `triangles` triangles: vertices (n, 3), faces (m, 3)."""
    poly, along = _hub_profile()
    length = along[-1]
    mean_circumference = math.pi * (HUB_OUTER_MM + HUB_BORE_MM)
    quads = triangles // 2
    segments = max(8, round(math.sqrt(quads * mean_circumference / length)))
    profile = max(8, quads // segments)
    stations = np.linspace(0.0, length, profile, endpoint=False)
    r = np.interp(stations, along, poly[:, 0])
    z = np.interp(stations, along, poly[:, 1])
    z[np.abs(z) < 1e-9] = 0.0                     # the flat base is exactly on z = 0
    return _revolve(r, z, segments)


def tube_mesh(outer=10.0, inner=6.0, height=25.0, segments=96):
    """A tube spacer: a rectangle (r, z) loop revolved."""
    r = np.array([inner, outer, outer, inner])
    z = np.array([0.0, 0.0, height, height])
    return _revolve(r, z, segments)


def box_mesh(sx, sy, sz):
    corners = np.array([[dx * sx, dy * sy, dz * sz] for dz in (0, 1) for dy in (0, 1) for dx in (0, 1)], float)
    faces = np.array([(0, 2, 1), (1, 2, 3), (4, 5, 6), (5, 7, 6), (0, 1, 4), (1, 5, 4),
                      (2, 6, 3), (3, 6, 7), (0, 4, 2), (2, 4, 6), (1, 3, 5), (3, 7, 5)])
    return corners, faces


def organic_mesh(rows=200, cols=250, size=(110.0, 90.0, 100.0)):
    """A lumpy closed body: a sphere with smooth bumps, scaled to `size`, poles closed."""
    theta = np.linspace(0, np.pi, rows + 2)[1:-1]
    phi = np.linspace(0, 2 * np.pi, cols, endpoint=False)
    t, p = np.meshgrid(theta, phi, indexing="ij")
    radius = 1.0 + 0.12 * np.sin(3 * t) * np.cos(2 * p) + 0.08 * np.sin(5 * p + t) * np.sin(t)
    xyz = np.stack([radius * np.sin(t) * np.cos(p), radius * np.sin(t) * np.sin(p), radius * np.cos(t)], -1)
    ring = xyz.reshape(-1, 3)
    vertices = np.vstack([ring, [[0, 0, 1.0]], [[0, 0, -1.0]]])
    top, bottom = len(ring), len(ring) + 1
    faces = []
    i = np.arange(rows - 1)[:, None]
    j = np.arange(cols)[None, :]
    a, b = i * cols + j, i * cols + (j + 1) % cols
    c, d = (i + 1) * cols + (j + 1) % cols, (i + 1) * cols + j
    faces.append(np.stack([a, d, c], -1).reshape(-1, 3))
    faces.append(np.stack([a, c, b], -1).reshape(-1, 3))
    jj = np.arange(cols)
    faces.append(np.stack([np.full(cols, top), jj, (jj + 1) % cols], -1))
    last = (rows - 1) * cols
    faces.append(np.stack([np.full(cols, bottom), last + (jj + 1) % cols, last + jj], -1))
    vertices = vertices - vertices.min(axis=0)
    vertices = vertices / vertices.max(axis=0) * np.asarray(size)
    return vertices, np.concatenate(faces)


def mesh_stl(vertices, faces, label=b"slice service measure_plate"):
    """A binary STL of an indexed mesh, with real normals."""
    tris = np.asarray(vertices, dtype=np.float64)[faces]
    normals = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    normals /= np.linalg.norm(normals, axis=1, keepdims=True)
    record = np.dtype([("normal", "<f4", 3), ("v", "<f4", (3, 3)), ("attr", "<u2")])
    body = np.zeros(len(tris), dtype=record)
    body["normal"] = normals
    body["v"] = tris
    return label.ljust(80, b"\0") + np.uint32(len(tris)).tobytes() + body.tobytes()


def hub_stl(triangles):
    return mesh_stl(*hub_mesh(triangles))


def grid_centres(count):
    return [(GRID_ORIGIN_MM + PITCH_MM * (n % GRID_COLUMNS), GRID_ORIGIN_MM + PITCH_MM * (n // GRID_COLUMNS))
            for n in range(count)]


def plate_layout(stl_path, instances):
    """The plate as plate_3mf.py takes it: `instances` hubs, upright, on the grid."""
    stl = Path(stl_path).read_bytes()
    parts = {"hub": {"name": "Hub", "stl_path": Path(stl_path),
                     "footprints": orientation_footprints(read_binary_stl(stl, "Hub"))}}
    placed = [{"ref": "hub", "orientation": "+z", "angle": 0, "x": x, "y": y} for x, y in grid_centres(instances)]
    return placed, parts


# The reference plates (restart notes section 6.9): name -> (parts {ref: stl builder},
# instances [(ref, x, y)], supports). Placements keep 5 mm between footprints.
def _organic_row(count):
    return [("organic", 70.0 + 125.0 * k, 160.0) for k in range(count)] if count <= 2 else \
        [("organic", 65.0, 70.0), ("organic", 185.0, 70.0), ("organic", 125.0, 230.0)]


REFERENCE_PLATES = {
    "mechanism": ({"hub": lambda: hub_stl(20_000), "tube": lambda: mesh_stl(*tube_mesh()),
                   "gusset": lambda: mesh_stl(*box_mesh(60, 40, 5)), "block": lambda: mesh_stl(*box_mesh(100, 60, 30))},
                  [("hub", 40, 40), ("hub", 95, 40), ("tube", 150, 40), ("tube", 180, 40), ("tube", 210, 40),
                   ("tube", 240, 40), ("gusset", 60, 120), ("gusset", 140, 120), ("block", 260, 140)], False),
    "full-small": ({"hub": lambda: hub_stl(12_000)},
                   [("hub", x, y) for x, y in grid_centres(FULL_SMALL_HUBS)], False),
    "organic-1": ({"organic": lambda: mesh_stl(*organic_mesh())}, _organic_row(1), False),
    "organic-2": ({"organic": lambda: mesh_stl(*organic_mesh())}, _organic_row(2), False),
    "organic-3": ({"organic": lambda: mesh_stl(*organic_mesh())}, _organic_row(3), False),
    "organic-1-supports": ({"organic": lambda: mesh_stl(*organic_mesh())}, _organic_row(1), True),
    "organic-3-supports": ({"organic": lambda: mesh_stl(*organic_mesh())}, _organic_row(3), True),
    "mechanism-supports": (None, None, True),
}


def plate_definition(name):
    parts, instances, supports = REFERENCE_PLATES[name]
    if parts is None:                                     # the same plate as its base, supports on
        parts, instances, _ = REFERENCE_PLATES[name.removesuffix("-supports")]
    return parts, instances, supports


def measure(name, stop_mb=limits.MEASURE_STOP_MB):
    """Slice one reference plate under the slice service's memory watchdog with the
    ceiling `stop_mb`; its result dict."""
    builders, placed_instances, supports = plate_definition(name)
    with tempfile.TemporaryDirectory(prefix="measure_plate_") as tmp:
        work = Path(tmp)
        parts, volumes, triangles = {}, {}, {}
        for ref, build in builders.items():
            stl = build()
            path = work / f"{ref}.stl"
            path.write_bytes(stl)
            mesh = read_binary_stl(stl, ref.capitalize())
            parts[ref] = {"name": ref.capitalize(), "stl_path": path, "footprints": orientation_footprints(mesh)}
            volumes[ref] = analyse(mesh)["volume_mm3"]
            triangles[ref] = mesh.triangles
        instances = [{"ref": ref, "orientation": "+z", "angle": 0, "x": float(x), "y": float(y)}
                  for ref, x, y in placed_instances]
        names = write_plate_3mf(work / "plate.3mf", instances, parts)
        process = write_process_with_overrides(DEFAULT_PROFILES.process,
                                               validate_overrides(SUPPORTS_ON if supports else SUPPORTS_OFF),
                                               work / "process.json")
        profiles = SliceProfiles(DEFAULT_PROFILES.printer, DEFAULT_PROFILES.filament, process)
        instance_volumes = [volumes[c["ref"]] for c in instances]
        row = {"plate": name, "instances": len(instances), "triangles": sum(triangles[c["ref"]] for c in instances),
               "volume_cm3": round(sum(instance_volumes) / 1000, 1), "supports": supports,
               "estimate_mb": limits.estimate_peak_mb(instance_volumes, supports)}
        started = time.monotonic()
        try:
            result = slice_plate(work / "plate.3mf", profiles, work / "slice", memory_ceiling_mb=stop_mb)
            names_ok = sorted(plate_object_names(result.output_path)) == sorted(names)
            row.update(peak_mb=round(result.peak_rss_kb / 1024), sliced_bytes=result.output_path.stat().st_size,
                       verdict="ok" if names_ok else "failed")
        except SliceError as exc:
            over = exc.reason == STOPPED_AT_CEILING
            row.update(peak_mb=round((exc.peak_rss_kb or 0) / 1024), verdict="over" if over else "failed")
            if not over:
                row["error"] = exc.error_code
        row["seconds"] = round(time.monotonic() - started, 1)
    return row


def _model(base, per_instance, per_cm3, factor):
    return {"MEMORY_BASE_MB": round(float(base), 1), "MEMORY_PER_INSTANCE_MB": round(float(per_instance), 2),
            "MEMORY_PER_CM3_MB": round(float(per_cm3), 3),
            "MEMORY_SUPPORTS_FACTOR": round(float(factor), 2) if factor is not None else None}


def fit(rows):
    """Two fits of peak = base + per_instance * instances + per_cm3 * volume over the rows with
    supports off, each with its supports factor from the supported rows:

    - least_squares: the best fit, with the mean ratio of a supported plate to it;
    - envelope: the upper envelope, which never estimates below a peak of these rows, with
      the least total over-estimate (base and per_instance on a 5 MB / 0.5 MB grid, per_cm3
      the least that covers every row), and the largest supported ratio.
    """
    plain = [r for r in rows if not r["supports"] and r["verdict"] == "ok"]
    if len(plain) < 3:
        raise SystemExit("--fit needs at least three rows with supports off and verdict ok")
    supported = [r for r in rows if r["supports"] and r["verdict"] == "ok"]
    a = np.array([[1.0, r["instances"], r["volume_cm3"]] for r in plain])
    y = np.array([r["peak_mb"] for r in plain], dtype=float)
    (base, per_instance, per_cm3), *_ = np.linalg.lstsq(a, y, rcond=None)
    ratios = [r["peak_mb"] / (base + per_instance * r["instances"] + per_cm3 * r["volume_cm3"]) for r in supported]
    best = None
    for env_base in np.arange(0.0, 300.1, 5.0):
        for env_instance in np.arange(0.0, 40.01, 0.5):
            need = max((r["peak_mb"] - env_base - env_instance * r["instances"]) / r["volume_cm3"] for r in plain)
            env_cm3 = max(float(need), 0.0)
            over = sum(env_base + env_instance * r["instances"] + env_cm3 * r["volume_cm3"] - r["peak_mb"] for r in plain)
            if best is None or over < best[0] - 1e-9:
                best = (over, env_base, env_instance, env_cm3)
    _over, env_base, env_instance, env_cm3 = best
    env_ratios = [r["peak_mb"] / (env_base + env_instance * r["instances"] + env_cm3 * r["volume_cm3"]) for r in supported]
    return {"least_squares": _model(base, per_instance, per_cm3, np.mean(ratios) if ratios else None),
            "envelope": _model(env_base, env_instance, env_cm3, max(env_ratios) if env_ratios else None),
            "rows": len(plain), "supported_rows": len(supported)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--plate", choices=sorted(REFERENCE_PLATES))
    group.add_argument("--list", action="store_true", help="list the reference plates")
    group.add_argument("--fit", metavar="RESULTS", help="fit the memory model to a results file")
    parser.add_argument("--out", help="append the result as one JSON line to this file")
    args = parser.parse_args(argv)
    if args.list:
        for name in sorted(REFERENCE_PLATES):
            _parts, instances, supports = plate_definition(name)
            print(f"{name}: {len(instances)} instances, supports {'on' if supports else 'off'}")
        return 0
    if args.fit:
        rows = [json.loads(line) for line in Path(args.fit).read_text().splitlines() if line.strip()]
        print(json.dumps(fit(rows), indent=2))
        return 0
    row = measure(args.plate)
    print(json.dumps(row))
    if args.out:
        with open(args.out, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")
    return 0 if row["verdict"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
