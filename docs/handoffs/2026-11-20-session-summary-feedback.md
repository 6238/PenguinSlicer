# Owner's feedback on the session summary (working notes)

Temporary file. It collects the owner's feedback on
the session summary of Fri 2026-11-20 (since deleted; its content is in
[the plan](../plans/penguin-slicer-plan.md) and the components' guides), given in pieces from
Fri 2026-11-20. Nothing is to be rewritten until the owner says the review is finished.
Delete this file once the changes are made.

## General

- **No running list of decisions.** Once a decision is made, the documents are rewritten
  to state the result. The documents the owner reviews describe the state of affairs at
  the time of review; they do not accumulate decisions and their answers.

## Terms

- **"copy"** is confusing when a part is on the plate once. Owner suggests "placement" or
  another word. Applies to the mockup and the documents.
- **"HTTP face"** is confusing. Owner suggests "interface", perhaps "slice service
  interface".
- **Auto-orient, Arrange** are buttons that may change; remove them from the terms table.
- **"plate job"** does not sound like work being done; it is a configuration. Owner
  suggests "plate configuration", with "slice job" kept for the work. The owner still
  finds the pair a little confusing.

## Decisions

- **D1.** Repository `PenguinSlicer` in the `6238` organization, like `6238/PenguinCAM`,
  using the owner's GitHub account `chondl`.
- **D2.** The description is hard to follow. Leave it out as a decision; keep it as a test
  for the session at the real printer, and understand the real problems then.
- **D3.** Yes, fix the remaining small open items now.
- **D4.** Read Orca's debug log; no patch to Orca. The Orca version is pinned, so the log
  format changes only at an upgrade. The upgrade process gets a scripted test that
  verifies the debug-log reading still works; if it fails, the reading is fixed then.
- **D5.** Stay on Orca 2.4.2. Record the 2.5.x upgrade as known future work.
- **D6.** Daemon telemetry is part of the initial work. A protocol for the daemon to send
  messages back, recorded on the server. It helps development now and is ported when the
  daemon moves to Rust or Go. Why it matters: the daemon runs on a wide variety of
  hardware, and the problems are hard to foresee: network misconfiguration, hardware
  platform capabilities, issues with the UI, the host computer going to sleep, the host
  being overloaded, the daemon timing out because its host runs slowly.
- **D7.** Move Penguin Slicer's specs and plans into the Penguin Slicer repository.
- **D8.** The proposed reference plates are good enough, but the limit of 25 copies is too
  low: as many as 100 small parts in a 10 by 10 grid. Raise the limit, and use a small
  spacer for a 3/8 inch hex shaft, 1/8 inch thick, as the sample for that plate.
- **D9.** Do not worry about the printer's certificate.
- **D10.** Remove the Raspberry Pi installer: never tested, probably never needed.
- **D11.** Not a concern: the workspace `CLAUDE.md` is not generated from anywhere on the
  Mac, as far as the owner knows.

## The owner's answers to four questions

1. "copy" becomes **"instance"**.
2. D1: `6238/PenguinSlicer` is public. Done Fri 2026-11-20: created at
   https://github.com/6238/PenguinSlicer, branch `build/ports-and-hardening` pushed.
   `main` pushed and made the default branch; the build branch merged into it by
   pull request 1 (merge commit `1997432`). From here every change goes through a pull
   request that the agent opens and merges; the rule is in the workspace `CLAUDE.md`.
3. D7: everything moves to the Penguin Slicer repository: the plan, the mockup, the
   wizard research and the orchestration records.
4. D3: hold the fixes until the review is finished.

## Open items

- **S2** is a real design flaw, not an optional low item: an HTTP header must not carry
  10 kB or more. The owner left the design of the HTTP interface to the agent, with no
  need to check back. Chosen: a route `GET /slices/<job>/summary` returns the summary as
  a JSON body, with the file route's error reports for a slice job that failed, was
  cancelled or is not finished; the file route returns only the file and the
  `X-Slice-Summary` header is removed. Built with the other fixes after the review.

- **S4, and the number of interfaces.** The owner's concern: a component should have one
  interface used in all contexts; the slice service appears to have a command line, an
  HTTP interface and direct access to inner functions. Found in the code: three
  documented ways in (the Python function `slice_plate_job`, the command `slice` that
  wraps it, the HTTP interface that also wraps it), plus the internal
  `slicer.slice_plate` that S4 is about. S1 and S10 exist only because the ways in
  differ. **Owner's answer:** the HTTP interface is the slice service's one interface. In
  time there may be several instances of the slice service, possibly on a machine other
  than the web application's, so HTTP is right. The Python function and the internal
  function are not interfaces of the component. **Remove the `slice` command:** there is
  no requirement that a person can slice by hand; for testing and development an agent
  writes throwaway scripts against the HTTP interface. The `serve` command stays, as the
  way the service is started.
- **One interface per component is the default, not a hard rule.** The wizard may exist
  both inside Onshape and as a page reached directly from a browser; the Onshape source
  may likewise be hosted in Onshape and separately. Write it in the repository's notes
  for agents as a default.
- **Consequences to carry into the fixes:** S1 and S10 go away with the `slice` command;
  ruling R3 loses its command-line half; S4 is no longer about a supported way in; S8
  (one process per service) matters more once several instances are planned.

## Scope the owner gave before leaving (Fri 2026-11-20)

Go ahead: record the decisions, update the relevant documents, the plan and the session
summary, and make the code fixes discussed. The owner has reviewed only the terms,
section 2.1, section 3 and section 4.1; the rest of section 4 and the mockup are still to
review, and no other change may start until that review is finished.

The owner writes the name as **PenguinSlicer**, one word.

## Feedback of Sat 2026-11-21

- **The team's real parts.** Eight STL files of parts from the Popcorn Penguins' robot
  (`/repos/popcornpenguins/PartsFRC/`) go into the slice service's tests under the MIT
  licence, keeping the existing test parts. The team's mechanical mentor's target: **4
  instances of each part on 2 build plates of the H2S**. If that needs more memory, the
  slicer's memory ceiling is raised.
- **The whole repository is MIT**, with PenguinCAM's licence text; the copyright holder is
  "Popcorn Penguins, Inc." Refer to the team as the Popcorn Penguins.
- **The wizard should look like PenguinCAM:** the panel can be widened by dragging, so
  the design works at 320 px but is not fixed to it; light mode, not dark; text and
  control sizes, spacing and alignment as PenguinCAM's. The screenshots and the full
  points are in [the visual reference](../reference/penguincam-in-onshape/README.md).
  The mockup is not changed until the owner's review of it is finished.

## Mockup feedback of Sat 2026-11-21

Recorded only: no work starts on it until the owner says so.

**Keep.** Quantity on each row of the parts list (instances by quantity) and the 3D
picture of each part. PenguinCAM's parts list has neither; the owner prefers this.

**The wizard's steps.**

- Moving backwards and forwards between steps is an important capability, and it stays.
- The Layout step does not change the list of parts: no duplicate or delete buttons
  there. To change how many instances there are, the student goes back to the Parts step
  and forward again.
- No undo or redo on the Layout step: expensive, and not needed.
- Sending to the printer becomes its own step after Preview. It is complicated enough
  that sharing the Preview step's screen is a problem.
- The progress shown on the Preview step while slicing is good as it is.

**Printer status always visible.** Once the wizard is open, if a print is already
running it says so, and whether the print is behind. A small printer-status icon at the
top of the panel, which expands on a click to give the details, is one way.

**Work already running.** The mockup must show what happens when the page is refreshed,
the student comes back to the page, or the wizard is closed and opened again while
something is running, whether started by this user or by another. And what happens when
a student sends to the printer while another user's print or send is running; how that
meets the relay and the daemon is to be worked out and shown in the mockup.

**A part that will not export** (screenshot: [export-failed.png](../reference/mockup-v3-feedback/export-failed.png)).

- The mockup's "Details for a mentor" shows an HTTP request, a status code and a page
  id. Nothing a student sees may mention PenguinSlicer's internals. Any detail must be
  something a mechanical engineering mentor or a very experienced student understands
  (for example: what about the part is wrong, and where to look in Onshape).
- "Try again" makes no sense for a broken part: a part Onshape cannot export is most
  likely broken in Onshape, so a retry will not help. It is a hard error.
- **Export failed** (the part or its STL is broken): show a notification, do not add the
  part to the list, and do not disable Next.
- **A problem reaching our server** is probably transient: retry quietly in the
  background, show progress, say when it is taking longer than usual, and report a
  failure only when the retries have failed.
- In either case: a notification, the list of parts unchanged, and never a broken entry
  in the list that disables Next.

## Mockup version 5 feedback of Tue 2026-11-24

Given a step at a time. At about 22:30 the owner asked for all of it to be built into
mockup version 6. The Layout step was not reviewed in this round.

**Parts step.**

- Good as it is: the 3D picture beside each part in the list, and the list's size for
  the page and the likely number of parts.
- Adding parts from files (the wizard opened outside Onshape) looks good and works.
- **Units of the sizes.** The team mostly works in inches but sometimes imports metric
  parts, and some projects off the main robot are metric. An STL carries no units, and
  guessing them from a part's size would feel inconsistent and flaky, so the wizard never
  guesses:
  - **Picked in Onshape:** the units of the assembly or Part Studio; failing that, the
    part's own units or Onshape's default units, whichever the API gives.
  - **Uploaded from a file** (the wizard outside Onshape): inches by default. An option
    in the configuration (the one the header names, set once by an administrator for
    everyone who uses it) makes millimetres the default.
  - **The plate's size** is in millimetres, as Bambu Lab specifies it.
  - **Spacing and heights** are in inches when every part on the plate is in inches,
    otherwise in millimetres.
- **In an assembly, too many words** (screenshot of the version 5 panel in the owner's
  message):
  - Drop "Add every part in the assembly", its sentence, and the notice it produces
    (the "Added the 7 parts of Intake v3…" card). It is a feature not needed at first
    and it adds complexity.
  - Clicking an instance, in Onshape's instance list or in the graphics area, is enough.
  - The prompt says only something like "Click a part in the assembly"; no help text
    beneath it. The same in a Part Studio: no help text.
- **The prompt does not change when a part is added.** Its "Added one more: HTD Pulley
  24T: 2 instances." is redundant: only the list of parts updates.
- **No refresh button on a row of the list.** If the part changes in Onshape, the
  student removes it and adds it again. A row keeps its name, size, quantity and remove
  button.

**Step 2 is named "Settings"**, not "Setup": the steps are Parts, Settings, Layout,
Preview, Send.

**Settings step** (called Setup in version 5). Less help text in general.

- **The chips row as on Layout:** the Settings step shows the same chips as the Layout
  step (parts and instances, filament, profile, "+1 change"), updating at once as the
  filament, profile or a setting changes. The same chips on both steps is consistent.
  The "+1 change" chip is clickable on every step where it shows: a click opens, joined
  to the chip as the printer-status details are, the list of changes in the yellow box's
  wording ("Quality › Resolution: 0.014 mm (profile 0.012 mm)"), as plain text, not
  links.
- **No printer row** ("Printer: Shop H2S, Bambu Lab H2S 0.6 nozzle, Free"): it repeats
  the printer-status icon.
- **Each filament has its own profiles.** The configuration lists them per filament, so
  the profile menu offers the profiles of the filament chosen. The mockup offers the
  same profiles for every filament; it should show different ones.
- **No help text under the profile control.** The one exception: once the user has
  changed a setting, a one-line warning with a caution icon appears there saying that changing the filament
  or the profile clears those changes. It stays until the changes are cleared. (This
  refines M13: changing the filament changes the profile, so it clears changes too.)
- **The setting controls (infill, walls, supports, brim):** one per row, full width,
  below 480 px, because they are too cramped at 320 px. Two per row from 480 px.
- **Sentences to remove:** "Pick the filament and the profile; change a setting only if
  this print needs it."; "Your team's configuration lists these printers, filaments and
  profiles; a mentor changes them there."; in advanced mode, "Every slicing setting,
  grouped as in Orca Slicer."; "Your changes stay for this print."

- **Changed settings replace the Advanced mode button.** Once a setting is changed,
  the yellow box listing the changes takes the place of the Advanced mode button. The
  box has one button, "Advanced mode" (more discoverable), and each line of its list is
  also a link that opens advanced mode at that setting (more direct, for those who know).
  No "Reset all" button in the box, and no second advanced mode button. Advanced mode
  keeps its own "Reset all" button: with each setting's "Reset" link and picking the
  profile again, it is a way to clear the changes.

**Advanced mode** is getting too complicated.

- **No search box** for the settings.
- **No Common / All switch:** every setting is shown, in collapsed groups as in Orca
  Slicer.
- **Narrow panel: an accordion, not pills.** Below 480 px the five sections (Quality,
  Strength, Speed, Support, Others) are not tabs: the pills wrapped to two rows and
  looked like the step pills and chips. Each section is a bold heading with a chevron
  and its changed count; opening one shows its groups, one level in, with the same
  chevrons; one section is open at a time. The Expand all / Collapse all icon sits at
  the right of the open section's heading. From 480 px, the rail of section names down
  the left with the groups beside it, as in version 5.
- **The groups are always one column**, however wide the panel: version 5's two columns
  from 700 px go. The column has a maximum width (about 480 px) so each value stays
  near its name. This settles M5.
- **Expand all / Collapse all:** in each of advanced mode's tabs, one icon button (not
  a word) that opens or closes all of that tab's groups: a double chevron (unfold more / unfold less)
  with the tooltip "Expand all" or "Collapse all", at the far right of the row of tabs,
  so it takes no line of its own. Where the tabs become a rail down the side (from
  480 px in version 5), it sits at the top right of the groups instead.
