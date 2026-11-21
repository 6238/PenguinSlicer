# PenguinSlicer: summary of the session of Thu 11-19 and Fri 11-20

> **What changed in this revision** (Fri 11-20 12:40 PT; remove this block when your
> review ends). The terms take your new words, drop Auto-orient and Arrange, and define
> slice job, main state, start note, recording and the daemon's computer. Section 2.1
> holds no decision: each result is written in its own section. Sections 1, 4.1, 4.2
> (same structure), 6 and 7 are rewritten to the present state, with the third review
> rounds' figures; 3.1 and 3.2 name the plan and GitHub; section 3.6 is new. In the
> sections you have not read (2.2 to 2.5, 4.3, 4.4, 5) only terms, facts no longer true
> and what follows from your decisions changed (R3, R4, R7, R11, R13, R15 to R18).

Written Fri 2026-11-20 at 02:30 PT, for the owner, and revised Fri 2026-11-20 at 12:40 PT.
All times are Pacific. It covers one working session, from the late afternoon of
Thu 2026-11-19 to Fri 2026-11-20 02:21 PT, when the last work was committed, and the
review-feedback run of Fri 2026-11-20 morning (section 3.6). The owner was present until
about 23:30 PT on Thu 11-19; the rest of that night ran unattended.

This file is meant to stand alone. Everything the owner has to answer or do is copied
into section 2 in full. Links to other files are evidence, not required reading.

## 1. Short answer

- The 3D printing work lives in its own repository, **PenguinSlicer**:
  https://github.com/6238/PenguinSlicer, public, checked out at
  `/repos/popcornpenguins/penguin-slicer`. Every change reaches `main` through a pull
  request.
- **The slice service is ported, hardened and brought into line with the owner's
  feedback.** Its HTTP interface is its one interface; it takes up to 150 instances on a
  plate; it reads Orca's reason for a failed slice from Orca's debug log. The third review
  round of the review-feedback run judged it fit to merge, with two low defects; the third
  fix round fixed both, and the change is on `main` (pull request 4). What is open now is
  in section 4.1.
- **Printer delivery is ported, hardened, and its small open items are fixed.** Its third
  review round judged it fit to merge with two low defects, which the third fix round
  fixed; the change is on `main` (pull request 5). Two open items remain, P1 and P2 (section 4.2): they become
  serious only if the real printer behaves in a way nobody has yet observed, and the
  session at the real printer (section 2.4) measures that. Daemon telemetry is part of the
  initial work on printer delivery and is not yet designed.
- **The wizard exists only as a mockup**, in its third version, now with the new terms,
  with options for the owner to compare (section 2.3).
- **What needs the owner** is in section 2, grouped by kind: no decision is open (2.1),
  rulings to confirm or reverse (2.2), the mockup's questions (2.3), a session at the real
  printer (2.4), and facts only the real Onshape panel can settle (2.5). Section 7 lists
  ways forward by risk.
- The code changes of the review-feedback run are on `main`: pull request 4 for the slice
  service, 5 for printer delivery. They were merged after their third fix rounds on the
  evidence of the suites, with no fourth review round.

## Terms

Each term means one thing everywhere in this file.

| Term | Meaning |
|---|---|
| **Orca** | Orca Slicer, the open-source slicer that turns models into printer instructions. It runs on the server with no window. Version 2.4.2 is the one in use. |
| **H2S** | The team's Bambu Lab H2S printer. |
| **print branch** | The branch `feature/onshape-test-bed` in PenguinCAM, which holds the first attempt at 3D printing. It is now only a source to port from. |
| **restart notes** | The file of Sun 2026-10-11 that described the first attempt and the owner's feedback on it. |
| **plan** | The PenguinSlicer restart plan, first written Thu 2026-11-19 and kept to the present state. |
| **PenguinSlicer** | The repository and the product in it. |
| **component** | One of the four parts of PenguinSlicer, each developed as its own project: the slice service, printer delivery, the wizard, the Onshape source. |
| **part, instance, plate** | A part is one distinct solid to print. An instance is one placement of a part on the plate; a part printed once has one instance. The plate is the printer's bed and everything on it. |
| **plate configuration** | What to slice: the parts, where each instance sits on the plate, and the chosen profiles and settings. It is a description, not work. |
| **slice service** | The component that takes a plate configuration, runs Orca and returns a sliced file. |
| **slice job** | The work of slicing one plate configuration in the slice service, from its arrival to its end. The plate configuration is the description; the slice job is the work on it. |
| **slice service process** | One running slice service: one process, which holds its slice jobs in its memory. |
| **HTTP interface** | The slice service's web routes, its one interface: submit a plate configuration, follow the slice job's progress, cancel it, fetch the sliced file, fetch its summary. |
| **reference plates** | The plates the team must be able to print, which decide what "big enough" means for the slice service and its host (section 4.1). |
| **printer delivery** | The component that sends a sliced file to a printer and reports how the print goes. It has two halves, the relay and the daemon. |
| **relay** | The half of printer delivery that runs on the server. |
| **daemon** | The half of printer delivery that runs on the daemon's computer and talks to the printer on the local network. |
| **the daemon's computer** | The computer next to the printer, on the printer's network, that runs the daemon. For the session at the real printer it is the owner's Windows computer on that network. |
| **daemon telemetry** | Messages the daemon sends about its own state to the server, where they are kept. Not yet designed or built. |
| **caller** | The application that uses a component: for the relay, the web application that hands it a sliced file and shows its progress to a student. |
| **wizard** | The step-by-step user interface (Setup step, Parts step, Layout step, Preview step), designed for Onshape's right panel, about 320 px wide. |
| **advanced mode** | The wizard's view that shows every slicing setting. |
| **Onshape source** | The component that turns a selection in Onshape into the parts to print. Not started. |
| **mockup** | A click-through imitation of the wizard that runs in the browser with nothing real behind it. It has had three **mockup versions**. |
| **scenario strip** | The yellow bar of controls above the mockup. It is not part of the product. |
| **wizard research** | The study made in this session of how Orca lays out and previews parts, what Onshape allows a panel to show, and how parts can be oriented and arranged in the browser (section 3.5). |
| **resting position** | One way an instance can lie on the plate, with one flat outside face down. |
| **sliced file** | The `.gcode.3mf` file Orca writes, which the printer runs. |
| **error report** | The one shape in which every component reports a failure: a stable code, what happened, where, what to do, and the underlying detail for the log. |
| **progress report** | The one shape in which every component reports how far a long job has got. A progress report is **stale** when the daemon or the printer has not been heard from for a stated time; it then carries a marker and the age of the last word. |
| **memory estimate** | The slice service's rough prediction of the memory a plate configuration needs, from the volume of its parts. |
| **watchdog stop** | The slice service's memory watchdog stopping Orca because Orca's measured memory passed the ceiling. |
| **delivery job** | One sliced file on its way to one printer, from the send until the print ends. |
| **start command** | The message the daemon sends the printer to begin printing an uploaded file. |
| **start note** | The daemon's note of a start command: the file `start.json` in the daemon's folder, written before the command is sent and kept until its outcome is known. |
| **status document** | One message of the printer's own report of its state. It may carry every field or only the fields that changed. |
| **main state** | The field of a status document that says whether a print is going on (`gcode_state`: for example `IDLE`, `RUNNING`, `PAUSE`, `FINISH`, `FAILED`). |
| **picture** | What the daemon knows of the printer's state, built from status documents. It is **whole** when it includes the printer's main state, and **fresh** when its last status document is at most 15 seconds old. |
| **hold** | The daemon's refusal to send any other start command to a printer until evidence settles what became of the last one. |
| **recording** | A file of status documents saved from the real printer by the daemon's `record` command. |
| **simulated printer** | A program that answers the daemon as an H2S would, over real network connections, from scripted status documents. |
| **upstream** | Open-source code written by others that a component rests on: Orca for the slice service, the `bambulabs_api` library for the daemon. |
| **upstream check** | A component's suite of tests that pins every behaviour of its upstream code the component relies on (`make test-upstream`); the upgrade command runs it. |
| **port** | Bringing code and tests from the print branch into PenguinSlicer without changing behaviour. |
| **hardening** | Making a ported component robust: errors, progress, cancellation, cleanup, logs, and a routine way to take new upstream versions. |
| **phase** | Either the port or the hardening of one component. |
| **first build** | The ports and the hardening of Thu 11-19 and the night after (sections 3.3 and 3.4), merged into `main` by pull request 1. |
| **review-feedback run** | The work of Fri 11-20 that applied the owner's feedback on this file to the components and the documents (section 3.6). |
| **fast suite** | A component's everyday tests: no real Orca, no real printer, no real waiting. |
| **property test** | A test that runs many randomly generated sequences and checks that a rule holds in every one. |
| **brief** | The written instructions given to an agent for one piece of work. |
| **builder** | An agent that wrote or changed a component. |
| **review round** | One check of a component by a fresh reviewer that never sees the builder's own account: it reruns the tests many times in random order, breaks the code on purpose to see whether tests notice, and tries hostile inputs. |
| **fix round** | A builder's work on the defects one review round found. |
| **defect** | Something a review round found that can mislead a user, lose work, hang, leak, fail now and then, or hide a failure. |
| **open item** | A defect not yet fixed, or a known gap that is not a defect. Reviewers graded open items **serious** (can lose work or start a print wrongly), **medium** (blocks or misleads a user until someone intervenes) or **low** (rare, small, or visible only to a developer). |
| **coordinator** | The main Claude session, which planned, wrote the briefs, made rulings and committed. |
| **ruling** | A decision the coordinator made where the owner had not decided. |
| **ledger** | The coordinator's running account of every dispatch, return and ruling. |
| **guide** | A component's `README.md` in the repository. |

