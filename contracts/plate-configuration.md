# Plate configuration

What the slice service slices: the parts, where each instance of a part sits on the plate
and how it is turned, and the printer, filament and process profiles with the settings
that replace the process profile's values. It is a description, not work: one plate
configuration is one plate and gives one [sliced file](sliced-file.md). Slicing it is a
slice job of the slice service. An instance is one placement of a part on the plate; a
part printed once has one instance.

A plate configuration is a JSON object, sent to the slice service's HTTP interface
([The HTTP interface](../slice/README-details.md#the-http-interface) in the slice service's
details file, as built; from phase 2 [its contract](slice-http-interface.md#post-slices--submit-a-plate-configuration)).
The wizard makes it, on the Preview step, and the front server passes it
on with the user key of the signed-in user.

This file holds two things, kept apart. [To be built](#to-be-built) is the design built in
phase 2: parts named by hash with their units, no files sent with the plate configuration,
the plate's id and the submission's value, and every setting that is a parameter. Every
section after it, from [Fields](#fields) to [Example](#example), is true of the code as
built today, in which a plate configuration arrives with the STL files it names; where
phase 2 changes one of those sections, the section says so in its first line, and the
design under To be built wins.

## To be built

*To be built in phase 2.*

What changes, in short:

- **A part is named by the SHA-256 hash of its bytes and its units label,** and no file is
  sent with the plate configuration. Each part is uploaded once, by itself, when the user
  adds it; the slice service checks it then and keeps it in its part store under the user
  key, the hash and the units. Slicing again uploads nothing.
- **The page makes an id for each plate and a value for each submission,** and the plate
  configuration carries both. A later slice of the same plate replaces that plate's earlier
  unfinished slice job; a repeat of one submission is answered with the first attempt's
  slice job.
- **Every setting the table of settings accepts** may replace a value of the process
  profile, under Orca's own name; the four overrides with their listed values go.
- **An error report lists the parts missing from the part store,** and the wizard uploads
  those parts again and submits again.
- **An instance may lie any way,** not only with one of the part's six axes up: it may carry a
  general rotation in place of an axis, so that a part laid on any face of its convex hull
  can be sliced.
- **One shared set of plates** keeps the wizard's placement check and the slice service's in
  agreement.

### Fields in phase 2

| Field | Type | Required | Meaning |
|---|---|---|---|
| `plate_id` | string | yes | The id the page made for this plate (see The plate and the submission). |
| `submission_id` | string | yes | The value the page made for this submission (see The plate and the submission). |
| `parts` | object | yes | The parts, each under a key of its own (see A part in phase 2). Only parts an instance names are read. |
| `instances` | array | yes | The instances on the plate (see [An instance in phase 2](#an-instance-in-phase-2)): at least one and at most `MAX_INSTANCES`, using at most `MAX_PARTS` different parts. |
| `printer` | string | no | The printer profile's name, from the profile catalog. Left out: the default set (see [Profiles](#profiles)). |
| `filament` | string | with `printer` | The filament profile's name, from the profile catalog, fitting the printer. |
| `process` | string | with `printer` | The process profile's name, from the profile catalog, fitting the printer. |
| `overrides` | object | no | Settings that replace values of the process profile, under Orca's own names (see Settings in phase 2). Left out: none. |
| `local_time` | string | no | As built: the caller's local time as `YYYYMMDD-HHMM`, used in the sliced file's name. |

A field not listed, in the plate configuration, a part or an instance, refuses the plate
configuration (`slice.bad_plate_configuration`), as built. The whole plate configuration
is at most 1 MB (see Limits in phase 2).

### A part in phase 2

The key of a part is, as built, 1 to 64 letters, digits, `-` or `_`; the page chooses it
and it means nothing beyond the plate configuration.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `name` | string | yes | As built: the part's name, not empty, at most 200 characters (`MAX_PART_NAME_CHARS`). It names the part's instances and the sliced file. |
| `sha256` | string | yes | The SHA-256 hash of the part's bytes, as 64 lowercase hexadecimal characters: the hash the slice service answered when the part was uploaded. |
| `units` | string | yes | The part's units label: `"mm"` for millimetres, `"in"` for inches. With `sha256` it names one entry of the part store: the same bytes under the other units are another part. |

A part is found in the part store under the user key of the request, its `sha256` and
its `units` together, and nowhere else: a part another user uploaded is never found, and
nobody can learn whether another user uploaded a given file. A part is not checked again
when a plate configuration names it, except that it must fit the plate's own printer in
some orientation (`slice.part_too_large`), since on arrival it was tested against the
largest printer in the profile catalog.

**Units.** The part's STL is in its units, and the slice service alone applies the scale:
a part in inches is multiplied by 25.4 about the STL's own origin, before anything else,
so that every figure after that is in millimetres. The orientation, footprint, angle and
position of an instance are then exactly as in [Coordinates](#coordinates), and an
instance's `x` and `y` stay in millimetres on the plate whatever the part's units. A part
without a units label, or with any value other than `"mm"` and `"in"`, refuses the plate
configuration (`slice.bad_plate_configuration`); the slice service never guesses units.

### An instance in phase 2

An instance has the fields of [Instance](#instance), as built, except that its turn out of the
part's own coordinates is given in exactly one of two ways:

| Field | Type | Required | Meaning |
|---|---|---|---|
| `ref` | string | yes | As built: the key of the part this is an instance of. |
| `orientation` | string | one of the two | As built: which axis of the part points up, one of the six of [Coordinates](#coordinates). |
| `rotation` | array of 4 numbers | one of the two | A general turn, for a part laid on a face of its convex hull that is not a side of its bounding box: a unit quaternion `[w, x, y, z]`, applied to the part in place of the matrix `M` of an orientation. |
| `angle` | integer | yes | As built: whole degrees, 0 to 359, turned counterclockwise about the vertical, applied after the orientation or the rotation. |
| `x` | number | yes | As built: where the centre of the instance's footprint goes on the plate, in millimetres. |
| `y` | number | yes | The same, along the plate's other axis. |

An instance with both `orientation` and `rotation`, or with neither, refuses the plate
configuration (`slice.bad_plate_configuration`). A `rotation` is refused the same way when it
has other than four elements, an element that is not a finite number, or a length
(`sqrt(w² + x² + y² + z²)`) that differs from 1 by more than 1e-6; the slice service divides
it by its length before use, and `q` and `-q` are the same turn. The page sends `orientation`
whenever the turn is one of the six, and `rotation` otherwise.

The turn of a `rotation` is the matrix of the quaternion, row-major:

    M = ((1 - 2(y² + z²),  2(xy - wz),       2(xz + wy)),
         (2(xy + wz),      1 - 2(x² + z²),   2(yz - wx)),
         (2(xz - wy),      2(yz + wx),       1 - 2(x² + y²)))

applied to each vertex `v` of the part, after its units' scale, as `v' = M v`. Steps 2 and 3
of [Coordinates](#coordinates) then hold unchanged for that `M`: the footprint is the convex
hull of the turned part's vertices seen from above, its centre the centre of the turned
part's bounding box in x and y, the instance turns by `angle` about the vertical line through
that centre, the centre goes to (`x`, `y`) and the instance's lowest point to z = 0. So the one
transform `p_plate = Rz(angle) M p_part + t` holds for both forms. The slice service writes the
same transform into the plate it gives Orca, and its placement check, the wizard's and the
shared plates below use it.

For example, a part laid on a face whose outward normal in the part's coordinates is the unit
vector `n` takes the rotation that turns `n` onto `(0, 0, -1)`, so that the face lies on the
plate.

### The plate and the submission

**The plate's id.** `plate_id` is 1 to 64 letters, digits, `-` or `_`. The page makes it
when a plate begins (a new tab with an empty plate, New plate, a change of group), as a
random UUID, and keeps it with the plate in the browser's storage, through a refresh and
for as long as the plate lives. Every plate configuration the page submits for that plate
carries it. The slice service compares plate ids and never interprets them, and only
within one user key.

When a plate configuration arrives while an earlier slice job of the same user key and
the same `plate_id` is still waiting or running, the slice service ends the earlier one
early: its last [progress report](progress-report.md) has the state `cancelled` and the
reason `replaced`. The earlier slice job gives up its place before the new one is
counted, so a user who slices a changed plate while every place is taken is not refused on
account of their own earlier slice. A slice job is never ended early on account of
another plate's, or of another user key's.

**The submission's value.** `submission_id` is 1 to 64 letters, digits, `-` or `_`. The
page makes a new one, as a random UUID, each time it decides to slice: entering the
Preview step with a plate that is not yet sliced as it now stands, Slice again, and
submitting again by itself after a slice job ended because the slice service was asked to
stop or after the slice service restarted. It sends the same value again whenever it
repeats a submission whose answer did not arrive, and when it submits again after
uploading parts the slice service said were missing.

The slice service remembers each submission's value beside the slice job it started, for
as long as it remembers the slice job (two hours after the slice job ends). A plate
configuration whose user key and `submission_id` are those of a slice job it remembers is
answered with that slice job, as if it had just been accepted, and starts nothing: it does
not replace that slice job, takes no place and is checked no further. The page never uses
one `submission_id` for two different plate configurations. A submission that was refused
(a part missing, no room to wait, the slice service stopping) started no slice job, so its
value is not remembered and may be sent again.

### Settings in phase 2

`overrides` holds the settings that replace values of the process profile, each under
Orca's own name for the setting, with its value as a string written as Orca writes it in a
profile:

```json
{"sparse_infill_density": "20%", "wall_loops": "3", "enable_support": "1", "support_type": "tree(auto)", "brim_type": "auto_brim"}
```

The settings that may appear are exactly those of the [table of settings](settings-table.md)
the slice service supplies, and each value is checked against its entry there before Orca
runs:

- a **choice** must be one of the entry's values (an on-and-off setting is `"0"` or `"1"`);
- a **number** must be of the entry's form (a whole number, a decimal, a percentage written
  with its sign, or either of the last two where the entry allows both) and within the
  entry's least and greatest values, where it has them;
- a **text** must be no longer than the entry's greatest length;
- a setting that Orca keeps as one value for each extruder variant takes one value here,
  and the slice service writes it for every variant.

A setting the table does not hold is refused: a programmatic setting (one that runs a
program, names a file on the server, or holds custom G-code), a setting of the filament or
printer profile, a misspelled name. A refused setting, or a value that does not fit, refuses
the plate configuration with `slice.bad_overrides`, whose sentence and `detail` name the
setting and say why. Only the process profile's values are ever replaced.

**Supports are on** when `overrides` sets `enable_support` to `"1"`, or when it does not set
it and the process profile's own value is `"1"`. That one question decides the spacing
(`SPACING_SUPPORTS_MM`) and the supports factor of the estimates, as built. Other settings
that make an instance need more room (a wide brim, a raft, printing one object at a time)
are not known to the placement check.

The four quick changes of the wizard's Settings step are ordinary settings in this form:
Infill is `sparse_infill_density`, Walls is `wall_loops`, Supports is `enable_support`
(with `support_type` `tree(auto)` when on) and Brim is `brim_type`.

### From a profile to a plate configuration

The wizard makes the plate configuration from the group's [configuration](configuration.md)
and the user's work:

| Field | From |
|---|---|
| `plate_id`, `submission_id` | The page, as above |
| `parts` | The plate's parts in the browser's storage: each part's name, hash and units |
| `instances` | The Layout step |
| `printer`, `filament`, `process` | The chosen profile's `printer`, `filament` and `process` |
| `overrides` | The chosen profile's own `overrides`, then the user's changes on top: a setting the user changed takes the user's value, and a change the user put back to the profile's value is left out |
| `local_time` | The browser's clock |

So the slice service never sees the configuration, and a group's own names for its
filaments and profiles never reach it.

### Parts missing from the part store

When a plate configuration names parts that the part store does not hold under the
request's user key (they were never uploaded, were removed as least recently used, passed
two hours unused, or the slice service has restarted), the slice service refuses it with
one [error report](error-report.md) that lists every missing part, and starts nothing:

| Field of the error report | Value |
|---|---|
| `code` | `slice.part_missing` |
| `where` | `stage` `checking`, and `missing_parts`: one object for each missing part, in the order of the plate configuration's `parts` (see below) |
| `action` | `refresh_parts` |
| `retryable` | `false`: the same plate configuration succeeds only after those parts are uploaded |
| `detail` | Each missing part's hash and units, for the log |

Each object of `missing_parts` has three fields: `key`, the part's key in the plate
configuration; `sha256`, its hash; and `units`, its units label. The page uploads each of
those parts again from the browser's storage, with its units, and submits the plate
configuration again with the same `submission_id`. The user sees nothing of it; its
`message` and `remedy` exist for the log and for a page that cannot upload the parts
again. See [examples/error-report-parts-missing.json](examples/error-report-parts-missing.json).

An instance whose `ref` names no key of `parts` is a fault of the page, and keeps the
code as built (`slice.part_missing`, with no `missing_parts`).

### Limits in phase 2

The limits of [Limits](#limits) stand, with these changes:

| Limit | Value | Meaning |
|---|---|---|
| `MAX_PLATE_CONFIGURATION_BYTES` | 1,048,576 (1 MB; *proposed*) | The whole plate configuration, all its settings included. It bounds what one submission can make the slice service read. A larger one is refused (`slice.bad_plate_configuration`) before it is read. |
| `MAX_PARTS` | 25, as built | Different parts the instances on one plate use. It no longer bounds an upload, since no file is sent with a plate configuration; it bounds the parts one plate makes the slice service hold. |
| `MAX_PART_BYTES` and `MAX_PART_TRIANGLES` | As built | Now applied to each part when it is uploaded, by itself, and not to the plate configuration. |

From phase 3, `PLATE_SLICE_TIMEOUT_S` becomes a setting of the slice service rather than a
figure fixed in the code.

### Checks in phase 2

The order of [Checks](#checks) stands, with step 4 changed: every instance's `ref` names a
key of `parts`, and every part is in the part store under the user key, its `sha256` and
its `units` (`slice.part_missing`, listing every missing part at once, as above); each part
then fits the plate's printer in some orientation (`slice.part_too_large`). The other
checks on a part (whether it can be read, is binary, is too detailed, too small or
encloses nothing) have run when it was uploaded, judged on its true size in its units, and
are not repeated. Step 1 also refuses a plate configuration without `plate_id`,
`submission_id`, or a part's `sha256` or `units`, or with one that breaks its form, and an
instance with both or neither of `orientation` and `rotation`, or with a `rotation` that is
not a unit quaternion ([An instance in phase 2](#an-instance-in-phase-2))
(`slice.bad_plate_configuration`); step 5 places each instance by its orientation or its
rotation; step 3 checks the settings as above
(`slice.bad_overrides`). A repeat of a remembered submission is answered before step 1.

### Old and new versions together

From phase 3 the front server and the slice service are deployed apart, and each one's
previous version must work against the other's new one. So a field added to the plate
configuration after phase 2 is optional, with a meaning when it is left out that the
previous front server's plate configurations keep; and a field is never removed or given
a new meaning while a previous front server may still send it.

### Example in phase 2

See [examples/plate-configuration-phase-2.json](examples/plate-configuration-phase-2.json),
the plate of [Example](#example) as phase 2 sends it: the same parts, named by the hashes
of [examples/parts/bracket.stl](examples/parts/bracket.stl) and
[examples/parts/spacer.stl](examples/parts/spacer.stl) in millimetres, the same profiles,
and the four settings of the built example under Orca's own names, with a fourth instance: a
bracket laid on the face of its convex hull across the L's open corner, by a `rotation`.

### Shared plates for the placement checks

The wizard's placement check and the slice service's are kept in agreement by one set of
plates, run by both components' tests
([Shared plates for the two placement checks](../slice/README.md#shared-plates-for-the-two-placement-checks)).
A change to a rule or a figure changes the set and both components' tests in one commit.

**Where.** `contracts/examples/placement/`, one JSON file for each plate, named for what it
tries (`margin-pass.json`, `margin-fail.json` and so on). The parts are those of
`contracts/examples/parts/`, named by the hashes of their files: the bracket and the spacer,
and two posts written for the set, `post-340.stl` and `post-341.stl`, boxes of 10 by 10 by
340 mm and 10 by 10 by 341 mm (12 triangles each).

**A plate's file:**

```json
{
  "description": "Two brackets 4.99 mm apart with supports off",
  "plate_configuration": { "...": "a phase 2 plate configuration, every field" },
  "expected": {"code": "slice.placement_too_close", "instance": "Bracket #1", "other_instance": "Bracket #2"}
}
```

`plate_configuration` is a whole phase 2 plate configuration over the default set of
profiles (a Bambu Lab H2S, x from 0 to 340 mm, y from 0 to 320 mm, 340 mm tall), so that
the slice service can take it as it is once its parts are uploaded. `expected` is either
`{"accepted": true}` or the error report's `code` with the `instance` and, for a rule about
two instances, the `other_instance` its `where` names (for the first problem, in the order of
the checks).

**The plates.** For each rule one plate just passes and one just fails, each 0.01 mm from the
rule's figure:

| Rule | Passes | Fails |
|---|---|---|
| The 3 mm margin | A bracket whose footprint is 3.01 mm inside the printable area's edge | The same at 2.99 mm |
| The printable height | `post-340.stl` standing up | `post-341.stl` standing up; the same post laid down passes, which a third plate shows |
| 5 mm apart, supports off | Two brackets 5.01 mm apart | 4.99 mm apart |
| 12 mm apart, supports on | Two brackets 12.01 mm apart, `enable_support` `"1"` | 11.99 mm apart |
| A turned instance | A bracket at `angle` 37, 5.01 mm from another at the closest point of their outlines | The same at 4.99 mm |
| A rotation | The bracket laid on its hull face by `rotation`, 5.01 mm from a spacer | The same at 4.99 mm |

**Agreement.** On every plate of the set both checks give exactly the expected answer. The
slice service decides each rule with a tolerance of 1e-6 mm; the set keeps every distance
0.01 mm from its figure, so a check that computes in single precision, as a browser's
drawing may, still agrees. Closer to a figure than 0.01 mm the two checks may differ, and the
slice service's answer is the one that holds.

**Who writes it.** The slice service's builder writes the set and its parts first of all in
phase 2, before the rest of its work, since the wizard's builder runs it from the start
([the slice service's details](../slice/README-details.md#phase-2-one-machine)).

## Fields

*Built today. Phase 2 adds `plate_id` and `submission_id` and gives `overrides` Orca's own
names: see [Fields in phase 2](#fields-in-phase-2).*

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

*Built today. In phase 2 `stl` gives way to `sha256` and `units`: see
[A part in phase 2](#a-part-in-phase-2).*

The key of a part is 1 to 64 letters, digits, `-` or `_`.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `name` | string | yes | The part's name, not empty, of at most 200 characters (`MAX_PART_NAME_CHARS`; a longer one refuses the plate configuration, `slice.bad_plate_configuration`). It names the part's instances (see Instance) and the sliced file. |
| `stl` | string | yes | The part's binary STL file, in millimetres: the name of a file sent with the plate configuration, of at most 1,024 characters, with no NUL character and no piece between slashes over 255 bytes. Nothing outside the files sent with it is read. All the instances of a part share its one file. |

### Instance

*Built today. Phase 2 lets `rotation` stand in place of `orientation`: see
[An instance in phase 2](#an-instance-in-phase-2).*

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

*Built today. In phase 2 the part's STL is in its units, scaled to millimetres first: see
[A part in phase 2](#a-part-in-phase-2); and step 1 may use a general rotation in place of
the six orientations: see [An instance in phase 2](#an-instance-in-phase-2).*

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
[slice/src/penguin_slice/profiles/catalog/index.json](../slice/src/penguin_slice/profiles/catalog/index.json);
from phase 2 the slice service also supplies those names in the
[table of settings](settings-table.md#the-profile-catalogs-names).

- With `printer`: the printer must be in the catalog, and `filament` and `process` must be
  catalog entries that fit it.
- Without `printer`: the default set, a Bambu Lab H2S with the 0.6 mm High Flow nozzle
  (`Bambu Lab H2S 0.6 nozzle`), `Generic PETG @BBL H2S` and
  `0.24mm Balanced Quality @BBL H2S 0.6 nozzle`. `filament` and `process` may then be left
  out or must name those two.

## Overrides

*Built today. Replaced in phase 2 by every setting of the table of settings, under Orca's
own names: see [Settings in phase 2](#settings-in-phase-2).*

Each override is optional; its value must be one of the listed values, of the listed type.

| Override | Values | Orca setting |
|---|---|---|
| `infill` | 10, 15, 20, 30, 40, 60, 100 | `sparse_infill_density` = `<value>%` |
| `walls` | 2, 3, 4, 6 | `wall_loops` |
| `supports` | `"off"`, `"on"` | `enable_support` 0, or 1 with `support_type` `tree(auto)` |
| `brim` | `"auto"`, `"off"`, `"outer"` | `brim_type` `auto_brim`, `no_brim`, `outer_only` |

## Limits

*Built today. Phase 2 adds a limit on the whole plate configuration and changes what
`MAX_PARTS` bounds: see [Limits in phase 2](#limits-in-phase-2).*

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

*Built today. Phase 2 changes step 4: see [Checks in phase 2](#checks-in-phase-2).*

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

Orca may still refuse a plate that passes these checks; the slice service's details file,
[Error codes](../slice/README-details.md#error-codes), lists every code.

## Example

*Built today. For phase 2 see [Example in phase 2](#example-in-phase-2).*

See [examples/plate-configuration.json](examples/plate-configuration.json), which places
two instances of [examples/parts/bracket.stl](examples/parts/bracket.stl) and one of
[examples/parts/spacer.stl](examples/parts/spacer.stl). Each `stl` is the name the file
is sent under ([Use](../slice/README-details.md#use), in the slice service's details
file, shows the `curl` command).