- **A group's heading** starts with a chevron that points right (towards the name) when
  the group is closed and down when it is open, in place of today's small triangle.
- **A group's heading** shows no count of its settings; it keeps the changed count when
  a setting in it is changed: "Precision · 1 changed", not "Precision 5 · 1 changed".
- **A changed setting** keeps its tinted background, the bar on its left and the dot
  after its name. The line under it says "Profile 0.012 mm" (not "Pulley: 0.012 mm":
  the profile's name on every changed setting is redundant), followed by a "Reset" link
  that puts the profile's value back. No revert-arrow icon. The yellow box's lines use
  the same word: "Quality › Resolution: 0.014 mm (profile 0.012 mm)".
- **Slicer settings are always in millimetres** (layer height, line width, hole
  compensation and the rest), as in Orca Slicer and the profiles, whatever the parts'
  units.

**Preview step: two colours.** The key of six line types (outer wall, inner wall,
sparse infill, internal solid infill, top surface, bottom surface) is too much. Orca
Slicer's default "Line Type" view colours every line type and lets each be hidden; that
suits someone tuning a print, not someone checking a plate. PenguinSlicer draws the
parts in the filament's colour and supports (with their interface) in a light grey. The
key is two items, "Part · Supports", shown only when supports are on. No hiding of line
types, and no help text ("Click a line type to hide it…" goes).

**Arrange follows the Settings step.** Settings comes before Layout, so Arrange leaves
the spacing the slice service requires for the supports setting chosen there: 12 mm with
supports on, 5 mm with them off. The placement check uses the same spacing.

**Not only for FRC teams (applies to the whole interface).** PenguinSlicer will be used
by people who are not FRC teams, so no text a user sees says "mentor", "team" or
"student". Avoid describing roles at all; if a difference in permissions has to be
named, the word is "administrator".

The documents follow the same rule: "user" for the person using PenguinSlicer and
"administrator" for whoever edits the configuration, in the plan, research, contracts
and `DECISIONS.md` alike. The sentences the slice service and printer delivery write
change later, as their own change with their tests.

**Help text versus error text.** The two get opposite treatment:

- **Screens people work on: little help text.** The tool takes 30 minutes to an hour to
  learn; after that, help text only takes space, and most people don't read it even the
  first time. No instructions under step titles or controls. A short line only where an
  action has a consequence the user can't see (the caution about clearing changed
  settings) or a control does not explain itself. Tooltips are fine.
- **Errors: more information is welcome.** People read errors, and they are confused
  when one appears. Say what went wrong and add whatever is truly specific to this error
  and helps understand or fix it (which part, what about it, where to look). No generic
  troubleshooting and no internals.

**Printer-status icon.** Basic information only; print management happens at the
printer. Adding more is over-engineering.

- **The details open as part of the icon**, like a tab that expands and collapses from
  it, visually joined to it. Today they open as a separate card that floats away from
  the icon and reads like an information message.
- **Shorter text everywhere.** Free: "Nothing is printing." and nothing more.
- **Another user sending:** good as it is, including the pulsing icon in the header.
- **Printing:** show who sent it (their Onshape name), percent done, time left and the
  finish time; nothing more. Drop the sentence about when the printer last reported and about pausing
  or stopping at the printer's screen. Drop "behind its estimate" too: not useful.
  (This takes back "whether it is behind" from the earlier ruling and settles M24.)
- **Finished:** drop the reminder to take the plate off before the next print.
- **Offline:** keep how long since the printer was last heard from; drop the advice to
  check the printer, turn it on and connect it to the network.
- **No printer paired:** say only that PenguinSlicer needs to be paired with a printer,
  with a link to a documentation page to be written later.
