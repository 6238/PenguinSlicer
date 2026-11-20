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

A field not listed here, in the plate job, a part or a copy, refuses the plate job
(`slice.bad_plate_job`), so a misspelled `overrides` is never silently ignored. A
`printer`, `filament` or `process` name over 200 characters (`MAX_PROFILE_NAME_CHARS`)
refuses it too: no profile name is that long.

### Part

The key of a part is 1 to 64 letters, digits, `-` or `_`.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `name` | string | yes | The part's name, not empty, of at most 200 characters (`MAX_PART_NAME_CHARS`; a longer one refuses the plate job, `slice.bad_plate_job`). It names the part's copies (see Copy) and the sliced file. |
| `stl` | string | yes | The part's binary STL file, in millimetres: an absolute path, or one relative to the plate job file, of at most 1,024 characters, with no NUL character and no piece between slashes over 255 bytes. Sent to the HTTP face, it is the name of a file sent with the plate job, and nothing outside those files is read. |

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
| `DEFAULT_MAX_PEAK_MB` | 900 | The memory Orca may use while it slices the plate, unless the slice service's setting says otherwise (see Memory). |
| `MIN_PART_EXTENT_MM` | 0.1 | A part must be more than this in every direction. |
| `MARGIN_MM` | 3 | Every footprint stays this far inside the printable area. |
| `SPACING_MM` | 5 | The least distance between two copies' footprints. |
| `PLATE_SLICE_TIMEOUT_S` | 240 | Seconds Orca may take to slice the plate. |

No copy may be taller than the printer's printable height. There is no cap on the
triangles of a whole plate: triangles cost Orca time, not memory.

### Memory

No plate job is refused for memory before it is sliced. While Orca slices, the slice
service samples the memory of Orca and every process it started, with the kernel's
high-water mark of each; when the peak passes the memory ceiling (the slice service's
setting `PENGUIN_SLICE_MAX_PEAK_MB`, `DEFAULT_MAX_PEAK_MB` when it is not set) it stops
Orca and the plate job fails with `slice.out_of_memory`, the measured peak in the error
report's `detail`. The ceiling protects the server from a slice that keeps growing; it is
not a promise that no delivered slice ever touched it: a slice Orca finishes, with a
valid sliced file, before the next sample has stopped it is delivered even when its peak
passed the ceiling, and the server's log line for it says so. The same code is
reported when the kernel's out-of-memory killer stopped Orca (its count of such kills
rose) or Orca said an allocation failed; any other kill is `slice.orca_killed`.

The slice service also estimates the peak, in MB, as

    (MEMORY_BASE_MB + MEMORY_PER_COPY_MB x copies + MEMORY_PER_CM3_MB x volume in cm3)
      x MEMORY_SUPPORTS_FACTOR when supports are on

with `MEMORY_BASE_MB` = 170, `MEMORY_PER_COPY_MB` = 3, `MEMORY_PER_CM3_MB` = 0.985 and
`MEMORY_SUPPORTS_FACTOR` = 1.4, a part's volume being its mesh's when the mesh is
watertight, else its bounding box's, summed over the copies; supports are on when the
`supports` override says so, else when the process profile's `enable_support` is 1. The
estimate is rough (wrong both ways by up to four times on plates outside those it was
fitted to), so it only goes into the slice service's log; it refuses nothing.

## Checks

The slice service checks a plate job in this order and refuses it at the first failure,
before anything reaches Orca, with the [error report](error-report.md) whose code is shown:

1. the plate job, every part and every copy has its fields as above and no other
   (`slice.bad_plate_job`);
2. at most `MAX_COPIES` copies (`slice.too_many_copies`);
3. the profiles (`slice.unknown_printer`, `slice.profiles_not_offered`) and the overrides
   (`slice.bad_overrides`);
4. every copy's `ref` names a part whose STL file exists (`slice.part_missing`), and that
   file can be opened, is an STL, not empty, not cut off and with finite coordinates
   (`slice.part_unreadable`), binary (`slice.part_not_binary`), within `MAX_PART_BYTES`
   and `MAX_PART_TRIANGLES` (`slice.part_too_detailed`), over `MIN_PART_EXTENT_MM` in
   every direction (`slice.part_too_small`), a surface that encloses something
   (`slice.part_no_volume`), and able to stand on the chosen printer's plate in some
   orientation (`slice.part_too_large`);
5. the placement: every footprint inside the margin (`slice.placement_off_plate`), no copy
   too tall (`slice.placement_too_tall`), no two footprints closer than `SPACING_MM`
   (`slice.placement_too_close`).

A part that passes but has holes in its surface (or faces laid on top of each other), a surface facing inwards, or a size that
suggests an inch file read as millimetres is sliced, and carries a warning in the sliced
file's summary (`part_warnings`, see [sliced-file.md](sliced-file.md)).

Orca may still refuse a plate that passes these checks; the slice service's guide,
[slice/README.md](../slice/README.md), lists every code.

## Example

See [examples/plate-job.json](examples/plate-job.json), which places two copies of
[examples/parts/bracket.stl](examples/parts/bracket.stl) and one of
[examples/parts/spacer.stl](examples/parts/spacer.stl).