## 2. What needs you

Numbered so each can be answered by its number. Within each group the order has no
meaning.

### 2.1 Decisions

No decision is open. What was settled is stated as the present state in the section it
concerns.

### 2.2 Rulings made on your behalf: confirm or reverse each

| # | Ruling | The alternative |
|---|---|---|
| R1 | **Slice service: a memory watchdog replaces refusing plates on the memory estimate.** The memory estimate refused one 100 mm solid cube as "about 1,158 MB" when it slices at a peak of 276 MB. Now the slice service watches the running Orca's memory and stops it past a ceiling (a setting, 900 MB by default) with a truthful out-of-memory error report. The memory estimate is only logged. | Refuse before slicing on the memory estimate. That is cheaper for an oversized plate but wrong for many ordinary ones until the estimate is refitted on real plates. |
| R2 | **A complete, valid sliced file is never discarded by a stop the slice service itself decides on** (a timeout or a watchdog stop), even if the stop landed in the instant before Orca exited. The slice job succeeds with the stop noted. Near the ceiling a slice may therefore be stopped or delivered with a note, depending on timing; it is never silent. | Treat the ceiling and the timeout as hard: discard a finished file whose slice touched them. |
| R3 | **A cancel always discards the file, even if Orca happened to finish**: a cancel the caller asked for, and the cancel of a slice job that every client following it has left. The HTTP interface is the only way to slice, so this holds everywhere. | Deliver a file that finished in the instant of the cancel. |
| R4 | **There is no patch to Orca.** Orca's reason for a failed slice is read from the result file Orca writes and, for its general failure, from its debug log; the upstream check verifies that reading at every upgrade. A patch to Orca is always the owner's decision, and the upgrade command stops when a patch file exists, since applying one needs a source build. Patches to the Python printer library may be made by an agent; none was needed. | Build Orca from source as part of the upgrade command. |
| R5 | **Printer delivery: only evidence that the print has ended ends a delivery job.** Silence never does, except under R7. A pause, a clearable error, an open door or run-out filament gives a non-final stage, "waiting for a person", and the delivery job returns to printing on resume. | End a delivery job after a time without word. That reported running prints as failed. |
| R6 | **The printer's main state decides whether a print is going on**; its stage code only describes it. A main state the daemon does not know refuses a new send with its own retryable error report and never locks a caller in. | Guess from the stage code. That made an idle printer read as printing and blocked every send. |
| R7 | **"Outcome unknown".** After a print has started, a caller may stop following a delivery job whose progress report has gone stale, and the relay does the same by itself after 24 hours of continuous staleness. The delivery job ends with an error report that says contact was lost, the print may still be running or may have finished, check the printer. It never says the print failed. | No time rule at all: a printer switched off for good then leaves a delivery job that is kept for ever. The 24 hours is a choice and one setting. |
| R8 | **A printer whose last print ended, well or badly, is free for a new send.** | Refuse sends until the printer's screen is cleared. Whether the H2S needs that is on the checklist in section 2.4. |
| R9 | **A start command is sent only on a whole, fresh picture that positively says the printer is free.** Without one the daemon asks the printer for a whole status document and waits, and a cancel still works. | Start on the last known state. That allowed a second file to start while a first was printing. |
| R10 | **After a start command the daemon holds the printer** until evidence settles the first start. A printer slow to show the print gives a non-final stage, "has the file and has not shown the print yet". The time limits are named settings, all guesses until the H2S is timed (section 2.4). | A fixed 60-second failure, which the port had. |
| R11 | **Every final progress report is kept 24 hours**, so a caller that polls slowly still learns how a delivery job ended. | Drop it sooner. |
| R12 | **A relay restart keeps nothing but its secret key.** An in-flight delivery job is not resumed: every party ends in a defined state and the caller gets an error report. This was the builder's choice, accepted by the coordinator. | Store delivery jobs on disk so a restarted relay resumes them. |
| R13 | **The HTTP interface is the slice service's one interface** (submit a plate configuration, follow its progress, cancel, fetch the sliced file, fetch its summary). There is no command for slicing by hand: for testing and development an agent writes throwaway scripts against the routes. The `serve` command starts the service. One interface per component is the default, not a hard rule. | A Python function and a command line as well, as the plan first said. |
| R14 | **The simulated printer's status sequences are invented** from the one status document recorded on Fri 10-09, and the daemon has a `record` command to capture real ones. | Wait for recordings before building it. |
| R15 | **The print branch's "local mode" was not ported.** In PenguinSlicer, using the tool without Onshape is to be the wizard's own file upload; until the wizard exists, each component is exercised through its interface with the example files in `contracts/`. | Port the stand-in Onshape page as well. |
| R16 | **The timed rule after a start command stays as built** (section 4.2), and the session at the real printer (section 2.4) measures what the H2S does; open items P1 and P2 are settled by those measurements. | Change the rule before the H2S has been measured. |
| R17 | **The reference plates for the night's measurements were the set proposed in the restart notes:** (1) a typical FRC mechanism plate of several different functional parts; (2) a full plate of small instances; (3) one large organic part; (4) a plate of two or three large organic parts; (5) one of these with supports on. The reference plates now add a sixth (section 4.1). | Wait for the owner to name real plates. |
| R18 | **An end counts only as an end of this print.** An end state left over from the previous print, seen just after a start command, means "not showing our print yet"; and a daemon that restarts after a real end must still find it. | Take any end the printer shows after a start command as this print's end. |

### 2.3 The mockup

> **Superseded on Fri 11-20 at about 19:00 PT by mockup version 4**, built from the
> owner's feedback of Sat 2026-11-21: PenguinCAM's light look, a fifth step (Send), the
> printer-status icon, busy-printer and resume states, and part-arrival failures as
> notifications. Its design, the questions still open (M1 to M7, M11, M16, and M17 to
> M24) and what it needs from printer delivery are in its
> [DECISIONS.md](../mockups/print-wizard/DECISIONS.md), which replaces the rest of this
> section for review.

