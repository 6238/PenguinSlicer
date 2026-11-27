# Plate configuration

What the slice service slices: the parts as STL files, where each instance of a part sits
on the plate and how it is turned, and the printer, filament and process profiles with
their setting overrides. It is a description, not work: one plate configuration is one
plate and gives one [sliced file](sliced-file.md). Slicing it is a slice job of the slice
service. An instance is one placement of a part on the plate; a part printed once has one
instance.

A plate configuration is a JSON object, sent to the slice service's HTTP interface with
the STL files it names ([The HTTP interface](../slice/README-details.md#the-http-interface)
in the slice service's detailed guide).

## To be built

Phase 2 changes how a plate configuration names its parts, gives each part its units and
widens the settings it accepts. Everything else in this file is true of the code as built.

- **A part is named by the SHA-256 hash of its bytes,** where as built its `stl` names a
  file sent with the plate configuration. Each part is uploaded once, by itself, when the user
  adds it, and the slice service keeps it in its part store under the user key and that
  hash; no file is sent with the plate configuration, so slicing again uploads nothing.
- **An error report lists the hashes missing from the part store.** When a plate
  configuration names parts the part store no longer holds, the slice service answers with
  one error report listing every missing hash, and the wizard uploads those parts again
  and submits again.
- **Each part carries its units,** inches or millimetres, as a label beside it. The
  browser reads a part to draw it and lay it out and never changes its bytes; only the
  slice service applies the scale. The units travel with the part when it is uploaded,
  the slice service uses them in its checks on arrival (the size, the fit on the plate,
  the warning that a part may be in inches), and a part in the part store is identified
  by its bytes and its units together, so the same file under different units is a
  different part. Instances' positions on the plate stay in millimetres.
- **Every setting Orca allows that is a parameter with a value** is accepted: a choice
  from a list, a number or a piece of text, each checked against what Orca allows for it.
  All of them are available in the wizard's advanced mode. Settings that are programmatic
  are refused: those that run a program, those that name a file on the server, and custom
  G-code. This replaces the four overrides of [Overrides](#overrides) with their listed
  values; a refused setting gets an error report naming it.

*Proposed* (the design approved by the owner does not fix it; the builder settles it):
a part's `sha256`, the 64 hexadecimal characters of the hash, in place of `stl`; a part's
`units`, `"mm"` or `"in"`; `overrides` keeping its name, its keys becoming Orca's own
setting names, and a refused one keeping the code `slice.bad_overrides`. The routes and
the error reports' codes are proposed in
[the slice service's detailed guide](../slice/README-details.md#to-be-built).

- **What else in this file changes when this is built.** Seven places are true of the
  code as built and become untrue in phase 2: the opening ("with the STL files it names");
  the `stl` row of [Part](#part), which gains the units; "The part" under
  [Coordinates](#coordinates), whose STL is then in the part's units; [Overrides](#overrides);
  the meaning of `MAX_PARTS` in [Limits](#limits) ("It bounds the upload"); check 4 of
  [Checks](#checks), where a part's own checks move to its upload and `slice.part_missing`
  comes to mean a hash missing from the part store; and the [Example](#example). Also, from phase 3, `PLATE_SLICE_TIMEOUT_S` in [Limits](#limits)
  becomes a setting of the slice service rather than a figure fixed in the code.

## Fields

| Field | Type | Required | Meaning |
|---|---|---|---|
| `parts` | object | yes | The parts, each under a key of its own (see Part). Only parts an instance names are read. |
| `instances` | array | yes | The instances on the plate, at least one and at most `MAX_INSTANCES`, using at most `MAX_PARTS` different parts (see Instance). |
| `printer` | string | no | The printer profile's name, from the catalog. Left out: the default set (see Profiles). |
| `filament` | string | with `printer` | The filament profile's name, from the catalog, fitting the printer. |
| `process` | string | with `printer` | The process profile's name, from the catalog, fitting the printer. |
| `overrides` | object | no | Settings that replace the process profile's (see Overrides). |
| `local_time` | string | no | The caller's local time as `YYYYMMDD-HHMM`, used in the sliced file's name. Anything else, or left out: the slice service's UTC time. |

A field not listed here, in the plate configuration, a part or an instance, refuses the
plate configuration (`slice.bad_plate_configuration`), so a misspelled `overrides` is never
silently ignored. A `printer`, `filament` or `process` name over 200 characters
(`MAX_PROFILE_NAME_CHARS`) refuses it too: no profile name is that long.

### Part

The key of a part is 1 to 64 letters, digits, `-` or `_`.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `name` | string | yes | The part's name, not empty, of at most 200 characters (`MAX_PART_NAME_CHARS`; a longer one refuses the plate configuration, `slice.bad_plate_configuration`). It names the part's instances (see Instance) and the sliced file. |
| `stl` | string | yes | The part's binary STL file, in millimetres: the name of a file sent with the plate configuration, of at most 1,024 characters, with no NUL character and no piece between slashes over 255 bytes. Nothing outside the files sent with it is read. All the instances of a part share its one file. |

### Instance

| Field | Type | Required | Meaning |
|---|---|---|---|
| `ref` | string | yes | The key of the part this is an instance of. |
| `orientation` | string | yes | Which axis of the part points up: one of `+z`, `-z`, `+x`, `-x`, `+y`, `-y` (see Coordinates). |
| `angle` | integer | yes | Whole degrees, 0 to 359, that the instance turns counterclockwise seen from above. |
| `x` | number | yes | Where the centre of the instance's footprint goes on the plate, in millimetres. |
| `y` | number | yes | The same, along the plate's other axis. |

Each instance is named `<part name> #<n>`, the part name reduced to letters, digits, `-`
and `_` (every other character becomes `_`, at most 40 characters, `part` when nothing is
left), and `n` counting instances of the same reduced name from 1 in the order of
`instances`. Two different parts both named `Bracket` give `Bracket #1` and `Bracket #2`.
The printer shows these names in its list of objects to skip.

## Coordinates

**The part.** The STL's own coordinates, in millimetres, with any origin. The slice service
never moves the part's mesh itself; it only places instances of it.

**The plate.** Millimetres, z up, x and y as in the printer profile's `printable_area`
(on every printer in the catalog today, x from 0 to 340 and y from 0 to 320). The
printable height is the profile's
`printable_height` (340 mm today).

**An instance** is placed in three steps:

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
3. **Angle and position.** The instance turns by `angle` about the vertical line through
   the footprint's centre, the centre goes to (`x`, `y`), and the instance's lowest point
   goes to z = 0.

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
| `MAX_INSTANCES` | 150 | Instances on one plate. |
| `MAX_PARTS` | 25 | Different parts the instances on one plate use. It bounds the upload (`MAX_PARTS` x `MAX_PART_BYTES`); it is not a measured limit. |
| `MAX_PART_TRIANGLES` | 150,000 | Triangles in one part's STL. |
| `MAX_PART_BYTES` | 7,500,084 | Bytes in one part's STL: a binary STL of `MAX_PART_TRIANGLES` triangles. |
| `DEFAULT_MAX_PEAK_MB` | 2,000 | The memory Orca may use while it slices the plate, unless the slice service's setting says otherwise (see Memory). |
| `MIN_PART_EXTENT_MM` | 0.1 | A part must be more than this in every direction. |
| `MARGIN_MM` | 3 | Every footprint stays this far inside the printable area. |
| `SPACING_MM` | 5 | The least distance between two instances' footprints, with supports off. |
| `SPACING_SUPPORTS_MM` | 12 | The least distance between two instances' footprints, with supports on: Orca's supports need more room. A user interface that arranges the plate leaves this distance when supports are on. |
| `PLATE_SLICE_TIMEOUT_S` | 240 | Seconds Orca may take to slice the plate. |

No instance may be taller than the printer's printable height. A user's 10 by 10 grid of
small spacers is 100 instances of one part: well inside every limit.

### Memory

No plate configuration is refused for memory before it is sliced, nor for the triangles of
the whole plate: many instances of a detailed part are left to the memory ceiling below. While Orca slices, the
slice service samples the memory of Orca and every process it started, with the kernel's
high-water mark of each; when the peak passes the memory ceiling (the slice service's
setting `PENGUIN_SLICE_MAX_PEAK_MB`, `DEFAULT_MAX_PEAK_MB` when it is not set) it stops
Orca and the slice job fails with `slice.out_of_memory`, the measured peak in the error
report's `detail`. The ceiling protects the server from a slice that keeps growing; it is
not a promise that no delivered slice ever touched it: a slice Orca finishes, with a
valid sliced file, before the next sample has stopped it is delivered even when its peak
passed the ceiling, and the server's log line for it says so. The same code is
reported when the kernel's out-of-memory killer stopped Orca (its count of such kills
rose) or Orca said an allocation failed; any other kill is `slice.orca_killed`.

The slice service also estimates the peak, in MB, as

    (MEMORY_BASE_MB + MEMORY_PER_INSTANCE_MB x instances + MEMORY_PER_CM3_MB x volume in cm3)
      x MEMORY_SUPPORTS_FACTOR when supports are on

with `MEMORY_BASE_MB` = 170, `MEMORY_PER_INSTANCE_MB` = 3, `MEMORY_PER_CM3_MB` = 0.985 and
`MEMORY_SUPPORTS_FACTOR` = 1.4, a part's volume being its mesh's when the mesh is
watertight, else its bounding box's, summed over the instances; supports are on when the
`supports` override says so, else when the process profile's `enable_support` is 1. The
estimate is rough (wrong both ways by up to four times on plates outside those it was
fitted to), so it only goes into the slice service's log; it refuses nothing.

## Checks

The slice service checks a plate configuration in this order and refuses it at the first
failure, before anything reaches Orca, with the [error report](error-report.md) whose code
is shown:

1. the plate configuration, every part and every instance has its fields as above and no
   other (`slice.bad_plate_configuration`);
2. at most `MAX_INSTANCES` instances (`slice.too_many_instances`), using at most
   `MAX_PARTS` different parts (`slice.too_many_parts`);
3. the profiles (`slice.unknown_printer`, `slice.profiles_not_offered`) and the overrides
   (`slice.bad_overrides`);
4. every instance's `ref` names a part whose STL file exists (`slice.part_missing`), and
   that file can be opened, is an STL, not empty, not cut off and with finite coordinates
   (`slice.part_unreadable`), binary (`slice.part_not_binary`), within `MAX_PART_BYTES`
   and `MAX_PART_TRIANGLES` (`slice.part_too_detailed`), over `MIN_PART_EXTENT_MM` in
   every direction (`slice.part_too_small`), a surface that encloses something
   (`slice.part_no_volume`), and able to stand on the chosen printer's plate in some
   orientation (`slice.part_too_large`);
5. the placement: every footprint inside the margin (`slice.placement_off_plate`), no
   instance too tall (`slice.placement_too_tall`), no two footprints closer than
   `SPACING_MM`, or `SPACING_SUPPORTS_MM` when supports are on (`slice.placement_too_close`,
   whose report names both instances).

A part that passes but has holes in its surface (or faces laid on top of each other), a
surface facing inwards, or a size that suggests an inch file read as millimetres is
sliced, and carries a warning in the sliced file's summary (`part_warnings`, see
[sliced-file.md](sliced-file.md)).

Orca may still refuse a plate that passes these checks; the slice service's detailed guide,
[Error codes](../slice/README-details.md#error-codes), lists every code.

## Example

See [examples/plate-configuration.json](examples/plate-configuration.json), which places
two instances of [examples/parts/bracket.stl](examples/parts/bracket.stl) and one of
[examples/parts/spacer.stl](examples/parts/spacer.stl). Each `stl` is the name the file
is sent under ([Use](../slice/README-details.md#use), in the slice service's detailed
guide, shows the `curl` command).
