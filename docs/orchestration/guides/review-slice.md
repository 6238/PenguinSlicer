# Review of the slice service's guide

The guide ([slice/README.md](../../../slice/README.md), 1,123 lines) is close but not ready
for the owner: its figures match the code and the details file almost everywhere, and it
carries no code-level names, but it has gaps a decider would trip on. The single most
important thing to fix is the settings requirement. Its rule matches the decisions file,
item 5, exactly, yet everything built around the rule is the writer's own and partly stated
as fact (the security reasoning, the check of each value, the sum of 7,404 MB), and the
requirement the rule creates is missing: nothing says where the wizard's advanced mode gets
the list of settings, their kinds, permitted values and the profile's own values, nor how
the checks that depend on "supports on" behave once any setting is accepted.

Line numbers are those of the guide as reviewed on Fri 2026-11-27. "Details" is
[slice/README-details.md](../../../slice/README-details.md); "architecture" is
[docs/architecture.md](../../architecture.md); "decisions" is
[decisions-2026-11-27.md](decisions-2026-11-27.md).

## 1. Can the reader decide from it?

| Question | Answer | What is missing |
|---|---|---|
| Does it do the right things for a user? | Mostly yes | How a user comes to be offered a setting or a profile at all (1.1); what the slice service gives the Preview step (1.3) |
| Is the division of work sound? | Yes, with two gaps | Who supplies the catalog's names and the settings list (1.1); which component owns the proposed test of configurations (3.5) |
| Are the approaches to the hard parts sound? | Yes | Nothing; memory, stopping, deciding how a slice ended and reading Orca are the strongest sections |
| Are the limits and targets right? | Yes for limits | No target a user feels is stated (1.7) |
| Is security adequate? | Not decidable for one machine | Who can reach it in phase 2, and that nothing proves a request is the front server's (1.4) |
| Failure, cancel, restart, deploy | Cancel and restart yes; deploy no | The worst case of a deploy during a slice (1.2); a new front server meeting an old slice service (1.5) |
| What is built and what is not | Yes | Clear in every section's opening line |
| What remains undecided | Mostly | Three items listed as undecided are decided future work (4.7); one open point may be settled by item 5 (4.8) |

Findings, most serious first.

