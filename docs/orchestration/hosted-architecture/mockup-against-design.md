# The mockup's decisions against the hosted architecture design

This compares two approved documents. **The decisions** are
[the mockup's decisions, version 8](../../mockups/print-wizard/DECISIONS.md) (941 lines).
**The design** is
[the hosted architecture design](../../specs/2026-11-25-hosted-architecture-design.md)
(1,014 lines), approved after the decisions. Line numbers are those files' lines as of
Fri 2026-11-27. Each item quotes both sides and says what a user or builder would get wrong.
It does not say which side should win. Within each section the most consequential item
comes first.

## 1. Disagreements

Places where a statement in the decisions and a statement in the design cannot both be true.

### 1.1 Sending the same sliced plate again after a print

- **The decisions, decision 40** (lines 753-755): "A failed print says so on the card. A
  print that finished leaves no card (version 7): the last-print note takes its place at
  the top of the step (decision 60). Either way Send is enabled again for the same sliced
  plate, under the plate-clear reminder."
- **The design** (lines 277-279): "A sliced file can be previewed, downloaded, sent, and
  sent again after a print, for two hours after its slice ended. The front server enforces
  this: it refuses a sliced file older than two hours and deletes it."
- **What goes wrong:** after any print longer than two hours (and after a shorter print
  that ends more than two hours after the slice), a user is shown an enabled Send for a
  sliced file the front server has already deleted, and the send fails.

### 1.2 What a refresh or a reopened panel keeps

- **The decisions, decision 45** (lines 806-808): "The scenario strip's **Refresh page**,
  **Close and reopen** and **Come back 2 h later** throw away the page's state; what the
  server holds stays: this user's slice job and plate configuration, and the printer."
  **Decision 47** (line 815): "Otherwise it starts at the Parts step." **Decision 13**
  (line 539): "Changes last for this page load."
- **The design** (line 620, the state table): "Parts, layout, chosen settings, the current
  group, the id of the plate's slice job and when it was submitted | The browser's storage
  | Until the page, on opening, finds the plate's sliced file expired"; and (line 42): "The
  browser holds the user's parts and layout, in its own storage."
- **What goes wrong:** the decisions have a refresh on the Settings or Layout step (no
  slice yet) open an empty Parts step and drop the changes; the design restores the parts,
  layout and changes. A builder following one breaks the other, and a user cannot predict
  whether a refresh loses work.

### 1.3 Where a page that lost its state finds its slice job

- **The decisions, requirement on the slice service** (lines 274-276): "a page that has
  lost its state finds this user's running or finished slice job and its plate
  configuration, to resume on the Preview step. Not provided today."
- **The design** (lines 299-301): "A page that has lost its state (a refresh, a closed and
  reopened panel) reads the parts, the layout, the chosen settings, the id of the plate's
  slice job and the time it was submitted from the browser's storage, and asks the front
  server about that slice job." And (lines 316-317): "Work does not follow a user to
  another computer or browser: there the wizard opens empty."
- **What goes wrong:** the decisions ask the server to find the slice job and plate
  configuration by user. The design keeps them in the browser, so a builder may add a
  "my slice job" lookup the design does not have, or leave it out of one the decisions
  require. A user on a second browser, or in the panel after working in a tab, expects to
  resume and finds an empty wizard.

### 1.4 When the two hours of a finished unsent slice start

- **The decisions, M18** (line 233): "A finished slice that was not sent is dropped after
  two hours away." **Decision 48** (line 818): "After two hours away, a finished unsent
  slice is gone (M18)".
- **The design** (lines 277-278): "for two hours after its slice ended"; and (line 312):
  "Unknown, and the page submitted it more than two hours ago: its sliced file has expired".
- **What goes wrong:** the decisions count from when the user left. The design counts from
  the slice's end (or its submission) whether or not the page is open. A user who looked at
  the preview for an hour and then left loses the slice after one more hour, not two.

### 1.5 Per-filament colour of the layer preview

- **The decisions, requirement on the configuration** (lines 280-281): "(Version 8: no
  colour for each filament; the layer preview's colours are fixed.)" **Decision 33**
  (lines 642-643): "**Four fixed colours** (version 8, the owner, replacing version 6's
  two), one for each group of line types, whatever the filament".
