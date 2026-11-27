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
  own names, with any settings that replace a profile's own, and no colour for the layer
  preview (not yet confirmed by the owner:
  [item 1.5](../wizard/README-details.md#15-a-colour-for-each-filament), below). Each
  filament has its own profiles, not one list for all.
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

## Recommended, needing the owner's yes

The first is a disagreement between the wizard's approved mockup and the approved design;
the other two are things the mockup shows that the design's configuration cannot give.
Each is explained, with both sides, in
[the wizard's list of them](../wizard/README-details.md#where-the-mockup-and-the-design-differ).

- **No colour for each filament.** The design gives each filament "the colour for the
  layer preview"; the mockup's version 8 draws the layer preview in four fixed colours,
  one for each set of line types, whatever the filament. Recommended: the configuration
  holds no colour ([item 1.5](../wizard/README-details.md#15-a-colour-for-each-filament)).
- **The printer's Orca profile.** The group's printer is linked to its daemon by the
  paired-printer record, not by the configuration. Recommended: the configuration names
  the printer's Orca profile, from which the plate's size and height come, for the Layout
  step and for the plate configuration's `printer`
  ([item 1.7](../wizard/README-details.md#17-whether-the-printer-is-in-the-configuration),
  [item 2.1](../wizard/README-details.md#21-the-plates-size-and-height)).
- **The group's own name and purpose for each profile.** The mockup's Settings step offers
  profiles by names such as "Structural" and shows a profile's purpose as its option's
  tooltip (its decision 10). Orca's own profile names are not names a group would choose,
  and say nothing of a profile's purpose. Recommended: each profile carries
  the group's own name and its purpose beside the Orca profile it uses
  ([item 2.5](../wizard/README-details.md#25-a-profiles-name-and-purpose)).