- **1.1** — Lines 271-299 and 243-269, "Accept settings" and "Offer profiles" — A missing
  requirement. Item 5 makes every parameter setting "available in the wizard's advanced
  mode", and the plan (phase 2, "What it needs from the slice service") says "the wizard
  needs the profile catalog's names for its menus, and where it reads them from is open".
  The guide never says where the wizard gets the list of accepted settings, each one's kind,
  permitted values and the chosen process profile's own value, nor the catalog's names. The
  HTTP interface as built offers neither (the code has routes for slice jobs only). Line
  1096 raises it only for editing a configuration. Fix: add to "Accept settings" a paragraph
  stating the requirement ("The front server must be able to ask the slice service for the
  profile catalog's names and, for a chosen process profile, every accepted setting with its
  kind, its permitted values and the profile's own value; the wizard's advanced mode is
  drawn from that answer. To be built in phase 2.") and move the question of how into
  "Undecided", or state that it is open with the options (the slice service serves them; the
  front server carries a copy generated at build time, which breaks the rule that a
  component depends only on contracts).
- **1.2** — Lines 823-829, "It stops accepting new slice jobs, with an answer the front
  server and the page quietly try again and that no user sees" — Not true in the worst case
  the guide itself sets up. The running slice may take up to the time limit, 240 seconds;
  decisions item 14 has the page show "the server is being slow" after 20 seconds of failed
  retries and give up at 300 seconds. So a user who submits while a stopping slice service
  finishes a long slice sees the retry message for up to four minutes, and the two users
  whose waiting slice jobs were cancelled see the same. Fix: after "then exits" add: "While
  it finishes, nobody else can slice: a user who submits in that time sees nothing for 20
  seconds, then the wizard's message that the server is being slow, for as long as the
  running slice takes, at most the time limit of 240 seconds, which is inside the 300
  seconds the page keeps retrying." If the time limit rises after phase 3's measurements it
  can pass 300 seconds; say so under "Unmeasured".
- **1.3** — Whole guide — The Preview step is never mentioned as a consumer. The plan says
  the slice service "returns the sliced file and a summary, not toolpaths"; decisions item
  18 leaves the preview's method to implementation. A reader cannot tell whether the slice
  service owes the preview anything. Fix: one sentence in "What goes in and what comes out"
  after line 43: "The wizard's Preview step draws its layers from the sliced file itself;
  the slice service produces nothing else for it."
- **1.4** — Lines 708-715, "Who can reach it. Only the front server. Hosted, the slice
  container is on Railway's private network" — Says nothing for phase 2 on one machine, and
  does not state the accepted risk that the slice service cannot tell the front server from
  anything else that reaches its address. As built it listens on the machine's own loopback
  address by default. Fix: add "On one machine (phase 2) it listens only on that machine's
  loopback address, as it does today." and add to "What is accepted" (line 771): "Anything
  that can reach its address is believed to be the front server, with whatever user key it
  names; the private network, or the loopback address, is the only guard."
- **1.5** — Lines 819-833 — No word on the two containers running different versions. The
  architecture deploys "only the container that changed", so a new front server meets an
  old slice service and the reverse, and the plate configuration's contract is about to
  change (units, hashes, settings). The architecture's "Old and new versions together" has
  no rule for this pair. Fix: add under "When asked to stop" either the rule ("a change to
  the plate configuration or to the HTTP interface is made so that the previous version of
  the front server still works against the new slice service, and the reverse") marked as a
  proposal, or an entry under "Undecided" saying no rule exists yet.
- **1.6** — Lines 216-232 and 593-603 — The checks keyed on "supports on" are not carried
  forward to the wider settings. Today supports are one switch; from phase 2 any parameter
  is accepted (support type, brim width, skirt, raft, printing one object at a time), and
  several widen what an instance needs around it. Line 228 says only "another part or
  setting may need more". Fix: add to "Accept settings": "The placement check's spacing and
  the two estimates go on asking one question, whether supports are on. Other accepted
  settings can make an instance need more room (a wide brim, for one); the placement check
  does not know them, so such a plate passes the check and Orca refuses it with the report
  that names the pair." State it as today's design with the cost, or list it as undecided.
- **1.7** — Lines 634-688 — Limits are complete; no target is stated for what a user waits
  for. Fix: one sentence under "The limits": "There is no target for how long a slice may
  take beyond the time limit, and none for how long the check of an arriving part may take;
  the measured figures are 0.17 to 0.19 seconds to read all eight real parts and up to 5.8
  seconds to accept the largest plate." Or state the target if one is wanted.
- **1.8** — Lines 107-111 and 124 — The check "fits the printer in no orientation" runs from
  phase 2 when the part arrives, before any plate names a printer; the guide does not say
  against which printer. Details proposes "the largest printer of the catalog", and again
  against the plate's printer later. Fix: add after line 111: "On arrival the fit test uses
  the largest printer in the catalog (proposed); it runs again against the plate's own
  printer when a plate names the part."
- **1.9** — Lines 157-159 and 169-171 — "named by the SHA-256 hash of its bytes" and "The
  same file under different units is a different part" cannot both be read plainly: the
  reader is left to work out that a part is kept under its user key, its hash and its units
  together, and that the same file under two units counts twice toward the 25. Fix: at line
  171 add "A part is kept under its user key, its hash and its units together, so the same
  file under inches and under millimetres is two parts and counts twice toward the limit of
  25."

**Is every part earning its place at 1,123 lines?** No. About 150 lines can go without loss
to this reader.

Cut or shorten:

- **"The log", lines 835-876 (42 lines).** The architecture owns "Reading what happened".
  Keep the first paragraph, the sizing figures on the line that ends a slice job, the near
  miss, the once-a-minute line and the reason the front server collects the lines; drop the
  field-by-field lists (lines 845-855) and the buffer mechanics. About 15 lines.
- **"What a restart does", lines 807-817.** Lines 811-817 restate the architecture's table
  "The slice container restarts". Keep the slice service's own part (forgets slice jobs,
  empties the part store, removes dead scratch folders) and one sentence with the link.
- **"Taking a new Orca version", "Where it stands", lines 906-910.** The account of running
  the command to 2.5.1, to 2.4.1 and back is history and builder's evidence. Replace with:
  "The upgrade and the return were both tried on real versions and left no change behind."
- **"How it is tested", lines 935-947.** The list of the stand-in's modes and the paragraph
  "No test can hang" are builder's detail. Keep one sentence each.
- **"Running Orca", lines 458-462.** The 200 lines, the 4 KB and the clean folder are
  builder's detail; keep the first three bullets.
- **"Reading what Orca says", lines 573-576 and 585-586.** The sorting example and the 64 MB
  and 4 KB bounds: keep "the same plate gives the same list of warnings every time" and
  drop the rest.
- **The measurement table, line 651.** The row of 196 spacers is over the limit of 150
  instances and supports no conclusion in the guide; drop it or say why it is there.

Too thin: "Accept settings" (1.1, 1.6); "Units" (1.9, and what a plate configuration
without a units label means); "Security" for one machine (1.4); "When asked to stop" (1.2,
1.5); the fit test on arrival (1.8).

Not duplicated and worth their length: "Bounding Orca's memory", "Stopping Orca, and
deciding how a slice ended", "The estimates of memory and time", the limits table, and
"When things go wrong".

## 2. Written for a person

Code-level names: none found. No make target, route path, HTTP verb or status code, setting
or environment-variable name, constant, error code, function, class, file or test name is in
the guide. `.gcode.3mf` (line 37) and "SHA-256" (line 170) are a file format and a named
algorithm, both in the plan, and stand.

Sentences that must be read twice:

- Line 413-414 — "A user who comes back finds the slice done, not cancelled and to be waited
  for again." — The second half does not parse at first reading. Fix: "A user who comes back
  finds the slice done, where today they would find it cancelled and have to slice again."
- Line 502-503 — "The largest such rise measured was 502 MB (from 1,347 to 1,861 MB in 0.26
  seconds)." — The reader subtracts and gets 514. The source has the same mixture (details
  line 991: 514,268 kB is 502 MB of 1,024 kB, beside endpoints that differ by 514). Fix:
  drop the endpoints ("was 502 MB in 0.26 seconds"), and report the mixture to whoever owns
  the details file.
