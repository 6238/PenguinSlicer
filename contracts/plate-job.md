# Plate job

What the slice service slices: the parts as STL files, where each copy of a part sits on
the plate and how it is turned, and the printer, filament and process profiles with their
setting overrides. One plate job is one plate and gives one [sliced file](sliced-file.md).

A plate job is a JSON object. A plate job file's STL paths are read against the folder the
file is in.

## Fields

| Field | Type | Required | Meaning |
|---|---|---|---|
| `parts` | object | yes | The parts, each under a key of its own (see Part). Only parts a copy names are read. |
| `copies` | array | yes | The copies on the plate, at least one and at most `MAX_COPIES` (see Copy). |
| `printer` | string | no | The printer profile's name, from the catalog. Left out: the default set (see Profiles). |
| `filament` | string | with `printer` | The filament profile's name, from the catalog, fitting the printer. |
| `process` | string | with `printer` | The process profile's name, from the catalog, fitting the printer. |
| `overrides` | object | no | Settings that replace the process profile's (see Overrides). |
| `local_time` | string | no | The caller's local time as `YYYYMMDD-HHMM`, used in the sliced file's name. Anything else, or left out: the slice service's UTC time. |

Fields not listed here are ignored.

### Part

The key of a part is 1 to 64 letters, digits, `-` or `_`.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `name` | string | yes | The part's name, not empty. It names the part's copies (see Copy) and the sliced file. |
| `stl` | string | yes | The part's binary STL file, in millimetres: an absolute path, or one relative to the plate job file. |

### Copy

| Field | Type | Required | Meaning |
|---|---|---|---|
| `ref` | string | yes | The key of the part this is a copy of. |
| `orientation` | string | yes | Which axis of the part points up: one of `+z`, `-z`, `+x`, `-x`, `+y`, `-y` (see Coordinates). |
| `angle` | integer | yes | Whole degrees, 0 to 359, that the copy turns counterclockwise seen from above. |
| `x` | number | yes | Where the centre of the copy's footprint goes on the plate, in millimetres. |
| `y` | number | yes | The same, along the plate's other axis. |

Each copy is named `<part name> #<n>`, the part name reduced to letters, digits, `-` and
`_` (every other character becomes `_`, at most 40 characters, `part` when nothing is
left), and `n` counting copies of the same reduced name from 1 in the order of `copies`.
Two different parts both named `Bracket` give `Bracket #1` and `Bracket #2`. The printer
shows these names in its list of objects to skip.

## Coordinates

**The part.** The STL's own coordinates, in millimetres, with any origin. The slice service
never moves the part's mesh itself; it only places copies of it.

**The plate.** Millimetres, z up, x and y as in the printer profile's `printable_area`
(on every printer in the catalog today, x from 0 to 340 and y from 0 to 320). The
printable height is the profile's
`printable_height` (340 mm today).

**A copy** is placed in three steps:

1. **Orientation.** The part is turned so that the named axis of the part points up:
   `+z` is the part as modelled, `-z` upside down, `+x` resting on its -x face, and so on.
   The turn applied to each vertex `v` is `v' = M v` with these row-major matrices:

   | Orientation | M |
   |---|---|
   | `+z` | `((1, 0, 0), (0, 1, 0), (0, 0, 1))` |
   | `-z` | `((1, 0, 0), (0, -1, 0), (0, 0, -1))` |
   | `+x` | `((0, 0, -1), (0, 1, 0), (1, 0, 0))` |
   | `-x` | `((0, 0, 1), (0, 1, 0), (-1, 0, 0))` |
   | `+y` | `((1, 0, 0), (0, 0, -1), (0, 1, 0))` |
   | `-y` | `((1, 0, 0), (0, 0, 1), (0, -1, 0))` |

2. **Footprint.** Seen from above, the turned part's footprint is the convex hull of its
   vertices. Its centre is the centre of the turned part's bounding box in x and y.