**Open it:** [mockups/print-wizard/index.html](../mockups/print-wizard/index.html). In
the owner's Markdown viewer that link opens the working page
(`http://127.0.0.1:6249/penguin-slicer/docs/mockups/print-wizard/index.html`); from a
session, `open /repos/popcornpenguins/penguin-slicer/docs/mockups/print-wizard/index.html`
does the same. No server needs starting beyond the viewer. Its companion,
[DECISIONS.md](../mockups/print-wizard/DECISIONS.md), lists every design choice and
everything that is faked; its questions are copied below.

**How it works.** The dark panel on the right is the wizard; go through it with Next. On
the Parts step, click parts in the list or the picture on the left, as in Onshape. The
scenario strip arms errors, changes the panel width, switches between a Part Studio, an
Assembly and a standalone page, sets the speed of the mocked progress, and, new in mockup
version 3, switches three sets of options. Nothing is real: no slicing, no Onshape, no
printer. In the Assembly, Onshape's own word "Instances" (its list of an assembly's
instances) appears beside PenguinSlicer's instance; one Onshape instance becomes one
PenguinSlicer instance.

**What changed in mockup version 3**, from the owner's reactions of Thu 11-19:

- The Layout step has no modes. The Lay on face tool is gone.
- Parts arrive lying their best way. The Shooter Hood Rib lies flat, 8 mm tall, where it
  stood 353 mm. A selected instance offers "Put back as modelled".
- Arrange tries two ways of packing the instances and keeps the result that leaves fewer
  instances off the plate.
- Advanced mode stays in the panel as a full-height view, and lays out wider when the
  panel is wider. Onshape offers a right-panel application no dialog and no way to resize
  the panel; the wizard research checked that against Onshape's list of panel messages.

**The options to compare, by their names in the scenario strip:**

