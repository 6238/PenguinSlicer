# Review of the wizard's guide

The guide is close but not ready for the owner: what a user sees at each step follows the
mockup's decisions faithfully, and all twelve screens the mockup never showed are designed
and listed, but the choices the writer made in designing them are stated as settled design
and gathered nowhere. The single most important thing to fix is to add, to the table
"Designed here and not in the mockup", what this guide chose for each screen that no source
states, and to put a contents list and a pointer to that table and to "What is undecided"
in the opening paragraph. After that, the requirement areas the guide leaves out (who
writes the sentences of an error, two tabs sharing one stored plate, stored work that is
not tied to a user, a progress stream that cannot be reopened, reporting the browser's own
failures to the server log) need a paragraph each.

Reviewed Fri 2026-11-27: [the guide](../../../wizard/README.md) (1,549 lines), against
[its details file](../../../wizard/README-details.md),
[the mockup's decisions](../../mockups/print-wizard/DECISIONS.md),
[the decisions of Fri 2026-11-27](decisions-2026-11-27.md),
[the comparison of the mockup with the design](../hosted-architecture/mockup-against-design.md),
[the contract](../../../contracts/wizard-front-server.md),
[the front server's guide](../../../front/README.md),
[the architecture](../../architecture.md), and, where a claim reached them,
[the slice service's guide](../../../slice/README.md) and
[printer delivery's guide](../../../delivery/README.md). Line numbers are the guide's
unless a file is named. Counts: heading 1, 23 findings; heading 2, 13; heading 3, 27;
heading 4, 8.

## 1. Can the reader decide from it?

| Question | Answer | What is missing |
|---|---|---|
| Does it do the right things for a user? | Mostly yes | How a second plate is started; uploads in millimetres while no edit screen exists; the Send step before phase 5; accessibility as a requirement |
| Is the division of work sound? | No | Who writes each sentence of a failure; what the wizard reports to the server log; three asks the contract does not hold |
| Are the approaches to the hard parts sound? | Yes for geometry and the preview | Two tabs on one stored plate; stored work not tied to a user |
| Are the limits and targets right? | Partly | No target for the Layout view's frame rate or for the page's memory; the preview's machines are not specified well enough to test |
| Is security adequate? | Partly | Stored parts shown to the next user who signs in; "until the plate expires" is not true of the storage |
| Failure, cancel, restart, deploy | Partly | A progress stream that cannot be reopened; a damaged configuration; storage that is full; the known four-minute case at a deploy |
| What is built and what is not | Yes | Nothing is built, and each phase is named in place |
| What remains undecided | Partly | Twelve of the writer's thirteen choices are not shown as choices |

Findings, most serious first.

- l.1382-1403 — "They are the ones to read hardest." — The table lists the screens and
  where they are, not what was chosen; twelve of the writer's thirteen choices (table under
  heading 3) read as settled design, and only sign-out is offered as something to change —
  add a third column, "What this guide chose, which no source states", one line a row
  (for example "a card with a button, the page does not leave for Onshape by itself";
  "Sign in again inside the group details, not on the header line"; "changing group clears
  the changes and the slice, keeps parts and layout"; "nothing is shown at a self-reload").
- l.1-11 — the opening — The table of new screens is at l.1382 and the undecided items at
  l.1417, with no contents list and no pointer, so the owner cannot find them without
  reading 1,380 lines — add a contents list after l.11 and the sentence "The screens nobody
  has seen drawn are listed under [Designed here and not in the mockup], and what is not
  settled under [What is undecided or unmeasured]; read those two first."
- l.32-33 and l.1179-1180 — "Every sentence a user reads." against "whose sentences for
  the user the wizard shows as they are" — The guide never says which quoted sentences are
  the wizard's and which arrive in an error report. The slice failures at l.642-646 cannot
  be the slice service's as they stand (they change with "Onshape" or "your CAD program",
  with the count of instances, and carry the wizard's buttons), and the slice service's
  own sentence for out of memory differs (slice/README.md l.832: "for a single instance,
  split or simplify the part") — add a paragraph to "What the wizard asks of the front
  server": for each kind of failure, whether the wizard shows the error report's sentence
  or writes its own from the report's code and fields, and which component is changed
  when a sentence is wrong.
- l.627-633 and l.1238-1242 — "started in another tab or in a tab beside Onshape's
  panel" — Two tabs at one address share one browser's storage (l.68-69), so they share
  one stored plate and overwrite each other's parts, layout and settings; the guide
  designs only the slices cancelling each other — say what a second tab does (proposed:
  it reads the stored plate when it opens and when it regains focus, and the last change
  wins; or the second tab says the plate is open in another tab), and list it as
  undecided.
- l.254-257 and l.954-961 — "Your parts, layout and settings are kept in this browser."
  — The stored work is kept for a browser, not for a user, so when a sign-in runs out
  and a different person signs in, that person is shown the previous user's parts, and
  the page uploads them under the new user — add to l.954-961: the stored work carries
  the user it belongs to, and a page that opens signed in as someone else starts empty
  (clearing or hiding the other's work is the choice to state). Add it to "What a flaw
  would expose" at l.1287.
- l.226-228 — "the page reconnects silently, because progress streams are closed
  routinely" — With no request waiting, a page that only follows a print or a slice
  shows nothing when the front server is unreachable for minutes: the print card keeps
  showing its last figures as current, and the slicing card's state "The server cannot
  be reached" (l.614) has no moment at which it begins — state the rule: a progress
  stream that has failed to reopen for 20 seconds is treated as a failed request (the
  panel line of l.215, the slicing card's row of l.614, and the print card's figures
  greyed as at l.795).
- No line — The plan's standing requirement "Supportable from the server" is left out:
  failures that happen only in the browser (a part the page cannot read, storage refused
  or cleared, a lost 3D drawing context, the layout code failing on a part, an error
  message the page composed itself) reach no log — add a section saying which of these
  the page reports to the front server and what the report must never carry (a part's
  geometry), and add the request to l.1156-1176 and to the contract.
- l.320-323 — "the configuration's one option is the only control" — The configuration
  cannot be edited from the wizard and its edit screens are in no phase (l.303-304), so
  in a group with the built-in default nobody can use an STL file in millimetres at all;
  the mockup's answer (M25) assumed an administrator could set the option — say so in
  one sentence and list it under undecided with its options (leave it; the built-in
  default's units; a switch on the upload area until the edit screens exist).
- l.87-91, l.372, l.644-645 — "Plate 1, 16 instances" and "print the rest on a second
  plate" — The wizard holds one plate; nothing says how a user starts the second plate,
  clears a finished one, or what gives a plate its number — add to the Parts step what
  the user does (remove the rows by hand, or a "New plate" action, which no source has)
  and what "Plate 1" counts.
- l.753-755 — "Until phase 5 there is no printer: the step shows what will be printed,
  and its button is Download the sliced file." — Thin for a screen nobody has seen:
  the card of l.736 names "the printer by name" and there is none, the line of l.742
  ("Send starts the print at once") must not show, and the step and its tab are still
  called Send — say what the card holds, that the plate-clear line and the caret are
  absent, and whether the step keeps its name until phase 5.
- l.303-305 — "A group that has no configuration gets a built-in default" — A
  configuration that exists and cannot be read is not designed; the front server reports
  it and the group cannot slice until the document is repaired (front/README.md, "Things
  this design fixes", "A damaged configuration is reported, never replaced by the
  default") — add what the wizard shows, in which place, and that it names no
  "administrator".
- l.1215-1219 — the table "How well it must do it" — No target for the Layout view
  itself: 150 instances of parts of up to 150,000 triangles is the largest plate allowed,
  and l.1351 says the Layout view must be "fast enough" with no figure — add a row
  (proposed, with its reason), and a row for the memory the page may use at that plate.
- l.1464-1465 — "A school-issue laptop with integrated graphics and 8 GB of memory" and
  "the kind of aarch64 Linux machine the mockup was measured on" — Neither is a stated
  machine: drawing in software depends on the processor's cores and speed, which are not
  given, so the 10 frames a second cannot be checked or repeated — give each machine's
  processor, core count and memory, or say that naming them is part of what is undecided.
- l.894-905 and l.715-730 — "On the Parts step, empty ... The stored parts are dropped"
  against "your parts, layout and settings are unchanged" — A page left open when the
  sliced plate expires keeps the plate and offers Slice again; the same page refreshed a
  minute later opens empty and the user adds every part again. Both rules have sources,
  but the guide gives no reason for dropping the parts and does not put the two side by
  side — add the reason, or raise the difference under undecided with the option of
  keeping the parts on return as well.
- l.726-729 — "The page does not slice again by itself" — Not said: what happens when the
  sliced plate expires while the user is on another step and then presses Next into the
  Preview step, where entering slices (l.596) — add "Entering the Preview step after the
  expiry slices, as for any plate not yet sliced; the message appears only on the
  Preview and Send steps."
- l.801-812 — "After it, the card goes" — Not designed: what the printer-status icon and
  the printer details show after Stop following, or after the server gives a print up at
  24 hours. Printer delivery ends such a delivery job as failed with a sentence that the
  outcome is unknown (delivery/README.md l.654-668), and the icon's "Failed (red)"
  (l.826) means a fault at the printer — add a row to both tables, in words that do not
  say the print failed.
- l.827 and l.847-848 — "Offline (grey)" and the rows "Stale" and "Offline" — Not said
  which applies when a daemon is silent for more than two minutes during a print: the
  icon says Offline, but the details' Offline row has no figures and no Stop following,
  and the Send step's Offline message (l.784) says nothing of the print — say that a
  followed print's rows win: the busy or print card with greyed figures and Stop
  following, under an icon that says Offline.
- l.874 — "Paired with Shop H2S." — The guide never says where the printer's name comes
  from; the pairing form has one field, for the code — add one sentence (details l.400:
  from the paired-printer record; who types it and where is to be stated).
- l.920-935 — "reloads itself at the next quiet moment" — A quiet moment can come one
  second after the user lets go of the mouse, and the reload then resets the camera, the
  selection and the layer bar and closes notifications without a word; no least idle time
  is given and no reason for saying nothing — add the idle time (a figure, proposed) and
  the reason, and list the choice in the table of l.1388.
- l.289-293 — "Change to FRC 1678? Your 2 changes and this plate's slice are cleared."
  — Not said: a slice still running is cancelled; and since the slice is cleared, the
  print card of a plate sent before the change cannot come back "by changing back" with
  Send enabled for the same sliced plate — say what changing back shows.
- No line — Accessibility is scattered (the keyboard in advanced mode l.449, the layer
  bar l.667, the icon l.835) and never stated as a requirement: nothing says whether the
  Layout step can be worked by keyboard, or what a screen reader gets there — add a short
  section saying what is required and what is not.
- l.1249-1251 — "Safari is not supported" — What a Safari user sees is not said; the
  front server's guide proposes "a plain page saying that PenguinSlicer needs Chrome"
  (front/README.md l.182-184) — add the sentence and which component shows the page.
- l.493-498 and l.670 — "right-drag to look around" on the Layout step, "right-drag to
  pan" on the Preview step — The two 3D views give the right button opposite meanings.
  Both are as the mockup has them, and the Layout step's follows the answer "like
  Onshape", but the guide does not say the difference is intended — say so, or list it
  under undecided.

**Length.** Sections to cut or shorten:

- l.1356-1380, "What the mockup faked" — Cut. The mockup is thrown away and the table is
  history. Move its four live requirements to their places: the time expected is good to
  a factor of two, so the slicing card says "about" (to l.596-601); export times are
  unknown, so a row's bar promises no duration (to l.325-328); the documentation page for
  pairing is written in phase 5 (to l.869); the font differs by system (to l.108-112).
- l.1134-1144, l.1425-1437 and l.1471-1475 — The mockup's method failing is told three
  times. Keep the figures once, under the risk at l.1425, and leave two sentences at
  l.1134.
- l.912-916, l.968-976 and l.1238-1242 — "Work does not follow a user" is explained three
  times. Keep l.947-990 as the owner and leave a sentence and a link at the other two.
- l.689-694 and l.701-707 — The colour-difference figures and the shading's second colour
  are a builder's; one sentence ("checked by simulation for the three common kinds of
  colour blindness") is enough here, with the figures in the details file.
- l.161-168, l.831-836 — Tooltip and hover timings in the body repeat the row at l.1207;
  keep the row.

Too thin: the Send step before phase 5 (l.753), where the printer's name comes from
(l.874), how the wizard "asks once more" (heading 2), and everything listed above as
left out.

## 2. Written for a person

No make target, route, status code, setting name or error code slipped in. What did:

- l.684-687, l.701, l.707 — "`#2b5c9e`", "`#1c3d68`", "`#95a0ac`" — Colour codes are the
  one code-level notation in the guide — keep the four in the table, since the owner
  chose them, and drop the three in the prose in favour of words ("a darker blue", "a
  faint grey").
- l.690-692 — "the smallest difference between any two is 16.8 on the CIEDE2000 scale"
  — A figure with no statement of what is enough — add "(a difference above about 10 is
  plain to the eye)" or move it to the details file.
- l.102-106 — the table of widths — It stands before the text that explains its rows:
  "step circles", "quick changes", "advanced mode", "its sections", "the figures of a
  print" and "the parts list" are all defined later — move the table to the end of "The
  panel as a whole" with one sentence a row, or to "How well it must do it".
- l.99-100 — "Four widths change the layout, each including itself" — The table has
  three — "Three widths".
- l.97 — "The panel is fluid" — "The panel" is used throughout for the wizard's surface,
  in Onshape's panel and in a tab alike, and is never defined beside "the page" (l.67) —
  add to the terms: "The **panel** is the area the wizard draws in, whether that is
  Onshape's right panel or a browser tab."
- l.150-159 — "The panel has five ways to say something" — A sixth is used four times
  and never described: "asks once more" (l.289, l.420, l.804, l.879) — add a row saying
  what it is (a box joined to the control, or a dialog over the panel) and how it is
  dismissed.
- l.129-131 and l.215-216 — "the **panel line**" — Defined as a line that "goes at the
  user's next move or after a few seconds", then used for a retry message that stays, is
  red and holds a button — define it once with both uses, and say which wins when both
  apply.
- l.482-483 — "Beside it, when the selection could lie better, one link: "Lay it the
  best way", or "Put back as modelled"." — Must be read twice: "Put back as modelled" is
  not shown because the selection could lie better — "Beside it, one link at most: "Lay
  it the best way" when it does not lie its best way, "Put back as modelled" when it has
  been laid down differently from the model; nothing when it lies as modelled and that is
  its best way."
- l.558-561 — "The wizard does turn an instance at the moments when it gives it an
  orientation itself" — Must be read twice, and lists one case of three (heading 3) —
  "The wizard turns an instance about the vertical only when it has just laid it down
  itself and it is then too long for the plate:" followed by the cases.
- l.896-910 — the returning page's table — Its rows are not exclusive (a plate can have a
  finished slice and a print), and the rule that settles it comes after the table, as
  "the exception to the last row" — put the row for a print first and say before the
  table "the first row that applies".
- l.1047-1048 — "its cost grows with the part's corners times the hull's triangles" —
  Says nothing to this reader — "the time grows roughly with the square of the part's
  detail".
- l.774 — "under the plate-clear line" — A name used once for the line of l.741-744 and
  never given there — name it at l.741 or say "the line above the button".
- l.795 and l.847 — "the print's figures are stale", the row "Stale" — The section calls
  the state "gone quiet", the table "Stale", the icon "Offline" after two minutes — use
  "gone quiet" in the table and say once how it differs from Offline.

## 3. True

**Against the mockup's decisions, step by step.** The guide carries the decisions of every
step. Where it differs, most serious first:

- l.558-561 — "a part that arrives too long for the plate as it lies is turned" —
  Decision 64 has three more cases: an instance Auto-orient lays down that is then too
  long; an instance a lay-down leaves beside the plate, which "waits turned ... so that
  Arrange, which never turns, can place it" (decision 26); and an instance moved to the
  nearest free spot — add them.
- l.320-323 — "arrives 25.4 times too large and then fails the height or plate checks on
  the Layout step" — Copied from the mockup's M25, where nothing was checked on arrival.
  In this design the slice service checks each part when it is added, with its units,
  and refuses one "too large for the printer" on the Parts step (l.349) — "is usually
  refused on the Parts step as too large for the printer; one that passes fails the
  height or plate checks on the Layout step", and say that the refusal for an uploaded
  file reminds the user how STL files are read.
- l.732-751 — the Send step — Decision 42, "With no printer paired, nothing on the step
  names a printer", is omitted, while the card names "the printer by name" and the button
  is "Send to Shop H2S" — add what the card and the button are with no printer paired.
- l.580-581 — "An instance that Arrange left beside the plate gets no message of its
  own; Arrange's message already counts it." — Decision 57 and 64 except an instance too
  long for the plate as it is turned, which has its own message and is not counted by
  Arrange's — add the exception.
- l.576 — the row "An instance longer than the plate takes" — Decision 64 says "longer
  or wider", and that an instance still standing on the plate gets the same sentences
  after "not fully on the plate", with Turn it to fit in place of Arrange — add both.
- l.488-489 and l.545-546 — "The messages: anything the wizard moved" — Omitted: such a
  message, and "Arranged 16 instances.", goes when the user leaves the Layout step
  (decision 59, fix round 1 of version 7) — add.
- l.127 — "Every circle is clickable and shows its step's name as its tooltip" — The
  current step's circle, whose name shows beside it, has none (decision 3) — "every
  circle but the current one".
- l.477 — "the **pointer line**: one small line" — The decisions file (item 16) keeps it
  at 11 px, the one text below the body size — "one line at 11 px".
- l.1036-1041 — "if no kept face points within 30 degrees of that side" — Decision 61
  allows half a degree more, so that the hex shaft's flats, exactly 30 degrees off, count
  as covering; without it the guide's own example sits on the boundary. Also omitted:
  the rule keeps patches on a slanted part's ends (the Shooter Hood Rib's), which stood
  on make the part too tall and get the usual message (M29, "end patches included") —
  add both.
- l.142-143 — "one plain line for each change" — Omitted from decision 4: a setting that
  has a quick change is named in the quick change's words ("Others › Brim: Off (profile
  Auto)"), so the menu and the line agree — add.
- l.198 — "millimetres to 0.1 mm" — Decision 53 also has heights and spacing to 1 mm and
  distances to 0.1 mm — add, since the examples depend on it.
- l.410-454 (advanced mode), l.831-836 (printer details), l.695-697 (colour key),
  l.746-751 (the Send button's menu) — Details of decisions 13, 44, 33 and 36 are left
  out (the rail shows the section last opened; Expand all and Collapse all are
  remembered; focus stays where the user acted; opening the printer details closes the
  change details; the colour key closes on leaving the step; the menu's keys; Back keeps
  its width). They are a builder's, but the details file does not hold them either and
  the mockup is to be thrown away — carry them into the details file before that.

No question of "Please react to these" is treated as open or answered differently. M1,
M2, M3, M6, M16, M17, M18 and M29 are answered as the decisions file answers them, and
M7, M11, M21, M22, M23, M25 and M26 stand as the mockup has them.

**The twelve screens.** All twelve are designed, in the place a user meets them, and
listed at l.1388-1403 (with two more rows: the retry message, and the Send step before
phase 5).

| | Screen | Designed, in place | In pattern | What is thin or out of pattern |
|---|---|---|---|---|
| 3.1 | Signing in, failed, run out | Yes, l.230-260 | Partly | The run-out screen is called a card but is what l.156 calls a message (what happened, what to do, a button). "A blank printer-status icon" (l.256) is a state the icon's table (l.820-829) does not have; use the grey dot and "…" or add the row |
| 3.2 | Current group, Sign in again | Yes, l.262-305 | Yes | The confirmation's form (heading 2); a running slice at a change |
| 3.3 | Expiry with the page open | Yes, l.715-730 | Yes | Expiry while on another step (heading 1) |
| 3.4 | Waiting, and no room | Yes, l.612, l.619-625 | Yes | Nothing |
| 3.5 | Pairing, wrong code, unpairing | Yes, l.855-884 | Yes | Where the printer's name comes from. Unpair is off with a tooltip, and touch shows no tooltip (l.168) |
| 3.6 | Gone quiet, Stop following | Yes, l.792-812, l.847 | Yes | The icon and details afterwards; quiet against Offline (heading 1) |
| 3.7 | The page reloading itself | Yes, l.918-935 | Yes | No least idle time, no reason for silence |
| 3.8 | Stopped from another tab | Yes, l.627-633 | Yes | Nothing |
| 3.9 | What a restart shows | Yes, l.616, l.785, l.829, l.1315-1321 | Yes | The architecture says the Send step is "blank"; the guide keeps the print card's last figures (l.1318). Say that this is chosen, and what a page opened during those seconds shows |
| 3.10 | A print nobody sent | Yes, l.783, l.844 | Yes | Nothing |
| 3.11 | Limits on parts | Yes, l.365-377 | Yes | Nothing |
| 3.12 | Out of memory | Yes, l.645 | Yes | Its remedy differs from the slice service's own (below) |

**The writer's thirteen choices.**

| Choice | Does it contradict a source? | Can the owner see it as a choice? |
|---|---|---|
| A run-out sign-in is a card with a button; the page does not leave by itself (l.253-260) | Yes, three texts marked proposed: the contract l.66-67 ("on which the page starts it"), the front server's guide l.178-180 ("the page starts the sign-in itself") and the details l.347-349 | Reason given; not shown as a choice, and the three texts are left disagreeing |
| Sign in again inside the group details (l.272-283) | In the letter: the approved design, the front server's guide l.240 and the details l.353 say "beside the current group's name" | Reason given (one row at 320 px); not shown as a departure |
| Changing group clears the changes and the slice, keeps parts and layout (l.285-293) | No source | No |
| The retry message on the panel line, with "Retry now" (l.215-221) | No; the words are the builder's | Reason given for the place; "Retry now" is an addition nobody asked for and is not marked |
| Expiry with the page open (l.715-730) | No | No; and it differs from the returning page (heading 1) |
| No room to wait: amber, no retry by itself (l.619-625) | No; agrees with the contract l.129-132 | Reason given |
| Out of memory offers no Slice again (l.645) | The button, no. The remedy for one instance, yes: "Slice it in Orca Slicer on your own computer" against the slice service's "split or simplify the part" (slice/README.md l.832) | Reason given for the button |
| The pairing form in the printer details and on the Send step (l.862-864) | No; agrees with the details | Reason given |
| Stop following and Unpair open to every user; Unpair off during a followed print (l.800-803, l.878-884) | No; agrees with printer delivery l.208-214, which adds that whether the relay itself refuses is undecided. The guide omits that | Reason given for Stop following |
| "Not heard from yet" as a grey dot and "…" (l.785, l.829) | The architecture's word is "blank" | No |
| The self-reload shows nothing (l.927-935) | No | Stated, with no reason |
| The Send step exists from phase 2, with Download as its button (l.753-755, l.1412) | The plan's phase 5 and the details' table by phase (l.519-522) give the Send step to phase 5 and "the download" to phase 2 | Listed at l.1403; the difference from the plan is not said |
| Signing out is undecided (l.1496-1501) | No; the front server's guide says the same | Yes, with a proposal. But l.1289-1290 lists it among accepted risks |

**What the wizard asks of the front server.**

- l.720 and l.1170-1171 — "The page knows both times" and "with the time its slice
  ended, so the page can tell when it will expire" — The contract's section on the sliced
  file carries no such time, and the time the last print ended is not asked for at all;
  the page's clock may also be wrong (l.725) — ask for one thing, the moment the sliced
  file will be refused, as the front server reckons it, sent with the sliced file's
  summary and again when a print ends; add it to the table at l.1187 and to the contract.
- l.1191 — "The list of those settings, with each one's kind, range and choices" — Not in
  the contract. It is marked undecided, which is right; add it to the contract when
  settled.
- l.1156-1176 — the list — Missing: the request that reports the browser's own failures
  (heading 1), and signing out if the proposal at l.1499 stands.
- l.295-298 — "the page takes the first of the user's groups and says so" — The front
  server's guide tells the user to "Choose another group, or sign in again"
  (front/README.md, "When things go wrong") — the two guides should say one thing.

**Other figures and claims.**

- l.1287-1288 — "The parts sit unencrypted in the browser's storage until the plate
  expires" — Not what l.956 says: they stay until the page is next opened after the
  sliced file expired, and a plate never sliced never expires — "until the page is next
  opened after the plate's sliced file has expired; a plate never sliced stays until its
  rows are removed".
- l.1315 — "A restart or a deploy costs a user a pause and nothing else." — One known
  case is lost: a user who submits a plate while the slice service is finishing another
  user's slice before stopping sees "The server is being slow" for up to the time limit
  of 240 seconds plus the replacement's start, and past 300 seconds "The server could not
  be reached" (slice/README.md l.883) — add the sentence.
- l.343-348 — the row "A file is not an STL file the slice service can read" — The slice
  service refuses a text STL with its own reason, "a binary STL is needed"
  (slice/README.md l.122); the guide's sentence for that file would be "it is not a valid
  STL file", which is false of it, and l.1491-1492 says the refusal "saying so" is "this
  guide's text" — add a row for a text STL ("bracket.stl is a text STL. PenguinSlicer
  reads binary STL; export it again as binary.").
- l.1249 and l.1528 — "Chrome is the supported browser." — Stated flat here and as a
  proposal at l.1463, whose reason, "It is the one browser the design supports", is
  circular: the approved design says only that Safari is not supported and that the
  panel depends on Chrome (architecture l.260; details l.503-505). The front server's
  guide says the same sentence, also without a source — at l.1249 write "Chrome is
  proposed as the supported browser ([undecided])", and give the reason at l.1463 as
  "Onshape's panel depends on Chrome's handling of an embedded page's cookie and storage,
  and it is the browser the measurements were made in".
- l.1466-1467 — "At least 30 frames a second" and "At least 10 frames a second" — Both
  are marked proposed, each with a reason, under what is undecided, and l.1146-1147 and
  l.1219 point there; that is right. The reasons are assertions with no measurement
  behind them — say so in the sentence at l.1456-1459.
- l.1468 — "May be simplified while the view moves" — This relaxes decision 33's first
  and third requirements ("by whatever means keeps the look", "no combs and no
  show-through at any viewing angle"), which l.1118-1123 states as required — say in the
  row that it departs from the accepted requirement and needs the owner's yes.
- l.1471-1472 — "roughly a hundredfold cut from what the mockup's method takes" — True of
  the four-instance plate (about 10 seconds a frame). The target names the 14.1 MB plate
  and a plate of 150 instances, where the cut is far larger — "a hundredfold on a plate
  of four instances, and more on the plates the target names".
- l.1489-1494 — "Files other than binary STL" — Stated as undecided with both sides and
  what a user loses; that is right. Missing from it: that the mockup's decision 51 ("A
  3MF file states its own units") is thereby not carried, and the row for a text STL
  above.
- l.413-414 — "about 295 of them, and none of the programmatic ones" — About 295 is the
  count of all of Orca's settings (the mockup's "99 of about 295"; l.1371 says "about
  295, less the programmatic ones") — use l.1371's words.
- l.276-278 — "a group is read from Onshape only at sign-in" — Lost: "until the Onshape
  app is public", after which groups are read again once a day (front/README.md, "Onshape's
  yearly allowance of calls") — add the clause. Also omitted: nothing limits how often
  Sign in again is used, which the front server's guide lists as undecided.
- l.1512-1513 — "the Layout step as accepted shows no such mark" — Then the row at l.1370
  ("an invented threshold for "will need supports"") describes something the accepted
  mockup did not show to a user; the two disagree about what the mockup had — settle it
  from the mockup's "What is fake", item 14 (auto-orient's own score used the threshold).
- [README-details.md](../../../wizard/README-details.md) l.3-12, l.353, l.519-522,
  l.565-590 — "it is begun, not complete", "beside the current group's name", the Send
  step in phase 5, "Still to be written" — The details file now disagrees with the guide
  in these places and holds none of the steps; the two must not disagree (the
  repository's CLAUDE.md) — bring the details file into line once the guide is agreed.

## 4. One name per thing, and the design as it is to be

- l.70 and l.425 — "A **group** is the users who share one configuration" and
  "collapsible **groups** such as Precision" — One word for two things, both in bold, and
  both met in one sentence at l.401-408 — call the second "a setting group" everywhere
  (l.425-451, l.931-933, l.963-964).
- l.158 and l.183-184, l.638, l.642-643, l.770 — "**Details**: a small box that opens
  joined to the header element" and "folded under **Details**" — One name for two things:
  a box joined to an icon, and a folded part of a message — keep "Details" for the folded
  part, which is the word the user reads, and name the boxes only by their own names
  (the printer details, the group details, the change details, the colour key), calling
  the kind "a joined box".
- l.612-616, l.644-645 — "Waiting for the slicer", "The slicer restarted", "the server's
  limit", "more memory than the server allows" — In the sentences a user reads, the slice
  service is "the slicer" in three and "the server" in two, and "the server" is also the
  front server (l.215-216) — "the slicer" for the slice service in every sentence.
- l.1289-1290 and l.1496 — "the design has no sign-out" among "Accepted risks", and
  "Sign-out" among the undecided items with a proposal to add one — Accepted and
  undecided at once — remove it from the accepted risks and leave the link.
- l.1356-1380 — "What the mockup faked" — History of a document that is to be thrown
  away (heading 1) — cut.
- l.1384-1386, l.1407-1408, l.1512-1513 — "The mockup was reviewed step by step and its
  screens are settled", "The mockup that the steps above were settled on", "as accepted"
  — How the design was reached, in the body — at l.1384 keep only "The screens below
  have never been drawn"; drop the other two clauses.
- l.1134-1144 — "Why the mockup's method fails" — A rejected method told at length in the
  body — two sentences, with the figures under the risk at l.1425.
- l.208, l.604, l.717, l.810 — "the front server restarts", "running on the server",
  "kept on the server", "given up by the server itself" — In the guide's own prose "the
  server" stands for the front server, the slice service and the relay in turn — name the
  component in each.

Nothing is stated as open that the decisions file settles. Stated as settled with no
approved source: Chrome as the supported browser (l.1249), and the Send step in phase 2
(l.1412).
