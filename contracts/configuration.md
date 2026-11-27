# Configuration

What the configuration document must hold. **Its fields are not written yet:** their
names, types and an annotated example are written before phase 2's building starts. Until
then this file collects what is decided about the document, and says where a requirement
rests on an item still undecided, with a link to the guide that owns the item.

A group's **configuration** is the settings shared by everyone in one group, the users who
share one configuration and one printer (one Onshape company or classroom, or a user alone
who belongs to none). The [front server](../front/README.md#the-configuration) keeps it
and the [wizard](../wizard/README.md#the-current-group) reads it through the front
server, for the current group only.

## What it holds

- **The group's filaments.** For each filament, the profiles the wizard offers for it,
  each naming the Orca profile it uses by Orca's own name, with any settings that replace
  that profile's own. Each filament has its own profiles, not one list for all. The
  wizard offers a filament's profiles from the configuration and from nowhere else.
- **The group's own name and purpose for each profile,** beside the Orca profile it uses.
  The Settings step offers profiles by the group's names (such as "Structural") and shows
  a profile's purpose as its option's tooltip, because Orca's names are not names a group
  would choose and say nothing of what a profile is for
  ([The Settings step](../wizard/README.md#the-settings-step)).
- **A colour for each filament,** which the wizard shows where the user chooses a
  filament, so that two filaments of one material (a red PLA and a green PLA) can be told
  apart. It is never used in the layer preview, which draws every plate in four fixed
  colours, one for each group of line types, whatever the filament
  ([The result](../wizard/README.md#the-result)).
- **The printer's Orca profile,** from which the plate's size and height come (the
  profile's `printable_area` and `printable_height`), for the Layout step and for the plate
  configuration's `printer`. The group's printer is linked to its daemon by the
  paired-printer record, written only by pairing, not by the configuration; the
  configuration names only the profile to slice for. Nothing checks that the named profile
  matches the paired printer, so a group that names the wrong one sees a plate of the
  wrong size.
- **The units of uploaded files:** whether a part uploaded from a file (an STL carries no
  units) is read in inches or in millimetres. The wizard sends those units beside the part
  as a label and never changes its bytes; only the slice service applies the scale, and
  the same file under other units is another part
  ([Units](../slice/README.md#units),
  [the plate configuration](plate-configuration.md#to-be-built)). Whether the wizard may
  offer its own switch between the two until the edit screens exist, so that a group on
  the built-in default can use an STL file in millimetres, is undecided
  ([STL files in millimetres before the edit screens exist](../wizard/README.md#stl-files-in-millimetres-before-the-edit-screens-exist)).
- **A format number.** Like every record kept in the state bucket, the document carries
  the number of its format, so a document written for an older front server is read by a
  newer one ([the contracts](README.md)).
- **No secret.** The document holds no token, key or pairing code; the pairing code is
  typed into PenguinSlicer once and is then dead, and is never kept in the configuration
  ([Pairing in phase 5](../delivery/README.md#pairing-in-phase-5)).

What it does not hold: which daemon is the group's (the paired-printer record), and the
list of settings that advanced mode offers, which comes from the slice service if the
recommendation under
[Where the wizard gets the list of settings and the profile catalog's names](../slice/README.md#where-the-wizard-gets-the-list-of-settings-and-the-profile-catalogs-names)
stands; that item is to be answered before phase 2.

## What the profiles and settings in it may name

- **Profiles by the catalog's names.** Each Orca profile the document names must be in
  the profile catalog of the slice service that slices for it; the slice service refuses
  a name it does not know. After an Orca upgrade a name can leave the catalog. Who
  notices a configuration that names a lost profile is undecided; recommended, the front
  server checks every configuration against the catalog's names, which the slice service
  supplies, when it starts and when a configuration is edited
  ([Who notices a configuration that names a profile the catalog has lost](../slice/README.md#who-notices-a-configuration-that-names-a-profile-the-catalog-has-lost),
  [The list of settings and the profile catalog's names](../front/README.md#the-list-of-settings-and-the-profile-catalogs-names)).
- **Settings the slice service accepts, and no others.** The settings a profile adds are
  held to the same rule as a user's changes: every setting Orca allows that is a parameter
  with a value, and none that runs a program, names a file on the server or carries custom
  G-code ([Accept settings](../slice/README.md#accept-settings)). Which profiles a setting
  may replace values of is undecided, recommended the process profile only
  ([How the list of accepted settings is made](../slice/README.md#how-the-list-of-accepted-settings-is-made)).

## How it is kept

- **One JSON document for each group,** kept in the state bucket, the object store where
  the front server keeps what must outlast its restart. It is read whole and written
  whole.
- **Read whenever the wizard asks,** for the current group: when a page opens, and so
  after every sign-in, and when the user presses the reload glyph beside the current
  group's name ([Reading it and writing it](../front/README.md#reading-it-and-writing-it)).
- **Written on a condition.** An edit writes the whole document on the condition that it
  has not changed since it was read, so two users editing at once cannot silently
  overwrite each other; the second is told that someone else changed it and to reload,
  and nothing is merged. Every edit writes a log line with the user's name and what
  changed.
- **A built-in default.** A group with no document gets a built-in default configuration,
  which names the H2S profile, so a new group can slice without setting anything up.
- **A document that cannot be understood** (damaged, or of a format the front server does
  not know) is reported as an error and never replaced by the default, so a group's
  hand-written document is not lost to a typing mistake; the group cannot slice until it
  is mended (a choice the owner has not yet confirmed:
  [Choices the owner has not yet confirmed](../front/README.md#choices-the-owner-has-not-yet-confirmed)).
  What the wizard shows then is undecided
  ([A configuration that cannot be read](../wizard/README.md#a-configuration-that-cannot-be-read)).
- **A fixed set, until the edit screens exist.** The configuration's edit screens are a
  feature of their own, in no phase yet, with a design spec of their own
  ([the plan, Known future work](../docs/plans/penguin-slicer-plan.md#known-future-work)).
  Until they exist there is a fixed set of configurations: the built-in default, and
  documents the owner writes by hand and puts into the state bucket through Cloudflare's
  console, following the annotated example. No user can change one
  ([The fixed set, until the edit screens exist](../front/README.md#the-fixed-set-until-the-edit-screens-exist)).
- **An annotated example,** included when the fields are written. Since documents are
  written by hand until the edit screens exist, (*proposed*) the example says what every
  field means and which may be left out.
