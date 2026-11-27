# Configuration

What the configuration document must hold. **Its fields are not written yet:** their
names, types and an annotated example are written with phase 2's design. Until then this
file collects what is decided about the document.

A group's **configuration** is the settings shared by everyone in one group, the users who
share one configuration and one printer (one Onshape company or classroom, or a user alone
who belongs to none). The [front server](../front/README.md) keeps it and the
[wizard](../wizard/README.md) reads it through the front server.

## What is decided

- **One JSON document for each group,** kept in the state bucket, the object store where
  the front server keeps what must outlast its restart. It is read whole and written whole.
- **The group's filaments.** For each filament, the profiles to slice with, named by Orca's
  own names, with any settings that replace a profile's own. Each filament has its own
  profiles, not one list for all.
- **A colour for each filament,** which the wizard shows where the user chooses a
  filament, so that two filaments of one material (a red PLA and a green PLA) can be told
  apart. It is never used in the layer preview, which draws every plate in four fixed
  colours, one for each set of line types, whatever the filament
  ([the wizard](../wizard/README-details.md#the-configuration)).
- **The group's own name and purpose for each profile,** beside the Orca profile it uses.
  The Settings step offers profiles by the group's names (such as "Structural") and shows
  a profile's purpose as its option's tooltip; Orca's own profile names are not names a
  group would choose, and say nothing of a profile's purpose.
- **The printer's Orca profile,** from which the plate's size and height come (the
  profile's `printable_area` and `printable_height`), for the Layout step and for the plate
  configuration's `printer`. The group's printer is linked to its daemon by the
  paired-printer record, written only by pairing, not by the configuration; the
  configuration names only the profile to slice for. Nothing checks that the named profile
  matches the paired printer, so a group that names the wrong one sees the wrong plate. The
  built-in default names the H2S profile.
- **The units of uploaded files:** whether a part uploaded from a file (an STL carries no
  units) is read in inches or in millimetres.
- **No secret.** The document holds no token, key or pairing code; the pairing code is
  typed into PenguinSlicer once and is then dead, and is no longer kept in the
  configuration ([the plan](../docs/plans/penguin-slicer-plan.md)).
- **Read whole, written whole, on a condition.** The front server reads the document when
  a user signs in and again when the wizard asks. An edit writes the whole document on the
  condition that it has not changed since it was read, so two users editing at once cannot
  silently overwrite each other; the second is told to reload
  ([the front server](../front/README-details.md#the-configuration)).
- **A built-in default.** A group with no document gets a built-in default configuration,
  so a new group can slice without setting anything up
  ([the front server](../front/README-details.md#the-configuration)).
- **A format number.** Like every record kept in the state bucket, the document carries
  the number of its format, so a document written for an older front server is read by a
  newer one ([the contracts](README.md)).
- **An annotated example,** included when the fields are written. The configuration's edit
  screens are a feature of their own, in no phase yet, with a design spec of their own
  ([the plan, Known future work](../docs/plans/penguin-slicer-plan.md#known-future-work)).
  Until they exist, a group uses the default, or a document the owner writes by hand and puts into the state
  bucket through Cloudflare's console, following that example
  ([the plan](../docs/plans/penguin-slicer-plan.md)). So (*proposed*) the example must say
  what every field means and which may be left out.