| Menu | Options |
|---|---|
| **Lay on face** | *Pictures under the view* (the wizard research's choice): a row of small pictures, one per resting position. *Arrows on the part's faces*: amber arrows on the selected instance; a click lays it on that face. *Box around the part* (the owner's idea): a box whose sides are clicked, or which is dragged, to put that side down. *Tip handle*: a second handle that steps the instance to its next resting position. A double-click on a flat face works under all four. |
| **Mouse** | *Like Onshape* (right-drag turns the view), *Like a slicer* (drag on empty plate turns it, right-drag slides it), *Top-down first* (the view starts from above). |
| **Parts arrive** | *lying their best way*, or *as modelled*. |

The options behave differently on a small blocky part and on a long thin one, so the
L Bracket and the Shooter Hood Rib make a useful pair. The agent that walked mockup
version 3 told the coordinator that *Box around the part* was the weakest of the four on
thin parts; that remark is kept only in its message, not in a file.

**The questions for mockup version 3**, copied from `DECISIONS.md`. Each can be answered
in a sentence.

| # | Question |
|---|---|
| M1 | **Lay on face: which one?** *Pictures under the view*, *Arrows on the part's faces*, *Box around the part*, or *Tip handle*? Try each on the L Bracket and on the Shooter Hood Rib: they behave differently on a small blocky part and on a long thin one. |
| M2 | **Mouse: which one?** *Like Onshape*, *Like a slicer*, or *Top-down first*? |
| M3 | **Parts arrive: lying their best way, or as modelled?** Lying their best way, the Shooter Hood Rib arrives flat and the student can put it back as modelled; as modelled, it arrives standing 353 mm tall with an error and an Auto-orient button. |
| M4 | **Advanced mode at 320 px:** do the search box, the Common / All settings switch, the tab row and the collapsing subgroups make the settings findable, or is the column still too cramped? |
| M5 | **Advanced mode when the panel is wider:** the tabs become a rail on the left once the panel is 480 px wide, and the subgroups sit in two columns once it is 700 px wide; the scenario strip's 560 px and 760 px settings show each. Onshape offers no dialog, so a panel dragged wider is the only "bigger" there is. Is that enough? |
| M6 | **Arrange and Auto-orient stay two buttons:** Arrange decides where instances sit and keeps how each one lies; Auto-orient decides how they lie. Arrange offers to lay instances their best way only when it has checked that more would then fit. Right, or should Arrange always auto-orient first, even if that undoes a way the student chose? |
| M7 | **The status line:** the plate's state is one line above the picture, where before it was a red bar inside the picture that could cover an instance or the rotation handle. Does one line say enough, with the full sentences and their buttons below? |

**Questions from mockup version 2 that version 3 did not settle.** Version 2 asked ten.
Three are closed: how to lay an instance down and how parts arrive are now M1 and M3, and
whether a stage-by-stage bar would do if Orca gave no percentage is moot, because Orca
does report a percentage (section 3.4). The other seven still stand:

| # | Question |
|---|---|
| M8 | **Is the 3D view big enough at 320 px?** The Layout step stays at panel width and zooms to the instances. Workable, or should the Layout step fill the whole panel as advanced mode does? |
| M9 | **When a laid-down instance needs more room** it moves to the nearest free spot; if there is none, the whole plate is arranged again, which moves instances the student may have placed by hand. Acceptable, or should other instances never move unless the student presses Arrange? |
| M10 | **Confirming a send.** Send to Printer always asks once more, naming the printer, the instances, the time and the filament. Every time, or only the first time in a session? |
| M11 | **Print progress.** After a send, a card shows the stage (Sending, Heating, Leveling, Printing, Done), percent, layer of total, time left and the expected finish time, and the layer preview follows the printer. What else would a student standing at the printer want there? |
| M12 | **Stopping things.** A slice can be cancelled at any moment. A send can be cancelled until the file has arrived. A running print cannot be stopped from the panel; the card says to use the printer's screen. Do you want pause or stop from the panel? |
| M13 | **Changing the profile keeps your changes.** If a student raises infill and then picks another profile, the change stays on top of the new profile and a sentence says so. Keep the changes, or clear them when the profile changes? |
| M14 | **A repeat click on a listed part** only flashes the row and says to raise the quantity; a ↻ button on the row brings in a changed part from Onshape. Should a repeat click raise the quantity instead? |

Two things the mockup cannot show honestly and that need a requirement, not a reaction:

| # | Question |
|---|---|
| M15 | What should **Cancel slice** do while the connection to the server is lost? The mockup cancels as if it could reach the server. |
| M16 | Which of Orca's other layout tools count as needed? The mockup leaves out scale, cut, mirror and per-part settings. |

**Faked in ways that could mislead.** The toolpaths in the layer preview are generated
shapes, not G-code. Slicing stages, times and percentages are invented (the real slice
service does report Orca's own stages and percentage; the mockup does not use them). The
"overhangs" label on a resting position uses an invented threshold. Advanced mode shows
about 95 of Orca's roughly 295 process settings. The panel's drag limits (240 to 800 px)
are not Onshape's. The mockup's plate holds up to 100 instances; the slice service takes
up to 150 (section 4.1). The full list of 26 is in `DECISIONS.md`.

### 2.4 The session at the real printer

No real printer was available. Every status sequence in the simulated printer is invented
from one recorded status document. One session at the H2S, with the daemon recording,
replaces invention with fact and measures what open items P1 and P2 depend on
(section 4.2).

**How to record a print**, on the daemon's computer, a Windows computer (the same
commands work on macOS and Linux, with `python` in place of `py`):

1. Install Python 3.11 or newer from python.org; tick "Add python.exe to PATH".
2. Get the daemon's code from GitHub: `git clone https://github.com/6238/PenguinSlicer`
   (or download the repository from that page and unpack it), then, in the
   `PenguinSlicer` folder, `py -m pip install .\delivery\daemon`. Nobody has yet installed
   the daemon this way on Windows.
3. `py -m penguin_delivery_daemon pair` finds the printer (or takes its address, serial
   and access code typed in) and writes its configuration.
4. `py -m penguin_delivery_daemon record` saves every status document the printer sends,
   one JSON line each, until Ctrl-C. Run it while a print goes from start to finish, and
   again for a print stopped on the screen and one paused by hand.
5. Bring the recording files back. An agent puts them in `delivery/simulator/scenarios/`
   as that folder's README says and runs `make -C delivery test-sim`; the simulated
   printer then replays the real printer.

**What these steps do not cover.** They record prints started some other way (from the
printer's screen, or from Bambu's own slicer), which is what the simulated printer needs.
They do not measure P1 and P2. The two checklist lines that measure them concern what the
H2S reports after a start command sent by the daemon, and that needs three more things:
a relay for the daemon to talk to, the daemon's `run` command, and a sliced file to send.
None of that is worked out for the daemon's computer yet:

- `pair` with no `--backend` option points the daemon at
  `https://penguincam.popcornpenguins.com`, where no relay for it runs. A relay must be
  started somewhere the daemon can reach (the guide's "Try it on one machine" starts one
  with `uv run python -m together.relay_server`) and its address given to `pair`.
- Neither the guide nor the scenarios' README says whether `record` and `run` can be
  connected to the printer at the same time.

So the session has two parts: recording prints started at the printer, which the steps
above cover, and a daemon-started print with recording, which an agent should prepare as
a written walk and try against the simulated printer first.

Everything the daemon keeps is in one folder: `%LOCALAPPDATA%\PenguinDelivery` on Windows,
`~/.penguin-delivery` elsewhere, or the folder given with `--home`. The recordings are in
its `recordings` folder.

**Checklist for the daemon's computer (Windows).** This list is the builder's own, from its account
of the hardening; it is not in the guide and no review round checked it. Nothing here has
run on Windows.

- [ ] `py -m pip install` of the daemon works in a fresh Python 3.11 or newer.
- [ ] `py -m penguin_delivery_daemon pair` writes
      `%LOCALAPPDATA%\PenguinDelivery\config.toml` and prints the run command.
- [ ] `py -m penguin_delivery_daemon run` connects, logs "paired with the relay" and the
      idle line, and Ctrl-C stops it cleanly.
- [ ] `status` and `record --seconds 10` run.
- [ ] Discovery of the printer (UDP port 2021) under the Windows firewall: allowed, or
      the typed address path used instead.
- [ ] A delivery job whose file name holds `:` or `?` uploads under a safe name.

**Checklist for the H2S**, copied from the guide. The names in code type are fields of
the printer's status documents and settings of the daemon; the recordings answer most
lines without anyone needing to read them live.

- [ ] `record` through one whole print, one print stopped on the screen, and one paused
      by hand (step 5 above turns them into the simulated printer's scenarios).
- [ ] **Whether the H2S sets `print_error` while a print is paused** (filament run out,
      door open, paused by hand), and whether it sets it for a moment while it keeps
      printing. The daemon reads either as waiting for a person, never as an end. If the
      H2S instead goes to `FAILED` for something a person can clear, the delivery job
      ends as failed.
- [ ] **What an idle H2S reports for `stg_cur`** (255, -1, or the last print's stage) at
      power-on, after a finished print and after a stopped one, and what it reports in
      the first seconds after a start command. Any `gcode_state` it sends that the
      daemon's table does not list refuses every send and must be added to the table.
- [ ] **That the H2S accepts a start from its finished and failed states without
      anything being cleared at the printer first**, and how long `FAILED` and
      `print_error` stay after a print is stopped on the screen (ruling R8).
- [ ] Whether a paused H2S keeps sending status documents (if not, a paused print shows
      as stale after 60 seconds, `PRINTER_QUIET_SECONDS`), and what it does with a start
      command while printing.
- [ ] **The first status documents after a start command, one by one** (after a finished
      print, after a print stopped on the screen, from power-on): does `subtask_name`
      change in the same status document as `gcode_state`, or before it, and how long
      does the previous print's end stay? Do `print_error` and the error entries of the
      last print clear, and when? This decides open item P1 and sets
      `LEFTOVER_END_SECONDS` (2 minutes).
- [ ] **How long the H2S takes to show the print after the start command**, for a small
      file and for the largest the team prints. This decides open item P2 and sets
      `START_SLOW_SECONDS` (60 seconds) and `START_SETTLE_SECONDS` (5 minutes), which
      must stay well above the measured time.
- [ ] **Whether the H2S sends whole status documents or only the fields that changed**,
      what the first status document after a connection is, and how long its answer to a
      request for a whole one takes (ruling R9).
- [ ] How often an idle H2S sends status documents by itself, and that it answers a
      request for a whole one every 10 seconds (`REPORT_REQUEST_SECONDS`) for ten minutes
      (`PRINTER_WAIT_SECONDS`) without complaint.
- [ ] Unplug the printer's network between the end of the upload and the start for two
      minutes, then plug it back: the delivery job shows "waiting for the printer" and a
      cancel works.
- [ ] What the H2S reports after it is switched off mid-print and on again. If it offers
      to resume, the delivery job has already ended as failed after two minutes
      (`PRINT_VANISH_SECONDS`) of idle status documents.
- [ ] The printer's codes for a stop on the screen (assumed `0300400C`), for filament run
      out (assumed `07008011`) and for an open door (assumed `0500400E`).
- [ ] The TLS version on the upload port (990), and whether a whole file arrives. In the
      simulated printer, 11 of 12 uploads lost their end under TLS 1.3 until one option
      of the library was set; the real printer's version is unknown.
- [ ] The format of the printer's file listing lines and the size it lists for an
      uploaded file. If the lines do not match what the daemon expects, every upload is
      judged failed.
- [ ] The H2S's answer to a delete for a file it does not have. The daemon takes a `550`
      that says there is no such file as that answer and logs that the file was not on
      the printer; any other answer is logged as a warning that the removal could not be
      confirmed, with the answer.
- [ ] A print shows its stages in order, and the remaining time is in minutes.
- [ ] A cancel during the upload removes the partial file from the printer's list.

### 2.5 Facts only the real Onshape panel can settle

Nothing in this session ran inside Onshape. These came out of the wizard research.

| # | Fact | How to settle it |
|---|---|---|
| F1 | How wide Onshape lets a user drag the right panel. PenguinCAM's own CNC help says to widen the panel, so a student probably can; Onshape publishes no limits. | Drag it in a real Part Studio and note the widths. |
| F2 | Whether the browser's full-screen request works from inside the panel. | One line in the real panel: `document.fullscreenEnabled`. |
| F3 | Onshape's default mouse mapping (taken from its documentation as right-drag turns the view), and its trackpad and touch gestures. | Try it in a real Part Studio. |
| F4 | What printing needs from Onshape beyond what the CNC wizard does in production: selecting whole bodies, exporting an STL file, picking parts inside an assembly. The print branch has that code; it has never run against real Onshape. | Checked by hand when the Onshape source is taken up. |
| F5 | The speed of automatic orientation and of Arrange in Chrome inside Onshape, on real team parts. Measured so far only on the mockup's generated parts: 0 to 12 ms per part to orient, about 1.5 s to arrange 23 instances. | Measured when the wizard is built. |

## 3. What was done, in order

### 3.1 The replanning conversation (Thu 11-19, late afternoon to about 18:00 PT)

The owner opened by saying the project had been built before its requirements were
understood. The print branch had grown to 412 changed files (about 9,000 lines of program
code, 6,000 of tests, the rest mostly Orca's profile data). The conversation settled:

- The work leaves PenguinCAM for one new repository, never several, built on PenguinCAM's
  stack so it can return later.
- Four components, each developed as its own project.
- The wizard keeps the CNC wizard's conventions and the Onshape panel as its main home.
  The first attempt's fault was missing capabilities, not the wizard's shape.
- Onshape integration is a solved problem (the CNC wizard does it in production) and is
  not treated as a risk.
- Planned work stops at three things: port and harden the slice service, port and harden
  printer delivery, build a wizard mockup. Planning resumes after those.
- The standing quality bar: fast tests that never fail at random, real coverage, and
  errors that say what happened and what to do. An Opus agent builds; a fresh Fable
  reviewer checks; at most four review rounds per phase.

The plan was written up, reviewed twice and committed:
[PenguinSlicer restart plan](../plans/2026-11-19-penguin-slicer-restart-plan.md). It is
kept to the present state, as this file is.

### 3.2 The repository

PenguinSlicer is https://github.com/6238/PenguinSlicer, public. Every change reaches
`main` through a pull request from a branch.

```mermaid
flowchart TB
    on["onshape/<br/>not started"] -->|"parts"| wz["wizard/<br/>mockup only"]
    wz -->|"plate configuration"| sl["slice/<br/>slice service"]
    sl -->|"sliced file"| de["delivery/<br/>printer delivery"]
    sl -.->|"error and<br/>progress reports"| wz
    de -.->|"error and<br/>progress reports"| wz
```

Each component has its own folder, tests and guide, runs without the others, and depends
only on the shapes defined in `contracts/` (the plate configuration, the sliced file, the
error report, the progress report). In production the components may run inside one
server; the files in `contracts/` are seams for development and testing.

### 3.3 The ports (Thu 11-19, about 17:30 to 18:40 PT)

Each service was brought over from the print branch by an Opus agent, cut free of
PenguinCAM, and had two review rounds. Faults inherited from the print branch were pinned
by tests for hardening to fix.

| Service | Review round | Defects | The worst |
|---|---|---|---|
| Slice service | 1 | 14 | A good sliced file thrown away when Orca's result file had an unexpected shape |
| Slice service | 2 | 2 | A crash of Orca reported as a kill |
| Printer delivery | 1 | 12 | An accepted send could lose its sliced file to a race the port introduced (3 of 150 sends) |
| Printer delivery | 2 | 1 | A test that failed if a stray system file sat in the daemon's folder |

### 3.4 Hardening (Thu 11-19 18:30 PT to Fri 11-20 02:21 PT)

The owner named the cases that mattered: bad STL files (a broken model once failed every
slice with a useless message), an empty file, out of memory; and for printer delivery,
networks that are slow, intermittent, or "seem down and then recover", on both links, and
the printer's own error codes. The owner also added that taking a new version of upstream
code must be routine, and that small patches to upstream are acceptable for error and
progress reporting only.

The cap was four review rounds per phase. The slice service used four. Printer delivery
used four, and then, at about 23:20 PT on Thu 11-19, the owner asked for two more "to see
if we can get to low issues only"; those are rounds 5 and 6.

| Service | Review round | Defects | The worst |
|---|---|---|---|
| Slice service | 1 | 14 | One test failed 1 run in 20; the memory estimate refused plates that fit |
| Slice service | 2 | 6 | The memory watchdog missed Orca's peak, a spike shorter than a tenth of a second |
| Slice service | 3 | 7 | A stop landing just after Orca wrote its file discarded the file (rare) |
| Slice service | 4 | 6, all low | Fit to commit; nothing that loses a student's work |
| Printer delivery | 1 | 11 | A print that was running was reported as failed after 90 seconds of printer silence, and never corrected |
| Printer delivery | 2 | 6 | A fault a person clears at the printer ended the delivery job as failed while the print finished |
| Printer delivery | 3 | 8 | An unknown printer value blocked every send for ever; two different files could overlap |
| Printer delivery | 4 | 6 | A start command could go out on a partial status document from a busy printer |
| Printer delivery | 5 | 7, all low | Low only on a condition the real printer must confirm (P1 and P2) |
| Printer delivery | 6 | 7, all low | The same condition; the fast suite had grown slow; one fix had no test |

Two findings from hardening that change earlier assumptions:

- **Orca reports real progress.** Its `--pipe` option sends one message per stage with
  its own percentage. The slice service reports those and never invents a figure. The
  restart notes had left open whether Orca, run with no window, reports its stages at
  all; it does.
- **The simulated printer found two faults that fakes could not:** a deadlock in the
  daemon's handling of the printer library's log, which would have hung the printer
  connection on the library's second log line, and uploads losing their end under
  TLS 1.3. Both are fixed.

### 3.5 The mockup and the wizard research

- **Mockup version 1** (Thu 11-19, 17:15 to 17:50 PT): an Opus agent built the whole
  wizard as a click-through page.
- **Mockup version 2** (to Thu 11-19 18:26 PT): two passes by Fable agents improved it;
  the owner tried it late on Thu 11-19.
- **The wizard research** (Thu 11-19 23:23 to 23:36 PT): an Opus agent studied Orca's
  source at version 2.4.2, Onshape's developer documentation and options for laying out
  parts in the browser. Its file:
  [wizard layout and advanced mode research](../research/2026-11-19-wizard-layout-and-advanced-mode-research.md).
  Its conclusions are in section 2.3. It did not run Orca's window. It found that Orca,
  Cura, PrusaSlicer and Bambu Studio all use a mode for laying a part on a face. Orca's
  code for orienting and arranging cannot be taken over: Orca is AGPL-licensed and
  PenguinCAM is MIT-licensed, so the mockup's versions are written fresh.
- **Mockup version 3** (Thu 11-19 23:36 PT to Fri 11-20 00:34 PT): an Opus agent applied
  the wizard research, and one pass by a Fable agent walked and corrected it.

### 3.6 The review-feedback run (Fri 11-20, morning)

The owner read the terms and sections 2.1, 3 and 4.1 of this file, gave feedback, and
asked for it to be applied. Pull request 1 merged the first build into `main` (Fri 11-20
09:13 PT); pull request 2 moved the plan, the wizard research, the mockup, the first
build's ledger, briefs and result files and this file into the repository's `docs/`
(09:31 PT); pull request 3 brought the mockup's new terms and the briefs of this run
(09:44 PT). Three Opus builders worked on the branch `work/review-feedback`, from
09:32 PT: the slice service, printer delivery, and the mockup's terms. The mockup's change
was terms only, walked in a browser with no console errors, and not sent to a reviewer.

| Component | Review round | Defects | The worst |
|---|---|---|---|
| Slice service | 1 | 1 medium, 3 low | The debug-log reading could name a sound part's warning as the reason another part failed |
| Slice service | 2 | 1 medium, 2 low | A cancel during the writing of a large plate was acted on only when the write ended (21.7 s) |
| Slice service | 3 | 2 low; fit to merge | No test with the real Orca holds a plate of several different parts to its placements |
| Printer delivery | 1 | 2 medium, 3 low | A file listing the daemon could not read was taken as proof that a file was not on the printer |
| Printer delivery | 2 | 4 low | A file the daemon uploaded could be left on the printer while its log said it was not there |
| Printer delivery | 3 | 2 low; fit to merge | The warning for a delete the printer never answered said "it answered" |

Rounds 1 and 2 were each followed by a fix round that reports every defect fixed. The
third review rounds, planned on Fable, stopped on Fable's usage limit at about 11:20 PT on
Fri 11-20; at the owner's word they were dispatched again on Opus at 11:46 PT and returned
by about 12:00 PT. Both third fix rounds report their defects fixed; the slice service's
also found and fixed a timer race in the Orca runner that failed one repeat run in 20.
The coordinator reran both fast suites, then merged the slice service (pull request 4)
and printer delivery (pull request 5) at about 12:35 PT. Sections 4.1 and 4.2 give the
figures of the third review rounds, and figures that come only from a fix round's own
account are marked "measured by the builder".

## 4. State of each component

### 4.1 Slice service

The slice service as it stands on `main` after pull request 4.

**What it does.** Its one interface is its HTTP interface. It takes a plate configuration
(the plate configuration as JSON and one STL file per part), checks every part before Orca
runs, slices with Orca 2.4.2, and returns the sliced file from one route and its summary,
as JSON, from another. Every failure is an error report that keeps Orca's own reason, read
from the result file Orca writes and, when Orca gives only its general failure, from
Orca's debug log. It reports Orca's stages and percentage as progress. A cancel, a timeout
or a watchdog stop leaves no Orca process and no files, and a cancel is acted on at once
also while the slice service writes the plate's model file, before Orca starts. A cancel
always discards the file (ruling R3). It writes one log line per change of a slice job's
state. One slice service process holds its slice jobs in its memory; several may run, on
one machine or several, and a client keeps talking to the slice service process that
accepted its slice job.

**Run it** (from the repository's top folder):

```
make -C slice install
make -C slice test
make -C slice test-upstream
uv run --project slice python -m penguin_slice serve --work /var/tmp/penguin-slice --port 8640
```

Then, as the guide's "Use" shows, submit the example plate configuration with `curl`:

```
curl -s -F 'plate_configuration=<contracts/examples/plate-configuration.json' \
     -F bracket.stl=@contracts/examples/parts/bracket.stl \
     -F spacer.stl=@contracts/examples/parts/spacer.stl \
     http://127.0.0.1:8640/slices
curl -sN http://127.0.0.1:8640/slices/<job>/events
curl -s  http://127.0.0.1:8640/slices/<job>/summary
curl -s -OJ http://127.0.0.1:8640/slices/<job>/file
```

`make test` is the fast suite. `make test-upstream` is the upstream check: it runs the
real Orca and also verifies that Orca's reason for a failed slice is still found in its
debug log. `make upgrade-orca VERSION=x.y.z` moves to another Orca version and runs the
upstream check; a failing test there names what to fix. The slice service stays on
Orca 2.4.2: Orca 2.5.x packs the Bambu Lab profiles in one file (`BBL.opc`) that the
script building the profile catalog cannot read yet, so taking 2.5.x is known future work
(section 7).

**The reference plates and the plate limits.** The reference plates are the five of
ruling R17 and a sixth: 100 instances of a small spacer for a 3/8 inch hex shaft, 1/8 inch
thick, round outside and 5/8 inch across, in a 10 by 10 grid. A plate may hold up to 150
instances (`MAX_INSTANCES`) of up to 25 different parts (`MAX_PARTS`). The builder set 150
from these measurements, one slice at a time with the default profiles, on an aarch64
Linux machine with 4 CPUs:

| Spacers | Slices | Peak (MB) | Orca's time (s) | Sliced file (MB) |
|---|---|---|---|---|
| 100 | 6 | 488 to 513 | 6.2 to 7.1 | 1.81 to 1.82 |
| 150 | 2 | 643 to 649 | 9.4 | 2.72 |
| 196 | 2 | 815 to 829 | 12.5 to 12.6 | 3.55 |

So the plate a team needs (100) peaks near half the 900 MB ceiling, 150 leaves more than a
quarter of it free, and 196 comes within 8 % of it. The reviewers measured 100 spacers at
504 to 526 MB and 150 at 651 MB. `MAX_PARTS` bounds the upload (188.5 MB) and is not a
measured limit. There is no limit on the triangles of the whole plate: the memory
watchdog decides, and in the first review round it stopped 100 instances of a detailed
16 mm knob at 922 MB with an out-of-memory error report. Instances of larger or more
detailed parts reach the ceiling sooner.

**Figures from the third review round of the review-feedback run** (the working tree of
`work/review-feedback` after the second fix round; another agent ran suites on the same
machine, so only the first runs of the fast suite are from a quiet machine):

| What was measured | Result |
|---|---|
| Fast suite, 20 runs in random order on 2 worker processes | 20 of 20 passed; 919 tests; 4.1 to 4.8 seconds a run on a quiet machine, 6.0 to 7.9 under load |
| Branch coverage of the package under the fast suite | 100% |
| Tests that run the real Orca, one Orca at a time | 35 passed in 33.1 seconds; no Orca left behind |
| Changes undone on purpose by the reviewers | 7 of 7 noticed by the tests in the second review round (and 14 of 15 in the first; the one missed now has its test); in the third, undoing the fix for a cancel during the write made 4 to 9 tests fail |
| 100 spacers through the real Orca | peak 509 MB, 6.2 seconds, a 1.81 MB sliced file |
| A plate of 9 instances of three different parts, through the real Orca | every instance where it was placed, to within 0.054 mm |
| A cancel during the plate write of the largest plate accepted | `cancelled` 0.03 to 0.20 seconds after the cancel, at any point of the write; Orca never started; the slice job's folder empty (21.7 seconds in the second review round, before the fix) |
| An abandoned slice job, and a shutdown, during the write | each ended with Orca never started and the folder empty |

The slice service writes the plate's model file one part at a time, so a freshly started
slice service process peaked at 216 to 233 MB of its own memory for the largest plate
accepted (150 instances over 25 detailed parts; 438 MB before the change). Over many
plates in a row its memory used to climb, to 360 MB after thirteen: each request and
slice job runs on its own thread, and the C library kept a memory pool per thread. The
`serve` command now limits those pools to two, and the same sixteen plates peaked at
199 MB on the first and 261 MB on the sixteenth (measured by the builder). About 4 MB a
plate of growth remains, cause not found, so the guide sizes a host for 400 MB of the
slice service beside Orca's ceiling: 1.3 GB with the default 900 MB ceiling.

**The debug-log reading.** When Orca fails with only "The slicer could not slice this
plate", the warnings Orca reported while slicing are in its debug log and nowhere else.
The log cannot say which warning, if any, is why the slice failed, so the sentence keeps
the general failure and adds every warning found, labelled as possibly unrelated: "The
slicer could not slice this plate. It also warned, though this may not be why it failed:
It seems object Block #1 has floating regions. Please re-orient the object or enable
support generation." The upstream check slices that block (20 by 20 by 5 mm on a stem
0.4 mm across) and fails when the warning is no longer found.

**Memory of the eight synthetic plates, measured by the builder in hardening and not
repeated by a reviewer.** One slice at a time, default profiles: the highest peak was
915 MB, for three large smooth bodies with supports on (1,398 cm³ in all). A plate of 25
small hubs peaked at 781 MB. One 100 mm solid cube peaked at 276 MB. These were measured
under a 3 GB stop rule, before the watchdog existed. The 915 MB plate is above the default
ceiling of 900 MB, so by rulings R1 and R2 the slice service would now stop it as out of
memory, or deliver it with a note if Orca finished first; that plate was not run again at
the default ceiling. No real team plate was measured, nor CPU time, nor how many slices
can run at once.

**Open now.** The small open items of the hardening are fixed, or gone with the command
for slicing by hand. The third review round's two low defects are fixed: a real-Orca
test, which the upgrade command runs, now holds a plate of three different parts,
interleaved and at four orientations, to its placements within 0.25 mm; and the guide's
host sizing is measured (above). Two known gaps remain, neither of which can lose a student's work:

| # | What | To a user | How likely | The fix |
|---|---|---|---|---|
| S7 | Orca 2.5.x cannot be taken yet: the script that builds the profile catalog cannot read the packed `BBL.opc`. | None now. | Certain at the next upgrade. | Known future work (section 7); size unknown until the format is examined. |
| S9 | A thin, tall part (a needle 0.3 mm across and 300 mm tall) fails with only "The slicer could not slice this plate." Orca 2.4.2 raises the real reason ("One object has an empty first layer and can't be printed"), collects it and loses it: neither its result file nor its debug log holds it, even at the debug log's level 5 (`--debug 5`). | A general sentence where Orca knew the reason. | Occasional, with unusual parts. | None without a patch to Orca, and there is no patch to Orca (ruling R4). |

Also known and stated in the guide: parts that intersect themselves are not detected
before slicing; the expected slicing time is only within about a factor of two (five
times too high for the 100 spacers); the peak memory in the log can be under Orca's true
peak for an Orca that fails between two of the watchdog's samples. Not measured: the disk
held by finished slice jobs, which keep their uploads and sliced file for an hour.

### 4.2 Printer delivery

**What it does.** A caller gives the relay a sliced file for a team's printer. The daemon
fetches it, uploads it to the printer, and starts it under rulings R9 and R10. The caller
follows a stream of progress reports through the whole delivery: waiting, downloading,
uploading, starting, then the print with its stage, percent, layer and minutes remaining,
marked stale when the daemon or printer has gone quiet. Both faults of the first hardware
test (Fri 10-09) are fixed: the start check reads the field the H2S actually fills, and
an upload is judged by the size the printer lists for the file. The daemon is a plain
Python program started by hand on Windows, macOS or Linux, with no installer, no service
setup and no operating-system protection of its stored secrets. It stays in Python for
now and moves to Rust or Go later. The daemon accepts any certificate the printer
presents.

**Run it** (from the repository's top folder):

```
make -C delivery install
make -C delivery test
make -C delivery test-properties
make -C delivery test-sim
make -C delivery test-upstream
make -C delivery together
```

`make test` is the fast suite. `make test-properties` runs the three property tests,
before a commit and in every review round. `make test-sim` runs the daemon against the
simulated printer. `make test-upstream` checks the assumptions about the printer library.
`make together` sends a sample file through relay and daemon in one process. The guide's
section "Try it on one machine" walks the whole chain by hand with the simulated printer
in four terminals. `make upgrade-printer-library` moves to another library version.

**The timed rule after a start command.** After a start command, if 5 minutes
(`START_SETTLE_SECONDS`) of whole, fresh pictures pass with no print shown, the printer is
taken not to have started the file and is free again (open item P2). A daemon that could
not watch the start, because it restarted or lost the printer, takes an end shown by the
printer as this print's end once the command is 5 minutes old (open item P1). Each answer
is wrong only if the H2S is slower than that to show a print, or keeps showing the
previous print's end under the new file's name for that long; then the delivery job gets a
wrong final answer and a resend sends a second start command. The session at the real
printer measures both (section 2.4). In the hardening's last review round, 109 of 4,300
random sequences of faults ended with a wrong final answer, every one of them P1 on a
simulated printer that kept the previous end under the new name; none sent a file's start
command twice.

**Daemon telemetry** is part of the initial work on printer delivery and is not yet
designed or built: a protocol by which the daemon sends messages about its own state back
to the server, where they are kept. It matters because the daemon runs on many kinds of
hardware and its problems are hard to foresee: a misconfigured network, what the daemon's
computer can do, problems with the user interface, the daemon's computer going to sleep or
being overloaded, and the daemon timing out because its computer runs slowly.
It helps development now, and the protocol is designed to be ported when the daemon moves
to Rust or Go. Today both halves write structured log lines only.

### Outcome of the last round

The review-feedback run (section 3.6) fixed the small open items of the hardening and made
the changes that follow from the owner's decisions: one builder's work, then three review
rounds and three fix rounds. The third review round judged the change fit to merge.

- **Fixed and confirmed by a review round:** the hold's timing after a restart has its
  test. A property test that fails no longer spends minutes reducing its example, so a
  real bug fails the property tests within about a minute. The three property tests run
  in their own make target, so the fast suite is back to about 4 seconds on two workers;
  it keeps eight sequences written out by hand for nine known faults, and two of those
  faults only the written-out sequences catch, as the guide says. A damaged or out-of-date
  start note gives way to the relay's word on the last start granted, with no 5-minute
  wait and the printer still held. Time when nobody watches the hold is not counted, as
  the guide says, and a slow answer from the relay does not stop the count. Several
  Ctrl-C at once end the daemon's log quietly. The Raspberry Pi installer is removed, with
  the relay's installer route and the daemon's hand-over to an installed service.
  Removing a cancelled file from the printer always sends the delete, and the log line
  follows the printer's own answer: "removed", "was not on the printer", or a warning
  that the removal could not be confirmed, with the answer; no delete is ever sent after
  a start command. The guide's walk names the stages a short print really shows.
- **Fixed in the third fix round, measured by the builder:** the warning says "it
  answered" only for an answer from the printer, and otherwise says what happened ("no
  answer: timed out", "the connection dropped"). The computer the daemon runs on has one
  name in the code and the guide, "the daemon's computer", defined once as the computer
  next to the printer. The guide's "Two limits that wait for the real printer" says the
  timed rule stays as built.
- **Left as they are, by ruling R16:** P1 and P2. The guide states both limits in a
  subsection, "Two limits that wait for the real printer".

**Figures from the third review round of the review-feedback run** (the working tree of
`work/review-feedback` after the second fix round, with another agent using the machine,
so no timing is from a quiet machine; the second review round's quiet runs took 3.58 to
3.72 seconds):

| What was measured | Result |
|---|---|
| Fast suite, 20 runs in random order on 2 worker processes | 20 of 20 passed; 1,120 tests and 168 subtests; 4.42 to 9.52 seconds a run at a load of 1.9 to 3.2 |
| Fast suite on one worker, as `make test` runs it | 5.91 seconds at a load of 1.3 |
| Property tests (`make test-properties`) | 3 passed; 5.68 seconds |
| Simulated-printer suite | 37 passed; 18 seconds |
| Check of assumptions about the printer library | 57 passed; 17 seconds |
| `make test-repeat` (ten runs in a row), in the second review round | 10 of 10 passed; 63 seconds |
| Branch coverage | Not fallen: `run_loop.py` 99%, `printer.py` 97%, `start_record.py` 96%, the relay's modules 98% to 100% |
| Faults put back into the code on purpose by the reviewer | 5 of 5 noticed by the fast suite (13 of 13 in the second review round) |
| A cancel at each moment of a delivery job, 16 cases on a fake clock | The same outcome, word for word, as the code on `main`; no delete ever sent after a start command |
| The hold's count with a slow or failing relay, 35 cases on a fake clock | The same end, to the second, as the code on `main` in all 35; silence never counted |

**After the third fix round, measured by the builder:** 1,123 tests and 180 subtests,
20 of 20 random-order runs passed in 3.51 to 4.28 seconds each; property tests, 3 passed
in 5.27 seconds; the simulated-printer suite, 37 passed; the check of assumptions about
the printer library, 57 passed; branch coverage not fallen.

**Open on `main` after pull request 5.** Both on condition, as the hardening's last review
round rated them.

| # | What | To a user | How likely | The fix |
|---|---|---|---|---|
| P1 | A print can be reported as finished, or as failed, when it has not begun. The mechanism is in "The timed rule after a start command" above. | A wrong final answer, and the printer counts as free, so a resend sends a second start command. | Unlikely: it needs a daemon that could not watch and a printer holding an old end under a new name for 5 minutes, and nobody has seen an H2S do that. **Serious if the H2S does.** | A recording that rules it out (section 2.4). |
| P2 | A printer that takes more than 5 minutes to show a print it accepted is reported as not having started it. See "The timed rule after a start command" above. | A failure message for a print that is beginning; a resend sends a second start command. | Unlikely: the one recorded status document suggests seconds. **Serious if the H2S is that slow.** | A measured time and a setting well above it (section 2.4). |

Not handled, by design, and stated in the guide: stopping a print that is already running
(it must be stopped at the printer); checking the printer's certificate (the daemon
accepts any); a relay restart does not resume an in-flight delivery job (ruling R12).

### 4.3 The wizard

A mockup only (section 2.3). No product code exists. Its requirements are to be written
from the owner's answers to M1 to M16 and whatever else the owner says after trying it.

### 4.4 The Onshape source

Not started. The folder is empty. The print branch holds code for selecting parts and
exporting STL files that has never run against real Onshape (fact F4).

## 5. What went wrong or deserves a caution

**The coordinator's own mistakes**

- **Times written without reading the clock.** For about 25 minutes on Thu 11-19 (real
  time about 18:00 to 18:22 PT), the coordinator wrote times into the ledger and into
  messages that ran up to about 30 minutes ahead of the real time, including the times
  attached to three of the owner's decisions. The order of events was right. The ledger
  carries a correction, and every time after it was read from the clock.
- **Files edited through scripts.** The coordinator told every agent to edit files only
  with the editing tools, and itself changed the plan, the ledger and the briefs through
  small scripts several times.
- **A first misreading of the risks.** Early in the conversation the coordinator listed
  Onshape's messages and slicing progress as large unknowns. The owner corrected both:
  the CNC wizard already does the Onshape part in production, and the owner's point about
  progress concerned the print as well as the slice.

**Incidents**

- **Out-of-memory kills.** During the third review round of printer delivery's hardening
  (Thu 11-19, about 21:14 to 21:19 PT) the reviewer put faults back into the code that
  made tests loop for ever. Its time limit stopped the wrapper program and not the tests,
  which grew to 2.1 GB on a machine with 5 GB, and the container logged two
  out-of-memory kills. The slice review round running at the same time returned normally,
  and its figures were checked again in the next round. Every test now has a hard time
  limit from outside the test.
- **Rule lapses the agents reported themselves:** several chained shell commands with
  `cd ... &&`; two changed a line with `sed`; one made a batch of edits through a script. None
  wrote outside its folder, and none ran a git command that writes.
- **A builder went beyond its list once.** In the last fix round of the hardening the
  builder also fixed the double-counting in the hold, which changed the hold's timing. The
  final review round checked the hold again and found it sound, but that fix had no test
  until the review-feedback run added one.

**Claimed, but checked by no independent review**

- **The mockup's last two changes in version 3:** a text change in the selection row made
  after the final reload, and the "Lay them the best way" button, which never appeared on
  any plate the walking agent built. The coordinator loaded the page afterwards and saw
  it render with no console errors, nothing more.
- **The upgrade commands.** The builders ran them (Orca to 2.5.1 and to 2.4.1 and back;
  the printer library to 2.6.5 and back). The reviewers read the commands and did not run
  them, because running them rewrites files in the repository.
- **The memory measurements** of the eight synthetic plates in section 4.1 are the
  builder's.
- **The checklist for the daemon's computer** in section 2.4 is the builder's.
- **Windows.** The daemon has never run on Windows. Tests exercise each
  platform-dependent choice with the platform faked.
- **The wizard research's facts about Onshape and Orca** come from documentation and
  source code. Orca's window was not run, and nothing was tried in a real Onshape panel
  (section 2.5).
- **Mockup below 1,450 px of window width:** the scenario strip wraps to three rows.

## 6. Where everything is

| What | Where |
|---|---|
| The repository | https://github.com/6238/PenguinSlicer, public, checked out at `/repos/popcornpenguins/penguin-slicer` (the local folder keeps the name `penguin-slicer`). `main` holds pull requests 1 to 3. |
| The code changes of the review-feedback run | On `main`: [pull request 4](https://github.com/6238/PenguinSlicer/pull/4) (slice service) and [pull request 5](https://github.com/6238/PenguinSlicer/pull/5) (printer delivery) |
| The first build's commits, oldest first | `cbd912c` skeleton and the error and progress contracts; `7e1e2e1` printer delivery port; `c2c9a3c` slice service port; `30401cf` slice service hardening; `81b5f4a` printer delivery hardening; `fce698d` notes for agents; `5d38566` printer delivery, how a start is decided; `9989a12` printer delivery, the hold survives restarts. Merged into `main` by pull request 1 (`1997432`). |
| Guides | [slice/README.md](../../slice/README.md), [delivery/README.md](../../delivery/README.md), [contracts/](../../contracts/README.md), and [CLAUDE.md](../../CLAUDE.md) (commands, the quality bar, the terms and lessons learned) |
| The plan | [plans/2026-11-19-penguin-slicer-restart-plan.md](../plans/2026-11-19-penguin-slicer-restart-plan.md) |
| The review-feedback run | Its ledger, [orchestration/review-feedback/progress.md](../orchestration/review-feedback/progress.md); its briefs, starting with [the standing rules](../orchestration/review-feedback/briefs/standing-rules.md); its result files in `orchestration/review-feedback/results/`, the latest being [slice-review-3.md](../orchestration/review-feedback/results/slice-review-3.md), [delivery-review-3.md](../orchestration/review-feedback/results/delivery-review-3.md) and [delivery-fix-3.md](../orchestration/review-feedback/results/delivery-fix-3.md) |
| The first build's ledger | [orchestration/penguin-slicer/progress.md](../orchestration/penguin-slicer/progress.md) |
| The first build's briefs | [orchestration/penguin-slicer/briefs/](../orchestration/penguin-slicer/briefs/standing-rules.md): standing rules, review, fix, the two hardening briefs, upstream, wizard research |
| The first build's result files | `orchestration/penguin-slicer/results/`. The two final review rounds of the hardening: [slice-hardening-review-4.md](../orchestration/penguin-slicer/results/slice-hardening-review-4.md) and [delivery-hardening-review-6.md](../orchestration/penguin-slicer/results/delivery-hardening-review-6.md) |
| The wizard research | [research/2026-11-19-wizard-layout-and-advanced-mode-research.md](../research/2026-11-19-wizard-layout-and-advanced-mode-research.md) |
| The mockup | [mockups/print-wizard/index.html](../mockups/print-wizard/index.html) and [DECISIONS.md](../mockups/print-wizard/DECISIONS.md); in the owner's viewer, `http://127.0.0.1:6249/penguin-slicer/docs/mockups/print-wizard/index.html` |
| The first attempt | The restart notes, [handoffs/2026-10-11-print-path-restart-notes.md](https://github.com/chondl/PenguinCAM-notes/blob/main/handoffs/2026-10-11-print-path-restart-notes.md) in the notes repository, and the print branch in PenguinCAM |

The notes repository (`chondl/PenguinCAM-notes`) no longer holds PenguinSlicer's plan,
research, mockup, ledgers, briefs or result files; it keeps the restart notes and the
other notes of the first attempt. PenguinCAM itself was not changed. The owner's global
instructions were not changed. The workspace file `/repos/popcornpenguins/CLAUDE.md`
points at the plan in this repository, names `6238/PenguinSlicer` on GitHub, and allows
an agent to open and merge pull requests here; as far as the owner knows, nothing
generates it from elsewhere.

## 7. Ways forward

These are options. The order is by risk, riskiest first, as the owner's standing rule
asks; it is not a schedule and not a statement of priority.

| Option | What makes it risky |
|---|---|
| **The session at the real printer** (section 2.4) | Feasibility: everything printer delivery knows about the H2S beyond one status document is invented. The upload's TLS version, the file listing format and the first status documents after a start command can each break delivery outright, and open items P1 and P2 hang on its timings. Resources: the owner, the printer and the daemon's computer together, and a relay the daemon can reach. |
| **Writing the wizard's requirements, then building the wizard** | Feasibility: the requirements are still being discovered through the mockup; direct manipulation in 3D at 320 px is the least proven part; facts F1 to F3 are unknown. Resources: the largest piece of building left. |
| **Daemon telemetry** (section 4.2) | Feasibility: what it must report is exactly what is hard to foresee on hardware nobody controls (networks, a daemon's computer that sleeps, is overloaded or runs slowly), and the protocol must survive the daemon's move to Rust or Go. Resources: new design on both halves and on the server that keeps the messages. |
| **Joining the components and returning to PenguinCAM** | Feasibility: no two components have yet run joined; each has only been run against the example files in `contracts/`, so a mismatch between them would show first here. Resources: it needs a working wizard first. |
| **Hosting and the memory estimate** | Feasibility and resources: no real team plate has been measured; the memory estimate overestimates smooth parts about twofold; how many slices can run at once is unmeasured; the host must hold the slice service's own memory beside Orca's ceiling (the guide sizes 400 MB, since a slice service process still grows about 4 MB a plate), and each slice service process holds its own slice jobs, so the choice of host follows from these. |
| **Taking Orca 2.5.x** (open item S7) | Feasibility: the packed profile format `BBL.opc` is unexamined, so the size of the work is unknown. |
| **Moving the daemon to Rust or Go** | Resources: a rewrite of the daemon. Feasibility is lower risk: the simulated printer, the tests and the telemetry protocol are what the new daemon is checked against. |
| **The Onshape source** | Feasibility: low. The mechanism is in production in the CNC wizard; three small behaviours need confirming by hand (fact F4). |