- Line 657 — "The same twelve, at a 3,000 MB ceiling" — The table gives a row measured under
  another ceiling with no word of why. Fix: add to the paragraph at line 662: "The twelve
  blocks with supports on pass today's ceiling of 2,000 MB and are stopped there; their
  figures are from a run with the ceiling raised to 3,000 MB for the measurement."
- Line 659 — "over 2,500, stopped" — Stopped by what, when the ceiling is 2,000 MB? Fix:
  "passed 2,500 MB and was stopped there, in a measuring run with the ceiling raised".
- Line 660 — "Six Stanford bunnies ... the heaviest plate ever measured" — Nothing says what
  a Stanford bunny is or that this plate was measured on another machine. Fix: "Six copies
  of a standard test model of a rabbit (112,402 triangles each), measured on a second
  aarch64 machine".
- Line 673 — "By the measurements: 6,000 MB, plus the 502 MB ..., plus 400 MB ..., is 6,902
  MB" — The sum has no conclusion. Fix: append "under the 8 GB, with about 1,100 MB to
  spare (the sum is proposed, not measured)"; details marks the sum as proposed.
- Line 1067 — "Money only while a heavy plate is slicing, since Railway bills ..." — A
  fragment whose subject is missing. Fix: "It costs more money only while a heavy plate is
  slicing, since ...".

Tables holding prose, or standing before their explanation:

- Line 124 — The cell beginning "The user, before any layout work. The test is deliberately
  lenient ..." — Sixty words of mechanism in a table cell. Fix: cut the cell to "The user,
  before any layout work" and move the rest to a paragraph after the table.
- Lines 349-363 — The table of stages uses "Building the plate" and "Slicing the plate"
  before lines 368-370 say what they are. Fix: move the sentence on the slice service's own
  stages above the table.
- Line 687 — "Near-miss warning in the log" — A row of the limits table that is explained
  only 170 lines later, in "The log". Fix: add "(a slice that came close to a limit without
  reaching it)" in the row.

Terms used before they are defined:

- Line 153 — "the hash that names the part" — Naming by hash is introduced at line 170.
  Fix: put "Keep each part once: the part store" before "Units", or write at line 153 "the
  hash of its bytes, by which a part is named (see the part store, below)".
- Lines 330 and 417 — "the time limit" — Defined at line 464. Fix: at line 330 write "the
  time limit, the longest one Orca may run (240 seconds today)".