- **The design** (lines 325-326): "For each filament it gives the colour for the layer
  preview and the profiles to slice with".
- **What goes wrong:** a builder writing the configuration document's contract adds a
  colour field for each filament that the wizard never reads, or draws the preview in the
  filament's colour against the owner's version 8 decision.

### 1.6 Who pairs the printer and edits the configuration, and where

- **The decisions, Terms** (line 164): "**administrator** | Whoever edits the
  configuration and pairs the printer." (line 165): "An administrator sets it once for
  everyone who uses it." **Decision 42** (lines 761-763): "No printer is paired with
  PenguinSlicer, so nothing can be sent. An administrator pairs the printer once, from the
  computer beside it." (The same words are in decision 58, lines 382-383.)
- **The design** (lines 52-53): "Every user of a group may edit its configuration."
  (lines 834-835): "**The administrator** is every user of a group: nothing distinguishes
  one user of a group from another." (line 435): "A signed-in user types the code into
  PenguinSlicer."
- **What goes wrong:** the wizard's message tells a user that someone else, at the computer
  beside the printer, must pair it. In the design, step 1 is run on the daemon's computer,
  but step 2 is done by any signed-in user of the group, typing the code into PenguinSlicer
  from any computer. A user who could pair the printer is told they cannot, and a builder
  may add an administrator role that the design rules out.

### 1.7 Whether the printer is part of the configuration

- **The decisions, Terms** (line 165): "**configuration** | The settings the header names
  ("Config: 6238 (Popcorn Penguins)"): the printer, the filaments, each filament's
  profiles, and the units of uploaded files."
- **The design** (lines 323-324): "A group's configuration is one JSON document in the
  state bucket ... It holds the group's filaments and the units of uploaded files." The
  printer is in the paired-printer record (line 81), and (line 838): "**One printer per
  group** for now, where the plan's configuration lists printers."
- **What goes wrong:** a builder reading the decisions puts the printer in the
  configuration document, where the design keeps it in a separate record written only by
  pairing.

### 1.8 A part that cannot be used: a row or a notification

- **The decisions, decision 16** (lines 423-426): "**Onshape cannot export a part** (a
  broken part): a notification names the part ... The part is not added". **Decision 17**
  (lines 431-432): "The list never holds a broken row." **Decision 19** (line 435): "A file
  that cannot be read on the standalone page is a notification and is not added."
- **The design** (lines 237-239): "The slice service runs its checks on the part as it
  arrives, so a part that cannot be sliced is refused on the Parts step, on its own row,
  before the user has laid anything out."
- **What goes wrong:** the builder of the Parts step must choose between a refused row and
  a notification with no row. One document is wrong whichever is built.

### 1.9 Retries that end in an error, against "a pause, not an error"

- **The decisions, decision 17** (lines 428-431): "**Our server cannot be reached:** the
  page retries quietly; ... after 20 seconds of failed retries a notification says the
  part was not added and to click it in Onshape again".
- **The design** (lines 688-690): "**Every client retries.** ... The page does the same for
  every request it makes, so a request that falls in the gap is repeated and the user sees
  a pause, not an error." And (line 637): "a deploy at any moment interrupts no user."
- **What goes wrong:** the design does not bound how long a restart takes. A deploy whose
  gap is longer than 20 seconds shows the decisions' error and drops the part, which the
  design's rule forbids.

### 1.10 Where a returning page opens after its print ended

- **The decisions, decision 46** (lines 809-811): "when this user's delivery job is
  running, it reopens on the Send step with live progress." **Decision 47** (line 815):
  "Otherwise it starts at the Parts step." **Decision 48** (lines 821-822): "A print of
  this user's that finished is the last-print note on whichever step opens".
- **The design** (line 314): "From phase 5, a page whose plate has a delivery job opens on
  the Send step."
- **What goes wrong:** for a plate whose print has ended within the two hours, the decisions
  open the Parts step and the design opens the Send step, because the delivery job's record
  still exists (kept a day, line 455).

### 1.11 How the standalone page finds its configuration

- **The decisions, "What is fake", item 25** (lines 937-938): "The standalone page
  imitates opening the configuration from a saved link".