3. **Angle and position.** The copy turns by `angle` about the vertical line through the
   footprint's centre, the centre goes to (`x`, `y`), and the copy's lowest point goes to
   z = 0.

As one transform: `p_plate = Rz(angle) M p_part + t`, with
`t = (x, y, 0) - Rz(angle) offset`, where `offset` is the footprint centre and the lowest z
of the turned part.

## Profiles

Profiles are named by Orca Slicer's own names. The catalog of names the slice service
knows, with the printers each filament and process fits, is
[slice/src/penguin_slice/profiles/catalog/index.json](../slice/src/penguin_slice/profiles/catalog/index.json).

- With `printer`: the printer must be in the catalog, and `filament` and `process` must be
  catalog entries that fit it.
- Without `printer`: the default set, a Bambu Lab H2S with the 0.6 mm High Flow nozzle
  (`Bambu Lab H2S 0.6 nozzle`), `Generic PETG @BBL H2S` and
  `0.24mm Balanced Quality @BBL H2S 0.6 nozzle`. `filament` and `process` may then be left
  out or must name those two.

## Overrides

Each override is optional; its value must be one of the listed values, of the listed type.

| Override | Values | Orca setting |
|---|---|---|
| `infill` | 10, 15, 20, 30, 40, 60, 100 | `sparse_infill_density` = `<value>%` |
| `walls` | 2, 3, 4, 6 | `wall_loops` |
| `supports` | `"off"`, `"on"` | `enable_support` 0, or 1 with `support_type` `tree(auto)` |
| `brim` | `"auto"`, `"off"`, `"outer"` | `brim_type` `auto_brim`, `no_brim`, `outer_only` |

## Limits

| Limit | Value | Meaning |
|---|---|---|
| `MAX_COPIES` | 25 | Copies on one plate. |
| `MAX_PART_TRIANGLES` | 150,000 | Triangles in one part's STL. |
| `MAX_PART_BYTES` | 7,500,084 | Bytes in one part's STL: a binary STL of `MAX_PART_TRIANGLES` triangles. |
| `MAX_JOB_TRIANGLES` | 300,000 | Triangles summed over every copy. |
| `MIN_PART_EXTENT_MM` | 0.1 | A part must be more than this in every direction. |
| `MARGIN_MM` | 3 | Every footprint stays this far inside the printable area. |
| `SPACING_MM` | 5 | The least distance between two copies' footprints. |
| `PLATE_SLICE_TIMEOUT_S` | 240 | Seconds Orca may take to slice the plate. |

No copy may be taller than the printer's printable height.

## Checks

The slice service checks a plate job in this order and refuses it at the first failure,
before anything reaches Orca, with the [error report](error-report.md) whose code is shown:

1. every part and copy has its fields as above (`slice.bad_plate_job`);
2. at most `MAX_COPIES` copies (`slice.too_many_copies`);
3. every copy's `ref` names a part whose STL file exists (`slice.part_missing`), and that
   file can be opened and is a binary STL with finite coordinates (`slice.part_unreadable`), within
   `MAX_PART_BYTES` and `MAX_PART_TRIANGLES` (`slice.part_too_detailed`) and over
   `MIN_PART_EXTENT_MM` (`slice.part_too_small`);
4. at most `MAX_JOB_TRIANGLES` (`slice.job_too_detailed`);
5. the profiles (`slice.unknown_printer`, `slice.profiles_not_offered`) and the overrides
   (`slice.bad_overrides`);
6. the placement: every footprint inside the margin (`slice.placement_off_plate`), no copy
   too tall (`slice.placement_too_tall`), no two footprints closer than `SPACING_MM`
   (`slice.placement_too_close`).

Orca may still refuse a plate that passes these checks; the slice service's guide,
[slice/README.md](../slice/README.md), lists every code.

## Example

See [examples/plate-job.json](examples/plate-job.json), which places two copies of
[examples/parts/bracket.stl](examples/parts/bracket.stl) and one of
[examples/parts/spacer.stl](examples/parts/spacer.stl).
