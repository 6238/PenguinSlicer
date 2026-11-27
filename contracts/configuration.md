# Configuration

A group's **configuration** is the settings shared by everyone in one group, the users who
share one configuration and one printer (one Onshape company or classroom, or a user alone
who belongs to none). It is one JSON document for each group. The
[front server](../front/README.md#the-configuration) keeps it in the state bucket and gives
it to the [wizard](../wizard/README.md#the-current-group), always for the current group;
the wizard reads from it the filaments and profiles of the Settings step, the units in
which uploaded files are read, and the printer whose plate the Layout step draws.

The document holds no secret: no token, key or pairing code. Which daemon is the group's
is the paired-printer record's business, written only by pairing
([Pairing in phase 5](../delivery/README.md#pairing-in-phase-5)); the configuration names
only the Orca profile to slice for. The settings a user can change in advanced mode, and
the names of the profiles the slice service knows, come from the slice service in the
[table of settings](settings-table.md), not from the configuration.

## Fields

| Field | Type | Required | Meaning |
|---|---|---|---|
| `format` | integer | yes | The number of the document's format. This file describes format `1`. |
| `printer` | string | yes | The Orca printer profile the group slices for, by Orca's own name, from the profile catalog (for example `Bambu Lab H2S 0.6 nozzle`). The plate's size and height, for the Layout step and for the placement check, come from this profile's printable area and printable height, which the [table of settings](settings-table.md#printer) gives. |
| `upload_units` | string | yes | How a part uploaded from a file is read, since an STL file carries no units: `"in"` for inches, `"mm"` for millimetres. The wizard's switch beside the upload area starts at this value. |
| `filaments` | array | yes | The group's filaments, 1 to 20 (see Filament), in the order the Filament menu offers them. The first is the one a new plate starts with. |
| `note` | string | no | Free text for whoever writes the document by hand, at most 2,000 characters. Nothing reads it. |

### Filament

| Field | Type | Required | Meaning |
|---|---|---|---|
| `name` | string | yes | The group's name for the filament, as the Filament menu and the plate summary show it ("PETG", "Red PLA"). 1 to 40 characters, unique among the document's filaments. |
| `colour` | string | yes | The colour shown beside the filament's name where the user chooses a filament, so that two filaments of one material can be told apart: `#` and six hexadecimal digits (`#1f6fd1`). It is never used in the layer preview, which draws every plate in four fixed colours, one for each group of line types ([The result](../wizard/README.md#the-result)). |
| `profiles` | array | yes | The profiles the wizard offers for this filament, 1 to 20 (see Profile), in the order the Profile menu offers them. Each filament has its own list. The first is the one picked when the user picks this filament. |
| `note` | string | no | As for the document. |

### Profile

A **profile** is what a user picks on the Settings step: a name of the group's own, with
the three Orca profiles it stands for and any settings that replace the process profile's
values.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `name` | string | yes | The group's name for the profile, as the Profile menu shows it ("Structural", "Draft"). 1 to 40 characters, unique among the filament's profiles. |
| `purpose` | string | yes | What the profile is for, in a few words, shown as the option's tooltip ("strong brackets and plates"). 1 to 120 characters. |
| `printer` | string | yes | The Orca printer profile's name. It must be the document's `printer`. |
| `filament` | string | yes | The Orca filament profile's name, from the profile catalog, fitting `printer`. |
| `process` | string | yes | The Orca process profile's name, from the profile catalog, fitting `printer`. |
| `overrides` | object | no | Settings that replace values of the process profile, each under Orca's own name for the setting, with its value written as Orca writes it, as a string (`{"wall_loops": "4", "sparse_infill_density": "40%"}`). The same rules hold as for a user's changes in [the plate configuration](plate-configuration.md#settings-in-phase-2): only settings the [table of settings](settings-table.md) holds, each value within what the table allows. Left out: none. |
| `note` | string | no | As for the document. |

The three Orca names and the overrides are exactly what goes into a plate configuration's
`printer`, `filament`, `process` and `overrides` when the user slices with this profile and
has changed nothing ([From a profile to a plate configuration](plate-configuration.md#from-a-profile-to-a-plate-configuration)).
In advanced mode the profile's value of a setting is its override when it has one, and
otherwise the process profile's own value from the table of settings; a user's change is a
departure from that value.

Names in the document are compared exactly, case and spaces included. Because filament
names are unique, and profile names unique within a filament, the wizard keeps the user's
choice in the browser's storage by those names; after the reload glyph, a choice whose
name is gone from the document falls back to the first filament or the first profile.

## When a document is invalid

The front server checks a group's document each time it reads it. A document is invalid
when any of these holds:

1. it is larger than 256 KB (*proposed*; the default is under 2 KB), is not JSON, or is
   not a JSON object;
2. `format` is missing, or is a number this front server does not know;
3. a field is missing that the tables above require, or a field appears that they do not
   list (a misspelled field is never silently ignored), in the document, a filament or a
   profile;
4. a value has the wrong type, or breaks its row's rule: a name empty or too long, two
   filaments of one name, two profiles of one filament with one name, a `colour` not of
   the form `#` and six hexadecimal digits, `upload_units` other than `"in"` or `"mm"`,
   no filament, a filament with no profile, more than 20 of either;
5. a profile's `printer` is not the document's `printer`;
6. an override's value is not a string, or an override's name is not a string of 1 to 100
   characters.

On an invalid document the front server serves the built-in default in its place, leaves
the saved document untouched, and writes an error to the log naming the group and the
first rule broken, with the path of the field (`filaments[1].profiles[0].purpose`). The
wizard is never given an invalid document and has no screen for one; its header names
the default, which is how the person who wrote the document sees that it was not taken
([Reading it and writing it](../front/README.md#reading-it-and-writing-it)).

What the front server does not check: that each Orca name is in the profile catalog, and
that each override is in the table of settings with a value it allows. Those are the slice
service's checks, made when a plate configuration arrives; a document that breaks them is
served, and a slice made with the profile concerned is refused with the slice service's
sentence asking the user to choose from the lists. Who checks a configuration against the
profile catalog's names is open
([Who notices a configuration that names a profile the catalog has lost](../slice/README.md#who-notices-a-configuration-that-names-a-profile-the-catalog-has-lost));
until the first upgrade of Orca the catalog does not change.

## How it is kept

- **In the state bucket, under the group's id.** The document does not name its group, so
  a document can be placed for any group as it is.
- **Read whole and written whole.** A write is conditional: it succeeds only if the
  document has not changed since the version the edit started from, and the second of two
  edits at once is told that someone else changed the configuration and to reload; nothing
  is merged. Every edit writes a log line with the user's name and what changed.
- **A format number.** Like every record kept in the state bucket, the document carries
  the number of its format ([the contracts](README.md)). A front server reads every format
  up to its own. A change to the format that a front server of the previous version could
  not read takes a new number.
- **A fixed set, until the edit screens exist.** Until the configuration's edit screens
  exist, every group gets the built-in default, unless the owner writes a document by
  hand for that group and places it in the state bucket through Cloudflare's console,
  following the annotated example below
  ([The fixed set, until the edit screens exist](../front/README.md#the-fixed-set-until-the-edit-screens-exist)).

## The built-in default

A group with no document, or with an invalid one, gets the built-in default:
[examples/configuration-default.json](examples/configuration-default.json). It is the
front server's own copy, and the front server's tests check that the copy it serves is
this file. It names the Bambu Lab H2S with the 0.6 mm High Flow nozzle, reads uploaded
files in inches, and offers two filaments:

| Filament | Profiles, by the group's names | Orca's filament and process profiles |
|---|---|---|
| PETG | Standard, Structural, Draft, Fine | `Generic PETG @BBL H2S`; `0.24mm Balanced Quality @BBL H2S 0.6 nozzle` (Standard; Structural, with four walls and 40% infill), `0.30mm Standard @BBL H2S 0.6 nozzle` (Draft), `0.18mm Balanced Quality @BBL H2S 0.6 nozzle` (Fine) |
| PLA | Standard | `Generic PLA @BBL H2S`; `0.24mm Balanced Quality @BBL H2S 0.6 nozzle` |

Every name in it is in the profile catalog of the pinned Orca and fits the printer. Its
first filament and first profile are the slice service's default set
([Profiles](plate-configuration.md#profiles)), so a plate sliced with the default and no
change slices exactly as a plate configuration that names no profile. The front server's
answer names the default as such ("PenguinSlicer default"), and the wizard's header shows
that name.

## An annotated example, for writing one by hand

[examples/configuration-hand-written.json](examples/configuration-hand-written.json) is a
complete document of the kind the owner places by hand for a group. JSON allows no
comments, so the explanations are here, and the `note` fields are where a writer may leave
their own.

```json
{
  "format": 1,
  "note": "Written by hand for 6238 (Popcorn Penguins), Fri 2026-11-27.",
  "printer": "Bambu Lab H2S 0.6 nozzle",
  "upload_units": "in",
  "filaments": [
    {
      "name": "Black PETG",
      "colour": "#202020",
      "profiles": [
        {
          "name": "Structural",
          "purpose": "strong brackets and plates",
          "printer": "Bambu Lab H2S 0.6 nozzle",
          "filament": "Generic PETG @BBL H2S",
          "process": "0.24mm Balanced Quality @BBL H2S 0.6 nozzle",
          "overrides": {"wall_loops": "4", "sparse_infill_density": "40%", "sparse_infill_pattern": "gyroid"}
        },
        {
          "name": "Draft",
          "purpose": "fit checks and test prints",
          "printer": "Bambu Lab H2S 0.6 nozzle",
          "filament": "Generic PETG @BBL H2S",
          "process": "0.30mm Standard @BBL H2S 0.6 nozzle"
        }
      ]
    },
    {
      "name": "Orange PETG",
      "colour": "#e8742a",
      "note": "Same material as Black PETG; the colour tells them apart in the menu.",
      "profiles": [
        {
          "name": "Structural",
          "purpose": "strong brackets and plates",
          "printer": "Bambu Lab H2S 0.6 nozzle",
          "filament": "Generic PETG @BBL H2S",
          "process": "0.24mm Balanced Quality @BBL H2S 0.6 nozzle",
          "overrides": {"wall_loops": "4", "sparse_infill_density": "40%", "sparse_infill_pattern": "gyroid"}
        }
      ]
    },
    {
      "name": "PETG-CF",
      "colour": "#5a5a5a",
      "profiles": [
        {
          "name": "Stiff bracket",
          "purpose": "stiff brackets and arms",
          "printer": "Bambu Lab H2S 0.6 nozzle",
          "filament": "Generic PETG-CF @BBL H2S",
          "process": "0.24mm Balanced Quality @BBL H2S 0.6 nozzle",
          "overrides": {"wall_loops": "4", "sparse_infill_density": "35%"}
        }
      ]
    }
  ]
}
```

Field by field:

- `format`: always `1` for a document written to this file.
- `note`: optional, anywhere a `note` is listed; say who wrote the document, for which
  group and when. Leave it out if there is nothing to say.
- `printer`: copy the name exactly from the printers of the profile catalog
  ([slice/src/penguin_slice/profiles/catalog/index.json](../slice/src/penguin_slice/profiles/catalog/index.json),
  or the [table of settings](settings-table.md#the-profile-catalogs-names)). A wrong printer
  is not caught: the group then sees a plate of that printer's size.
- `upload_units`: `"in"` or `"mm"`, how the group's STL files are usually written. A user
  can still switch on the Parts step.
- `filaments`: one entry for each spool the group wants to choose between. Two entries may
  name the same Orca filament profile, as Black PETG and Orange PETG do; only `name` and
  `colour` tell them apart.
- `colour`: `#` and six hexadecimal digits, roughly the spool's colour.
- `profiles`: the first is picked when the filament is picked. `name` and `purpose` are
  what users read; `printer` repeats the document's `printer`; `filament` and `process`
  are copied exactly from the catalog's filaments and processes, each listed there as
  fitting the printer.
- `overrides`: optional. Each key is Orca's own name for a process setting, as the table
  of settings lists it, and each value is a string written as Orca writes it: whole
  numbers as `"4"`, percentages with the sign (`"40%"`), choices by Orca's value
  (`"gyroid"`), on and off as `"1"` and `"0"`. A setting of the filament or the printer
  profile cannot be replaced; a group that needs another temperature needs another Orca
  filament profile.

A mistake of form (a missing comma, a misspelled field, a colour without its `#`) makes the
document invalid: the group gets the default, the header says so, and the log names the
mistake. A mistake of content that the front server cannot see (a profile name the catalog
does not hold, a setting the slice service does not accept) is met when the group slices
with that profile, as the slice service's refusal.