- **The design** (lines 51-52): "**Every user signs in with Onshape,** in Onshape's panel
  and outside Onshape alike." (lines 339-343): the configuration is the current group's,
  chosen in the header and checked against the sign-in cookie.
- **What goes wrong:** a builder may add a configuration link to the standalone page. In
  the design, the configuration comes only from the user's group, and a link would bypass
  the group check.

## 2. The mockup shows something the design gives no means for

### 2.1 The plate's size and height limit on the Layout step

The decisions show "Shop H2S: plate 340 × 320 mm, up to 340 mm tall, 12 mm apart"
(decision 55, lines 471-472) and use the plate size for Arrange and the placement check
(decision 27, lines 567-568: "3 mm inside the edge, 340 mm tall"). The design's
configuration "holds the group's filaments and the units of uploaded files" (line 324).
The paired-printer record holds "the printer's display name" (line 81) and no model, plate
size or height. No stored value or route gives the Layout step the plate's figures, nor
the slice service the printer model to slice for.

### 2.2 Who sent a print, what it is, and when the last one finished (requirements 1, 2 and 4)

Requirement 1 (lines 246-248) asks that the delivery job carry "the Onshape display name
of the user who sent it" and that the printer status return it. Requirement 2 (lines
249-252) asks for "a one-line description of the plate". Requirement 4 (lines 256-261) asks
for "The end time and the sender of the last print that finished". Decision 44 (line 788)
shows for Failed "when it stopped and at which layer". The design says what users see:
"Users of one group do see each other's names and a one-line description of a plate that
is printing, on the printer-status icon" (lines 733-734), and keeps "A delivery job's
record ... for a day after the delivery job ends, so that the Send step and the
printer-status icon can show how the last print ended" (lines 455-457). It lists no field
of the delivery job's record, the send or the sync that carries the sender's name, the
plate's description, the end time or the layer of a failure. A user's name is written
only "at sign-in and on an error" (line 595), in the log.

### 2.3 Finding this user's delivery job and its last print after the page lost its state (requirement 3)

Requirement 3 (lines 253-255) asks that "A page that has lost its state finds this user's
live delivery job". Decisions 46 and 48 (lines 809-822) reopen the Send step with live
progress, report a failed print in a notification, and show the last-print note on
whichever step opens. The design's browser storage holds "the id of the plate's slice
job" (line 620) and no delivery job id. Line 314 says the page opens on the Send step when
its plate has a delivery job, but no route gives the page its own delivery job, by user,
by plate or by slice job, and nothing tells a returning page that its print failed or
finished.

### 2.4 "Not heard from for 7 minutes"

Decision 44 (line 789) shows "Offline: "Not heard from for 7 minutes."", and decision 42
(lines 764-765) says an offline printer's message "says how long since the printer was
last heard from". The design keeps "Printer status and the progress of a print | The
relay's memory | Until the next sync replaces them | Gone" (line 629). After a restart of
the front server, the time a daemon was last heard from is lost, so the design gives no
means to say how long a daemon that is still off has been silent.

### 2.5 A profile's name and purpose

Decision 10 (lines 487-492) shows profiles such as "Structural, Pulley, Camera mount" and
says "A profile's purpose is its option's tooltip". The design's configuration gives each
filament "the profiles to slice with, by the names Orca gives them, with any settings that
replace a profile's own" (lines 325-327). It stores no name of the group's own for a
profile and no purpose text.

### 2.6 The "plate too large" error

"What is fake", item 9 (lines 909-910) says: "The plate-volume cap (600 cm³) is invented;
armed "plate too large" lowers it for one plate". The design's limits on one slice are the
memory ceiling and the time limit (lines 167-170), and it has no cap on a plate's volume
that this error could report.

## 3. The design requires something of the wizard that the mockup does not show

### 3.1 Signing in

The design: "Every user signs in with Onshape's OAuth, the same way in Onshape's panel and
outside Onshape" (lines 347-348), and "Every route of the front server refuses a request
without a signed-in user" (line 354). The cookie lasts thirty days (line 361), and in an
emergency key replacement "Every user then signs in again" (lines 802-803). The decisions
show no sign-in, no signed-out state and no expired sign-in on any step.

