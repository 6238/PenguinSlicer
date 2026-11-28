# Table of settings

*Built in phase 2 in the slice service, which supplies it; the front server's passing it on
and the wizard's advanced mode are their builders'.*

The **table of settings** describes every setting a plate configuration may change: each
setting of Orca's that is a parameter with a value, with what Orca allows for it, Orca's own
words for it and the value each process profile gives it. With it come the profile
catalog's names: the printer, filament and process profiles the slice service can slice
with, and each printer's plate. The [slice service](../slice/README.md#accept-settings)
holds the table, checks every plate configuration's settings against it and supplies it;
the [front server](../front/README.md#the-list-of-settings-and-the-profile-catalogs-names)
asks the slice service for it and passes it to the [wizard](../wizard/README.md#advanced-mode)
unchanged, keeping no copy from one start to the next, so that the table always matches the
slice service that is running.

The wizard draws advanced mode from it: the sections, the setting groups, the labels and
explanations, and a control for each setting made from its kind. The changes box, the change
details and the plate summary take the profile's value of a setting from it, and the Layout
step takes the plate's size and height from the printer it names.

## How it is made

- **From Orca's source, never by hand.** Each time an Orca version is integrated, the
  table is generated from that version's source: each setting's name, kind and permitted
  values, and Orca's own label, page, group and explanation for it, in Orca's order. The
  process profiles' values, and the profile catalog's names, come from the profile catalog
  of the same version. Taking a new Orca version therefore needs that version's source as
  well as its release ([Taking a new Orca version](../slice/README.md#taking-a-new-orca-version)).
- **Programmatic settings never appear in it.** A setting that runs a program, one that
  names a file on the server, and custom G-code are classified as programmatic and left
  out. So are the settings of the filament and printer profiles, which a plate configuration
  may not replace, and the process settings Orca does not offer: those it shows on no page
  of its process settings (the profile's own bookkeeping among them), and the one that holds
  a list of values, which no entry's kind can describe. Each process setting of the pinned
  Orca is classified, as a parameter, as programmatic or as not offered, by the person or
  agent doing the work; the programmatic and the not offered are listed in the slice
  service's folder by name, each with its reason. A setting classified nowhere fails the
  check against a new Orca version, so no setting is ever offered without someone having
  looked at it.
- **What the table holds is what the slice service accepts.** A setting is in the table
  exactly when a plate configuration may set it, and a value is accepted exactly when it
  fits the setting's entry ([Settings in phase 2](plate-configuration.md#settings-in-phase-2)).

## Fields

| Field | Type | Required | Meaning |
|---|---|---|---|
| `format` | integer | yes | The number of the table's format. This file describes format `1`. |
| `orca_version` | string | yes | The version of Orca the table was made from, for example `2.4.2`. |
| `settings` | array | yes | One entry for each accepted setting (see Setting), in Orca's order: by page, then by setting group, then as Orca lists them within a group. |
| `process_values` | object | yes | For each process profile of the profile catalog, under its name, an object that gives every setting of `settings` its value in that profile (see Process values). |
| `catalog` | object | yes | The profile catalog's names (see The profile catalog's names). |

### Setting

| Field | Type | Required | Meaning |
|---|---|---|---|
| `name` | string | yes | Orca's own name for the setting, the key a plate configuration's `overrides` uses (`sparse_infill_density`). |
| `kind` | string | yes | `"choice"`, `"number"` or `"text"`. |
| `label` | string | yes | Orca's label for the setting, as Orca shows it ("Sparse infill density"). |
| `section` | string | yes | The page of Orca's process settings it is on ("Strength"), which is advanced mode's section. |
| `group` | string | yes | The setting group it is in on that page ("Sparse infill"). |
| `explanation` | string | yes | Orca's explanation of the setting, its tooltip in Orca, as Orca wrote it. Empty when Orca has none. |
| `unit` | string | no | Orca's word for the unit shown after the value ("mm", "mm/s", "%"). Left out when Orca shows none. |
| `per_variant` | boolean | yes | Whether Orca keeps one value of the setting for each extruder variant (the standard and the High Flow nozzle). A plate configuration gives such a setting one value, which the slice service writes for every variant. At the pinned Orca 2.4.2 it is `false` for every setting: the only process settings Orca keeps for each variant are the profile's own list of variants and its map of them, which are not offered. |
| `choices` | array | with `kind` `"choice"` | The permitted values, in Orca's order, each an object with `value` (the string Orca writes, `"tree(auto)"`) and `label` (Orca's words for it, "Tree (auto)"). An on-and-off setting has the two choices `"0"` and `"1"`, labelled "Off" and "On", since Orca draws it as a box to tick and gives no words. |
| `number_form` | string | with `kind` `"number"` | How the number is written: `"integer"` (`"3"`), `"decimal"` (`"0.24"`), `"percent"` (always with its sign, `"40%"`), or `"decimal_or_percent"` (either; a percentage is of a figure Orca names in the explanation, often the nozzle's width). |
| `min` | number | no | With `kind` `"number"`: the least value Orca allows, when it sets one. For a percentage, in percent. |
| `max` | number | no | With `kind` `"number"`: the greatest value Orca allows, when it sets one. |
| `max_length` | integer | with `kind` `"text"` | The most characters the value may hold: the length of the longest text value of that setting in the profile catalog, and never less than 1. |

A field not listed for an entry's kind is left out of that entry.

### Process values

`process_values` maps each process profile's name to an object that maps each setting's
`name` to its value in that profile, as a string written as Orca writes it, of the form its
entry describes. It is the value Orca slices with when nothing replaces it: the profile's own
value, or Orca's default when the profile holds none; for a setting with `per_variant`, the
value for the extruder variant the profile's printer uses (the High Flow variant for the
0.6 mm nozzle of the default set). A profile may hold a list of values for a setting Orca
keeps once (Bambu Lab's profiles list a speed for each variant); Orca then slices with the
first value of the list, the standard nozzle's, whatever the printer's nozzle, and that
first value is the one given. Every process profile of `catalog.processes` has an entry, and
every entry holds every setting of `settings`.

What the wizard shows as **the profile's value** of a setting (in advanced mode's "Profile
0.24 mm · Reset" and in the change details) is the configuration profile's own override of
that setting when it has one, and otherwise this value of its process profile
([the configuration](configuration.md#profile)).

### The profile catalog's names

`catalog` holds three lists, each in the profile catalog's order:

| Field | Type | Meaning |
|---|---|---|
| `printers` | array | One object for each printer profile (see Printer). |
| `filaments` | array | One object for each filament profile: `name`, its Orca name, and `printers`, the names of the printer profiles it fits. |
| `processes` | array | One object for each process profile: `name` and `printers`, as for a filament. |

#### Printer

| Field | Type | Required | Meaning |
|---|---|---|---|
| `name` | string | yes | The printer profile's Orca name (`Bambu Lab H2S 0.6 nozzle`). |
| `printable_area` | array | yes | The plate's printable area, as the profile gives it: its corners in order, each an array of two numbers, x and y in millimetres (`[[0, 0], [340, 0], [340, 320], [0, 320]]`). |
| `printable_height` | number | yes | The tallest a print may be, in millimetres (`340`). |

The Layout step draws the plate of the printer the configuration names, from these two
figures, and the placement checks of the wizard and of the slice service use the same two.

## Rules

- **One table for one slice service.** The table changes only when the Orca version moves,
  and then the slice service, its checks and its table change together. The front server
  passes on what the slice service that is running supplies.
- **Names are Orca's.** A setting's `name`, a choice's `value` and every profile name are
  Orca's own, compared exactly. A setting's `label`, `section`, `group`, `explanation` and a
  choice's `label` are Orca's words, in English, shown as they are; PenguinSlicer writes none
  of them, except the "Off" and "On" of an on-and-off setting.
- **338 settings.** The pinned Orca 2.4.2 has 355 process settings, of which 338 are
  parameters; the table with every process profile's values is 379 kilobytes, 35 compressed,
  and it is served compressed.
- **A format number.** A change that a wizard of the previous version could not read takes
  a new `format`; a field added with a meaning when it is left out does not.

## Example

See [examples/settings-table.json](examples/settings-table.json). It is shortened and written
by hand to show the shape: nine settings, one of each number form and several choices, with
only some of Orca's infill patterns; the 0.6 mm nozzle's printer and three of its process
profiles, with their values from the profile catalog; and three filaments. The real table
is generated and holds every accepted setting, every choice and every profile of the
catalog, and its words are Orca's own, where the example's labels, explanations and ranges
are only of the kind Orca gives. The example marks `outer_wall_speed` `per_variant` with a
High Flow value of 500 to show how such a setting is written; at the pinned Orca 2.4.2 no
setting is `per_variant` (see `per_variant` above), and the real table gives that profile
120, the value Orca slices with.