- Lines 130, 445, 512 — "the tests against the real Orca" — The term "upstream check" is
  defined at line 892; see 4.1.
- Line 189 — "The page" — Never defined; see 4.4.
- Line 787 — "the print server" — Explained only at line 1118. Fix: add after the table "In
  these sentences 'the print server' is the old word for the slice service."

Paragraphs that list where they should explain: lines 845-855 (the fields of the log line),
covered under heading 1.

## 3. True

Checked against the details file, the architecture, the frozen design, the decisions file,
the plate configuration's contract and the code (the four settings and their values, the
figures of the two estimates, the limits, the catalog's counts of 4, 136, 16 and 27, the
340 mm height, the quoted sentences, the default listening address). Everything not listed
below agrees with its source.

The four things of the writer's own making:

- **3.1 The security reasoning for refusing programmatic settings: stated as fact.** Lines
  290-293 ("The line is drawn there for security ... a parameter can only choose among
  behaviours Orca already has") and 734-741 ("the rule for them is the security boundary
  ... custom G-code is two things at once, a small template language that Orca evaluates on
  the server, and raw commands that a shared printer would then carry out"). Decisions item
  5 gives the rule and no reason; no source in the repository holds this reasoning or the
  claim about a template language. Fix: keep the rule as fact and mark the reasoning: begin
  line 290 "The reason this guide proposes for the line is security:" and line 734 "The
  proposed reasoning:"; or cut the reasoning to one clause. The sentence at lines 740-741,
  that start and end G-code comes from the catalog's profiles and never from a user, is true
  of the code and stands.
- **3.2 "7,404 MB" for two Orcas at 3,000 MB: stated as fact.** Line 1068, "By the same sum
  as above, two Orcas at 3,000 MB plus a 502 MB rise each, plus 400 MB, is 7,404 MB of the
  8 GB, a thinner margin". The arithmetic is right; the figure is in no source (the frozen
  design and details say only "two at once would need a ceiling of about 3,000 MB each, and
  so smaller plates"). Fix: write "By this guide's own sum, not a measurement: ..." or
  remove the sentence and keep "a thinner margin, not worked out".
- **3.3 The generated list of accepted settings: marked as a proposal, with one claim that
  is not.** Lines 1074-1084 say "This is the proposal", which is right. But line 1077,
  "generated from the pinned Orca's own table of settings by the upgrade command", states as
  fact that the Orca release yields such a table; no source shows that it does, and the
  catalog holds only profile values, not kinds or permitted values. Fix: "generated by the
  upgrade command from the pinned Orca's table of settings, if the release can be made to
  give one, which has not been tried".
- **3.4 The check of each value: stated as the design.** Lines 295-297, "Each accepted value
  is checked against what that setting allows before Orca sees it, and a value that does not
  fit is refused with the setting named". Item 5 does not say this, and today's refusal does
  not name the setting ("These print settings could not be read; choose them from the
  lists."). Fix: "Proposed: each accepted value is checked ...".
- **3.5 The test of configurations against the catalog: marked as a proposal, but it does
  not cover what the plan allows.** Lines 1093-1095, "While the configurations are a fixed
  set kept with the code, the proposal is a test that checks every one of them against the
  catalog". "Kept with the code" is not in decisions item 8 ("a fixed set of
  configurations"), and the plan's "Known future work" lets the owner put a configuration
  into the state bucket by hand, which no test sees. The guide also does not say which
  component holds the test, when the configurations are the front server's and the catalog
  is the slice service's and a component depends only on contracts. Fix: add "A
  configuration the owner places in the state bucket by hand is not covered. Which component
  holds the test is open, since the configurations are the front server's and the catalog is
  the slice service's."

The rule on settings against decisions item 5: **it matches exactly.** Lines 281-288 accept
"every setting Orca allows that is a parameter with a value: a choice from a list, a number,
a piece of text", make all of them "available in the wizard's advanced mode", and refuse the
three kinds: a setting that runs a program, a setting that names a file on the server, and
custom G-code. The example at line 286, "such as a script Orca runs on the finished file",
is the writer's and harmless.

Other differences from the sources:

- **3.6** — Lines 429-430 — "It remembers a slice job for two hours after it ends ..., so a
  page that returns within the life of its sliced file still gets an answer about it" —
  Contradicts decisions item 10: a sliced file now lives until two hours after its last
  print ended, which can be many hours after the slice. Fix: "so a page that returns within
  two hours of the slice's end still gets an answer about it. After that a finished slice is
  known by its sliced file, which the front server keeps (two hours after the slice ended or
  after its last print ended, whichever is later)." Source: decisions item 10; architecture,
  the row "Slice jobs".
- **3.7** — Line 798 — "Later than that, the page opens on the Parts step and says the
  earlier sliced file has expired" — Lost the exception of decisions items 10 and 15: a
  returning page opens on the Send step while its plate is still stored and has a delivery
  job. The row also merges two cases (the record expired; the slice service restarted). Fix:
  "From phase 2: if the slice was waiting or running and was submitted less than two hours
  ago, nothing, the page submits it again by itself. If it had finished, nothing: the page
  finds its sliced file through the front server. Once the sliced file itself has expired,
  the page opens on the Parts step and says so."
- **3.8** — Lines 959-964 — Under "What only the host can prove": "each row of the
  architecture's table of what a restart of the slice container does is a test, run with the
  front server" — The plan builds these in phase 2 on one machine, and the architecture
  ("Keeping it true") runs them "with the rest of the suite". Fix: move the sentence out of
  this paragraph into one of its own: "From phase 2, each row ... is a test that runs on one
  machine with the front server."
- **3.9** — Lines 679 and 1043 — "25 parts of 7.5 MB each is 188.5 MB" and "188.5 MB of
  parts for one user" — 25 times 7,500,084 bytes is 187.5 MB. The 188.5 of details line 742
  includes the megabyte allowed for the form in today's upload, and details' own table
  gives "187 MB uploads". Fix: "187.5 MB" in both places; report the looseness in details
  to its owner.
- **3.10** — Lines 637-638 — "All measurements are from aarch64 Linux machines with 4
  processors" — Details says almost all are from one machine with 4 processors and nine
  plates (the bunnies among them) from another whose processors are not given; line 1026
  has it right. Fix: "from aarch64 Linux machines, almost all from one with 4 processors".
- **3.11** — Lines 376-378 — "Railway after five minutes without data, and Cloudflare after
  125 seconds" — Lost Railway's other rule, in the architecture and details: it closes any
  request after fifteen minutes. A slice job third in line can wait two time limits and run
  a third, twelve minutes, close to that. Fix: add "Railway also closes any request after
  fifteen minutes, whatever it carries; whoever follows the stream opens it again and gets
  the latest report at once."
- **3.12** — Lines 607-608 — "it is wrong in both directions by up to four times" — The
  wording is the contract's, but the guide's own examples show it over by 4.3 times (the
  cube) and under by 6 percent (the hubs); nothing in any source shows it under by four
  times. Fix: "it is wrong in both directions: over by more than four times on a solid
  cube, under on parts with many triangles".
- **3.13** — Lines 256-261 — "A plate configuration that names no printer gets the default
  set" — Lost the rule in the code that such a plate may name only the default set's
  filament and process, or none; any other is refused. Fix: add "and may name no other
  filament or process".
- **3.14** — Lines 992-1005, the phase 2 list — Omits two things the plan and details give
  phase 2: the quiet refusal of new slice jobs while stopping, and the tests of each row of
  the restart table. Fix: add both as bullets.

Omitted from the sources and needed to judge the component:

- **3.15** — The architecture's "To confirm before building on it" lists Railway's limit on
  a request body ("Its documents state none. A 7.5 MB part should pass; one real upload
  settles it"). It bears on the upload of a part and is absent from "Unmeasured". Fix: add
  it there.
- **3.16** — The same section says progress streams may be held back by Cloudflare or
  Railway, with asking for the latest report every second or two as the fallback. Line
  344-345 has the means and not the reason. Fix: one sentence in "Report progress".
- **3.17** — The same section leaves open whether Railway starts the new container before
  stopping the old one. Lines 92-94 require exactly one slice service process behind the
  address, and line 827 has the stopping process "keep answering" while the front server
  fetches. If two overlap, which one the front server reaches is not known. Fix: add to
  "How long a stopping container is given" (line 1048): "Nor is it known whether Railway
  starts the replacement before the old container has stopped; if it does, two slice
  service processes share one address for a time, which this design does not allow for."

## 4. One name per thing, and the design as it is to be

- **4.1** — Lines 130, 445, 512, 629 ("the tests against the real Orca", "the real-Orca
  tests") and 892, 951 ("the upstream check") — One thing under three names, the first used
  760 lines before the defined term. Fix: define at line 130, "the **upstream check** (the
  suite of tests that run the real Orca)", and use "the upstream check" everywhere.
- **4.2** — "Setting", throughout — One name for two things: a slicing setting a user
  chooses in a plate configuration (lines 271-299) and a setting of the slice service that
  is fixed when it is deployed (lines 305-306 "the two counts as settings", 332, 675, 981
  "the one limit that is already a setting", 1009). In a guide whose largest open
  requirement is about settings this misleads. Fix: keep "setting" for the first; call the
  second "a setting of the slice service" at every use, defined once at line 305: "a value
  fixed when the slice service is deployed, not chosen by a user".
- **4.3** — Lines 303, 586, 732, 866, 868, 941 — "caller" — The plan defines **caller** as
  the application that runs the relay. Here it means whoever sends the slice service a
  request. Fix: "the front server" where that is meant (303, 866, 868), "what was sent"
  elsewhere (586, 732), "every failure the front server can be answered with" (941).
- **4.4** — Lines 189, 420, 798, 813, 825-826 — "the page" beside "the wizard" — Two names
  with no sentence relating them. Fix: at line 189, "The page (the wizard, open in one
  browser tab) uploads ...".
- **4.5** — Lines 97 and 717 ("the object stores", "either object store") and 872
  ("long-term storage") — The architecture's terms are the **state bucket** and the **log
  bucket**. Fix: line 717 "no key to the state bucket or the log bucket (the two stores at
  Cloudflare R2 that the front server writes)"; line 872 "writes them to the log bucket".
- **4.6** — Line 228, "at the default profiles", and line 259, "the **default set**" — One
  thing under two names, the first before the definition. Fix: line 228 "with the default
  set of profiles (described below)".
- **4.7** — Lines 1112-1123 — "Taking Orca 2.5.x", "The words in the sentences users read"
  and "More than one slice container" stand under "Undecided". The plan lists all three as
  known future work; nothing in them awaits a decision. Fix: move them under a heading
  "Known future work" at the end, or into "What is built and what is not".
- **4.8** — Lines 1086-1088 — "whether settings may replace values of the filament and
  printer profiles as well as the process profile" is stated as open. Decisions item 5 says
  "every setting Orca allows that is a parameter with a value", with no limit to the process
  profile; the plan's advanced mode "shows every setting of the process profile". The two
  sources pull apart, so the point may already be settled toward all three profiles. Fix:
  state the two readings side by side and what each costs (the printer profile holds the
  start and end G-code and the plate's size, which the placement check trusts), so the owner
  can settle it from the page; do not leave it as a clause.
- **4.9** — Lines 796 ("it is the operator's to fix") and 841 ("The owner runs this
  service alone") — One person under two names. Fix: line 796 "it is for whoever runs the
  service to fix", and the same words at 841.
- **4.10** — Lines 441 ("scratch folder"), 694 and 1044 ("the slice job's folder", "the
  folder of one slice job") and 796 ("working files") — Unclear whether one thing or two.
  In details the slice job's folder holds the uploads and the plate file, and the scratch
  folder is Orca's. Fix: define once at line 441, "a scratch folder inside the slice job's
  own folder", and use each for its own thing.
- **4.11** — Line 1068 — "Plates over about 3,000 MB are refused as too large" — Elsewhere
  such a plate is "stopped" (lines 490, 672), and "refused" means turned away before a slice
  job exists (line 201). Fix: "are stopped as too large".
- **4.12** — Lines 906-910 — History in the body ("The command was run up to 2.5.1 and
  stopped there ...; run down to 2.4.1 ...; and back to 2.4.2 each time"). Fix as under
  heading 1.
- **4.13** — Lines 1061-1072 — The hosted memory ceiling is presented under "Undecided"
  with an options table. The sources state 6,000 MB as proposed and "the owner's to change",
  and the writer's brief has proposed items stated as the design. The table is useful to the
  owner, so it may stay, but the heading should not call it undecided. Fix: retitle "The
  hosted memory ceiling, proposed at 6,000 MB: what the other choice would be".