### 3.2 Choosing the current group, and "sign in again"

The design: "The wizard's header names it, as the mockup's "Config:" line does, and the
user changes it there" (lines 340-341), and "The wizard's header has a "sign in again"
action beside the current group's name, which reads the groups afresh" (lines 385-386;
also line 939). The decisions' header (decision 2, lines 308-309) has the configuration's
name and a reload glyph, with no group choice and no "sign in again".

### 3.3 A sliced file that expires while the page is open

The design refuses a sliced file "older than two hours" (line 279) whether or not the page
is open. The decisions show expiry only on return ("Come back 2 h later", decision 48),
and their **12 hours later** (lines 833-834, 939-941) moves the clock "with the panel left
open" and shows only the last-print note going. No step shows Send, Download or the
preview refused for an expired file, nor what follows the Cancel-sending notification's
"Your sliced plate is still here." (decision 37, lines 746-747) once it has expired.

### 3.4 A slice that waits, and no room to wait

The design: "A slice that cannot start yet waits, and its user is shown that it is waiting
and how many slices are ahead of it" (lines 184-185), and "When no more may wait, the user
is told the slice service is busy and to try again shortly" (lines 186-187). The decisions'
slicing card (decision 30, lines 622-624) has stages, elapsed and time left, but no waiting
state, no count of slices ahead and no busy answer.

### 3.5 Pairing in PenguinSlicer, a wrong code, and unpairing

The design: "A signed-in user types the code into PenguinSlicer. ... If none is, the user
is told at once that no daemon is showing that code and to try again in a moment" (lines
435-438); "A wrong code gets the same answer whatever was wrong with it, and attempts are
limited for each user" (lines 448-449); and "Unpairing removes the paired-printer record"
(line 459). The decisions show only "No printer is paired" with a "How to pair a printer"
link (decision 42, decision 44 lines 790-791): no field for the code, no wrong-code or
rate-limit answer, and no unpair action.

### 3.6 A stale delivery job and "stop following"

The design: "A running delivery job's report is fresh | The daemon's last sync was within
40 seconds | The report is marked stale. A stale delivery job whose print was started may
be given up by the user ("stop following")" (line 524). The decisions' printer-status
icon and Send step (decisions 37, 43, 44) show no stale report and no "stop following".

### 3.7 A page reloading itself on a new version

The design: "a page that sees a newer version reloads itself at the next moment when
nothing is in flight" (lines 699-700; also line 938). The decisions show no reload of this
kind and do not say what the user sees across it, which matters because decision 13
(line 518) has "A reload forgets it all" for advanced mode's open sections.

### 3.8 Two tabs: a slice cancelled by a later one

The design's table (line 311): "Cancelled by a later slice of the same user | Shows the
plate on the Preview step and offers to slice it; it does not submit by itself". The
decisions show no Preview step state for a slice cancelled from another tab.

### 3.9 What a restart shows

The design: when the slice container restarts, "Progress starts again" (line 649); when the
front server restarts during a print, "The printer-status icon and the Send step are blank
until the daemon's next sync" (line 660). The decisions show neither a slicing card whose
progress goes back to its start nor a blank printer-status icon or Send step.

### 3.10 A printer busy with a print nobody sent from PenguinSlicer

The design syncs "Printing, whoever started the print" (line 501) and refuses a send to a
printing printer "whether PenguinSlicer sent the print or someone started it at the
printer's own screen" (lines 514-517). The decisions define the busy printer as one
working "on another user's delivery job" (line 193), and its card says "whose, what"
(decision 41, line 756). They show nothing for a print with no sender and no description.

### 3.11 Limits on parts

The design uploads each part "in one request of at most 7.5 MB" (lines 229-230) and the
part store "holds at most 25 parts for one user key, the most a plate can use" (line 250).
The decisions limit instances to 150 (decision 22, line 439) and show no limit on a part's
size and none on the number of distinct parts on a plate.

### 3.12 Running out of memory

The design's memory ceiling ends a slice with `slice.out_of_memory`, "an error the wizard
explains" (lines 141-143, 169). The decisions' slicing failures (decision 32, lines
627-634) name the empty-layers, faulty-mesh and timeout failures and show no
out-of-memory message.
