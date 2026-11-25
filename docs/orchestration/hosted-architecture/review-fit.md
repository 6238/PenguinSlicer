# Review: does the hosted architecture fit the code it builds on

Written Wed 2026-11-25, Pacific time. An adversarial review of
[the hosted architecture spec](../../specs/2026-11-25-hosted-architecture-design.md)
against [the plan](../../plans/penguin-slicer-plan.md), the guides of
[the slice service](../../../slice/README.md) and
[printer delivery](../../../delivery/README.md), the mockup's
[DECISIONS.md](../../mockups/print-wizard/DECISIONS.md) and the code. Every finding was
checked against the cited lines. No suite was run and no server started.

Paths are relative to the repository root. `relay/` means
`delivery/relay/penguin_delivery_relay/`, `daemon/` means
`delivery/daemon/penguin_delivery_daemon/`, `slice/` means `slice/src/penguin_slice/`.
"Spec" with a line number means the hosted architecture spec.

## Count

| Severity | Findings |
|---|---|
| serious | 3 |
| medium | 10 |
| low | 7 |

Findings are ordered most serious first.

## Serious

### S1. The held sync, as written, breaks the relay's staleness rule and loops while a job is held

**The spec (lines 231-236):** "The relay answers at once when there is a delivery job, a
cancel or a granted start for that daemon, and otherwise after 50 seconds ... The daemon
posts its next sync as soon as one is answered, and at once when the printer's status
changes. ... A daemon whose held sync has not been renewed for two minutes is offline, as
today."

**The evidence.** Four things in the code depend on the sync's cadence, and the spec
names only the two-minute one.

1. A running delivery job is marked stale after 20 s without word from the daemon:
   `STALE_AFTER_SECONDS = 20` (`relay/deliveries.py:75`), applied in `_stale_age`
   (`relay/deliveries.py:388-390`); the word is stamped when a sync arrives
   (`heard`, `relay/deliveries.py:223-227`, called from `relay/relay.py:638`). A sync held
   for 50 s is silence for 50 s. The daemon syncs at once only when the snapshot's `state`
   changes (`daemon/run_loop.py:461-464`), not when the percent, the layer or the time
   left changes, so through a print every delivery job is stale for 30 of every 50
   seconds. A stale report past the start gate is what permits stop-following
   (`relay/relay.py:743-748`), so a healthy print can be given up as
   `delivery.outcome_unknown`. The percent, layer and time left
   (`daemon/printer.py:464-467`) and the printer's own quiet time (`report_age_s`,
   `daemon/printer.py:752`) also reach the relay only with a sync, so the Send step's
   progress would move once in 50 s.
2. While the relay holds a job, every sync is answered with that job again:
   `store_status` returns the job whenever `record.job` is not `None`
   (`relay/relay.py:612-631`), from the hand-out until the daemon's acknowledgement.
   "Answers at once when there is a delivery job" plus "posts its next sync as soon as one
   is answered" is then a loop with no wait, through the download, the upload, the waits
   for the printer (up to ten minutes each, `daemon/run_loop.py:95-98`) and the start
   wait. It runs into `SYNC_LIMIT` (120 a minute, `relay/routes.py:46`), and the daemon
   then stops for the `Retry-After` (`daemon/run_loop.py:478-481`), during which a cancel
   cannot reach it.
3. The daemon's loop does one network thing per pass (`daemon/run_loop.py:513-522`):
   acknowledgements (`_send_due_ack`) and the job's progress, sent each second while a
   job moves (`PROGRESS_SYNC_SECONDS`, `daemon/run_loop.py:58, 452-456`), share that loop
   with the sync. A sync blocked for 50 s delays both. The client's timeout is 20 s
   (`daemon/relay_client.py:84`), so a daemon not yet changed fails every held sync as a
   network error and backs off.
4. "A granted start" is not something the relay tells a daemon. The start gate is the
   daemon's own request, answered in the same exchange (`relay/routes.py:609-631`,
   `relay/relay.py:683-718`). Nothing waits on a sync for it.

`DAEMON_ONLINE_SECONDS` and `STATUS_ONLINE_SECONDS` (120 s, `relay/relay.py:34-35`) are
indeed safe with a 50 s hold; that part of the spec is right.

**Smallest fix.** Hold the sync only while the daemon has no live delivery job (that is
where the 518,000 idle requests are). While a delivery job is live, keep the cadence the
guide states: every 5 s, each second while a job moves. State that the relay answers a
held sync for a job newly offered or a cancel newly asked, not for a job the daemon
already holds, and drop "a granted start". Say that the daemon needs the hold on a
connection of its own, or must abandon it, to send an acknowledgement or a changed
status.

### S2. A flaw in the slice container reaches every printer and every browser, not only two hours of files

**The spec (lines 270-273):** "A flaw there exposes the parts and sliced files of the last
two hours, and nothing else." And (lines 79-81): "In its own container a flaw in Orca
reaches ... no other group's printer."

**The evidence.** The slice container is the only source of every sliced file. On Send
the relay copies whatever stream it is handed and computes the size and SHA-256 from that
same stream (`relay/sliced_files.py:104-129`, called from `relay/routes.py:356-369`); the
daemon checks the download only against those figures and then starts the file. Nothing
between Orca and the printer looks at the content. A slice container taken over through a
hostile STL keeps running until its next restart (the spec keeps it running always, lines
89-90), so from then on it can:

- hand any G-code to every group's printer that prints a plate sliced after the takeover
  (heater and motion commands on a machine in a shop);
- hand any bytes to every browser's Preview step and any JSON as the summary, which the
  wizard's page renders in the origin that holds the sign-in cookie;
- read every later user's parts as they are uploaded, not only the last two hours', and
  send them out, since the spec confines inbound requests only ("accepts requests only
  from the front container");
- write any log lines, which the front container fetches and files in the log bucket as
  the slice service's (spec lines 291-294).

The owner keys it sees are whatever the front container sends; if they are Onshape user
ids, it learns those too.

**Smallest fix.** Replace the sentence with what a takeover reaches (the list above) and
decide the two cheapest limits: the front container treats the sliced file, the summary
and the fetched log lines as hostile input (the page never inserts summary text as HTML;
the owner key is an opaque value derived by the front container, not the Onshape id), and
the slice container has no route out to the internet. Whether a sliced file is checked
before it goes to a printer is then a stated open question for phase 5 instead of an
unstated gap.

### S3. A sign-in that cannot be withdrawn for thirty days is all that guards the printer

**The spec (lines 187-188, 100):** "The cookie holds the user's identity, groups and
Onshape tokens ... Nothing about a session is kept on the server, so a restart signs
nobody out." Lifetime: "Thirty days". And (lines 219-220): "A send is allowed when the
signed-in user's current group has a paired-printer record for the daemon."

**The evidence.** The groups are read once, at sign-in (spec lines 179-180), and live in
the cookie. A user removed from an Onshape company or classroom keeps that group in the
cookie for up to thirty days, and with it the right to send prints, to unpair or re-pair
the printer and to edit the configuration (spec line 28: every user of a group may). The
server keeps no table of sessions, so nothing can end one user's sign-in; the only lever
is a new cookie key, which signs everybody out. The plan's phase 5 list puts this first:
"the caller's sign-in is all that stands between the internet and a print on the H2S"
([the plan](../../plans/penguin-slicer-plan.md), line 406). The spec's Security section
does not mention it.

**Smallest fix.** Read the user's groups from Onshape again on a short clock (each time
the Onshape access token is renewed is the natural moment, and the cookie is rewritten
then anyway) and before a send, a pairing, an unpairing and a configuration edit. State
the longest time a removed user keeps access.

## Medium

### M1. The 120-second abandonment contradicts the mockup's decisions 45 and 46, and the spec's own first paragraph of "Coming back"

**The spec (lines 144-148, 154-155):** "the page finds a running or finished slice job
without having kept its id" and then "A slice job that nobody follows is still cancelled
after 120 seconds, as today: closing the panel during a slice stops the slice, and coming
back starts it again."

**The evidence.** Decision 45: "Close and reopen ... what the server holds stays: this
user's slice job". Decision 46: "When this user's slice is running ... the wizard reopens
on the Preview step" with "Back where you were"
([DECISIONS.md](../../mockups/print-wizard/DECISIONS.md), lines 508-514). The code agrees
with the spec's second statement: a slice job with no subscriber for `ABANDON_GRACE_S`
(120 s) is cancelled and its file discarded (`slice/jobs.py:49, 256-271`), and only an
open `/events` stream counts as a subscriber (`slice/jobs.py:199-229`); a page that polls
`GET /slices/<job>` does not. So a running slice is found on return only within 120 s.
The spec overrides decisions 45 and 46 for a running slice without saying so. Two further
consequences it does not state: the subscriber the slice service sees is the front
container's connection, so the front container must close its stream to the slice service
when the browser's closes, or no slice job is ever abandoned; and decision 29 (leaving
the Preview step leaves the slice running) holds only if the page keeps its stream open
on the other steps.

**Smallest fix.** Say outright that a running slice survives a closed panel for 120 s
only, that this replaces decisions 45 and 46 for a running slice, and what the returning
user sees (the notification's words). Add the two consequences as requirements on the
wizard's server side and page.

### M2. A sliced file kept two hours meets the relay's forty-minute limit, and "Send again" outlives both

**The spec (lines 99, 137-139):** sliced files live "Two hours after the slice ended"; "On
Send, the front container hands the relay a stream of the same file".

**The evidence.** The relay refuses a send more than forty minutes after `sliced_at`
(`SLICE_MAX_AGE_SECONDS = 40 * 60`, `relay/routes.py:37-41, 351-354`;
[the guide](../../../delivery/README.md), lines 972-973). The limit applies only when the
caller passes `sliced_at` (`relay/caller.py:61-63`), and its reason (a file deleted an
hour after it was made) does not apply to a stream, which the relay copies at the send.
The spec does not say which it is. Separately, decision 40 says "A finished or failed
print says so on the card; Send is enabled again for the same sliced plate"
([DECISIONS.md](../../mockups/print-wizard/DECISIONS.md), lines 472-473). A print runs
for hours; by its end the sliced file has expired (two hours after the slice ended, spec
line 99) and the browser has dropped the parts ("Until the plate is sent", spec line 96),
so "Send again" has nothing to send and nothing to slice again from.

**Smallest fix.** State that the front container passes no `sliced_at` (so the
forty-minute limit does not apply to a stream) or that the limit is retired in phase 5.
Decide decision 40: either the sliced file and the parts are kept while the user's
delivery job is live and for a stated time after it ends, or "Send again" is withdrawn.

### M3. Sliced files and parts do exist outside the slice container

**The spec (lines 262-264):** "A part or a sliced file exists on the server only in the
slice container, for two hours at most ... on a disk that is emptied at every restart."

**The evidence.** The spec itself says the relay copies the stream (line 139). That copy
is a file in the relay's spool directory, in the front container
(`relay/sliced_files.py:104-129`), kept for as long as the relay holds the job
(`prune`, `relay/sliced_files.py:156-164`; up to eighteen minutes before the start, and
through the start wait). The front container is the one the internet reaches and the one
that holds every credential. Every part also passes through the front container on its
way to the part store. The sliced file then sits on the daemon's computer and on the
printer, outside any lifetime the spec sets.

**Smallest fix.** Correct the sentence, and add a row to "Where each piece of state
lives": the relay's copy of a sliced file, on the front container's disk, while the relay
holds the job, removed at the next start (`relay/sliced_files.py:84-102`).

### M4. Pairing: "signed as today" hides a change of the relay's key, and three pieces of state are missing

**The spec (lines 214-220):** "The daemon's token is signed with the relay's secret key,
as today, so nothing in the state bucket can be used to start a print or to pose as a
daemon." "Unpairing removes the record, and the daemon's next request is refused."

**The evidence.**

- Today's token carries the pairing code and nothing else that names the daemon
  (`issue_token`, `relay/relay.py:178-185`), and the pairing code is the key of
  everything in the relay: records (`relay/relay.py:1-6, 208-209`), delivery jobs
  (`relay/deliveries.py:108-110`), held files (`relay/sliced_files.py:46-48`), rate
  limits (`code_key`, `relay/routes.py:208-209`), the log's `printer=` tag
  (`relay/relay.py:103-108`) and the caller's interface, where `Team.pairing_code` is
  "the only field the relay trusts" (`relay/caller.py:36-40`) and is forced through
  `normalize_code` (eight Crockford symbols, `relay/routes.py:203-206`,
  `relay/relay.py:122-140`). With the code dead after pairing, all of this moves to the
  daemon's id. The spec's list of changes for printer delivery (lines 321-322) names the
  pairing code and the record only.
- A token is checked "by signature alone" and never expires
  (`relay/routes.py:217-221`, `relay/relay.py:181-183`). Refusing an unpaired daemon's
  next request therefore needs a lookup of the paired-printer record on every daemon
  request, by daemon id. The state bucket holds "one record per group" (spec line 102),
  so that lookup needs an index from daemon id to group, kept in memory and rebuilt from
  the bucket at every start. The table of state has no such row. The same index is what
  stops one daemon being paired to two groups; the spec does not say whether that is
  allowed.
- A pairing code good for fifteen minutes, and whatever proves to the relay that the
  daemon collecting the token is the one that asked for the code, live somewhere. Neither
  is in the table. If they are in the relay's memory, a restart of the front container
  kills every pairing in progress.
- Today a daemon whose token is refused (`401 repair`) blanks it and exchanges its stored
  pairing code again, unattended (`daemon/run_loop.py:471-477`). With single-use codes
  that recovery is gone: a change of the relay's secret key means a person at every
  daemon's computer runs `pair` and types a code. The spec should say so beside "The
  relay's secret key".
- "Nothing in the state bucket can be used to start a print" is true of reading it. A
  credential that can write it can link any group to any daemon id. The front
  container's bucket credential is therefore as strong as the relay's secret key.

**Smallest fix.** Say that the token names the daemon's id; that the relay keeps an index
of paired daemons in memory, loaded from the state bucket at start; add rows for that
index and for pairing codes in progress; state the one-daemon-one-group rule; note the
hand re-pairing after a key change.

### M5. One live slice job per owner key collides with decision 29, with two tabs and with "work does not follow a user"

**The spec (lines 258-260, 150):** "One user may have one slice job running or queued at
a time". "Work does not follow a user to another computer or browser: there the wizard
opens empty."

**The evidence.**

- Decision 29: "a changed plate cancels it and starts a new one"
  ([DECISIONS.md](../../mockups/print-wizard/DECISIONS.md), lines 423-425). A cancelled
  running slice job stays `running` until Orca and its children are gone
  (`slice/jobs.py:231-254`; it answers `cancelling`). The new plate's submission arrives
  in that interval and meets the limit of one. The spec does not say whether a slice job
  being cancelled counts as live.
- The owner key is the user, not the page. Two Onshape tabs, or two computers, share the
  one live slice job and the 25 parts of the part store. The second page's slice is
  refused, or its "changed plate" cancels the first page's slice.
- The list of an owner key's slice jobs is the same on every computer, so on a second
  computer the page is told of a finished slice while its storage holds no plate; "opens
  empty" needs a rule. The spec never says how a page decides that a listed slice job is
  the slice of the plate in its storage (decision 28: "coming back with the same plate").
  The plan asks for "its running or finished slice job and plate configuration"
  ([the plan](../../plans/penguin-slicer-plan.md), lines 270-272), and the list as
  specified returns no plate configuration and no mark of it.

**Smallest fix.** A submission replaces the owner key's live slice job (cancel, then
queue, inside the slice service) instead of being refused. The list returns, for each
slice job, a hash of its plate configuration, and the page opens a slice job only when
that hash matches the plate in its storage.

### M6. Behind Cloudflare and Railway the relay's address rules misfire, and its limits per pairing code do not fit a classroom

**The spec (lines 70-71):** "Cloudflare proxies it and holds no logic of PenguinSlicer's."

**The evidence.** The relay trusts one proxy hop by default (`trusted_proxy_hops=1`,
`relay/app.py:24, 65-67`). Cloudflare in front of Railway's own edge is two. With one
trusted hop, `request.remote_addr` is Cloudflare's address, and every limit keyed on the
address is shared by everybody: the download limit of 30 a minute for all daemons
together (`relay/routes.py:48, 648`) and the fallback key of every request without a
pairing code (`relay/routes.py:162-163, 208-209`). `require_https` is judged from the
same forwarded headers (`relay/routes.py:118-123`).

`STATUS_LIMIT` is 120 a minute per pairing code, sized as "ten open status lines per
team, polling every 5 s" (`relay/routes.py:43`). The spec's group is "an Onshape company
or classroom" (line 28) and the printer-status icon is on every step for every user; a
class of thirty open wizards passes the limit and every one of them gets 429s. The spec
says how the browser follows a delivery job (a stream) but not how the icon gets the
printer's status.

**Smallest fix.** State the number of trusted hops for the hosted relay as a setting of
the deployment, with a check in "To confirm before building on it". Say that the icon is
fed by a stream or that the status limit is per user.

### M7. The spec changes the plan's terms and phases while saying it uses them unchanged

**The spec (lines 8-9):** "the plan, whose terms this document uses unchanged."

**The evidence**, each against [the plan](../../plans/penguin-slicer-plan.md):

- **configuration** (plan line 36) holds "the printers ... the pairing code" and inside
  Onshape "is a configuration file kept in the Onshape account and read at sign-in". The
  spec's configuration is one JSON document per group in the state bucket, holds no
  pairing code, and "Phase 4 ... Nothing here changes" (spec line 339).
- **pairing code** (plan line 58): "An administrator puts it in the configuration". The
  spec's is typed once into PenguinSlicer and kept nowhere.
- **caller** (plan line 57): "it ... knows the pairing code".
- **Phase 3** is "the same on AWS" with "Done when a user ... opens the wizard at its AWS
  address" (plan lines 282-287). The spec hosts on Railway.
- **Onshape sign-in and the app registration** are phase 4 in the plan (lines 66, 96,
  333-334, 351-352). The spec puts both in phase 3 (lines 196-198, 337).

**Smallest fix.** Replace "unchanged" with a short list of what the plan must change when
this spec is agreed: those three terms, phase 3's host and done-when, and the move of
sign-in to phase 3.

### M8. One process for the wizard's server side and the relay: every deploy of the wizard forgets every delivery job

**The spec (lines 81-82):** "The split also keeps Orca's memory spike, and a redeploy of
the slicer, from dropping every daemon's connection."

**The evidence.** "A restarted relay keeps nothing but its secret key: every job,
delivery job and status is in memory and is gone"
([the guide](../../../delivery/README.md), lines 826-834): the caller's page gets
`404 delivery.job_unknown`, and a job that has not passed the start gate is never
started. The front container runs the relay and the wizard's server side in one process
(spec lines 17-18), and the wizard is the code that will change most. So each deploy of
the wizard ends every delivery job before its gate, cuts every user's Send step loose
from a print that goes on, and empties what the mockup's requirements on printer
delivery need kept: who sent the print going on and the end time of the last print
([DECISIONS.md](../../mockups/print-wizard/DECISIONS.md), lines 161-173). The table's
row "As printer delivery's guide says" is accurate but hides how often it will now
happen.

**Smallest fix.** State it in the table's row and under "Why two containers", and either
accept it in words (deploys wait for a printer with no live delivery job) or name the
relay as a third process to split off when it hurts.

### M9. "Every component already writes one JSON line for every transition" is true of the slice service only

**The spec (lines 286, 297-298):** "Every component already writes one JSON line for every
transition of a job." "Every line carries the time, the component, the group, the user
and the ids of the slice job, the delivery job and the daemon it concerns".

**The evidence.** The relay writes text lines of `key=value` pairs
(`log_line`, `relay/routes.py:106-110`; the guide's examples, lines 847-851), with no
time, no user and no group: a printer is named by a hash of its pairing code and a
`team=` number (`relay/routes.py:250-262`). The daemon's log is prose. The slice
service's lines are JSON (`slice/jobs.py:348-371`) but carry no time, user or group, and
the slice service "never interprets" the owner key (spec line 47), so it cannot write a
user or a group. "What changes in each component" lists none of this.

**Smallest fix.** Say that the front container stamps each line with the time, the user
and the group as it gathers it (mapping owner key and daemon id itself), and add "the
relay's log lines become JSON" to printer delivery's changes.

### M10. The development identity cannot be reached where the owner's development servers run

**The spec (lines 193-195):** "It offers the development identity only while it listens
on the loopback address, and refuses to start if it is told to use it on any other
address."

**The evidence.** The plan's phase 2 is "a user on one machine opens the wizard in a
browser" (plan lines 248-250). Where the server runs in a container and the browser on
the host, the server must bind `0.0.0.0` to be reached at the host's `127.0.0.1`; a
server bound to the container's loopback is not reachable from the browser at all. The
rule as written then makes phase 2 unusable in that setup, or pushes it to a real Onshape
app, which the spec defers to phase 3. Loopback is also not proof of privacy: a tunnel or
a proxy on the same machine forwards the internet to it.

**Smallest fix.** Gate the development identity on an explicit setting that the hosted
front container refuses (for example, refused whenever the Onshape client id is set or
the host's own environment marker is present), not on the listening address alone.

## Low

### L1. The slice service's progress stream already keeps itself alive

**The spec (lines 252-253):** "every stream sends a comment line at least every fifteen
seconds while it has nothing to report (the relay's does; the slice service's must be
added)".

**The evidence.** `JobPool.follow` repeats the latest report when 15 s pass with no
change (`WAIT_S = 15.0`, `slice/jobs.py:50, 215-229`), and the route writes it as an
event (`slice/web.py:264-266`). Data flows every 15 s already; it is a repeated progress
event with a fresh `elapsed_s`, not a comment line.

**Smallest fix.** Drop "a comment line on its progress stream" from the slice service's
changes, or say why a comment line is wanted in place of the repeat.

### L2. Not every daemon route carries the daemon's token

**The spec (lines 184-185):** "except the sign-in routes themselves and the daemon's
routes, which carry the daemon's token."

**The evidence.** The download carries none: "the token in the path is the whole
authority" (`relay/routes.py:643-647`). The pairing exchange carries none
(`relay/routes.py:521-544`), and the spec's own step 1, an unpaired daemon asking for a
pairing code, cannot.

**Smallest fix.** List the three exceptions and what guards each (the download token; the
rate limit on asking for a code).

### L3. A user in several groups: the owner key spans them, and the browser names the group

**The spec (lines 172-174):** "A user who belongs to several groups uses one at a time
... The choice is kept in the browser."

**The evidence.** The owner key names the user (spec lines 264-266), so a plate sliced
with one group's configuration is, to the server, sendable to another group's printer
after a switch. The current group arrives from the browser, so every use of it must be
checked against the groups in the cookie; the spec says "the browser cannot name" an
owner key but not this. "The front container reads the document when a user signs in"
(line 164) does not say for which group.

**Smallest fix.** One sentence each: the front container refuses a group that is not in
the cookie; a slice job records the group it was sliced for and a send checks it.

### L4. The count of secrets leaves out the ones that are not on the front container

**The spec (lines 279-282):** "There are five ... All are environment variables of the
front container".

**The evidence.** The spec itself adds a sixth, the read-only credential for the log
bucket (lines 301-303). The daemon's token and the printer's access code sit in the
daemon's configuration file (`daemon/config.py:27-40`), the download token is authority
in a URL (`relay/routes.py:643-647`), and the cookie in the browser holds Onshape tokens.

**Smallest fix.** Say "five on the front container" and list the others with where each
lives.

### L5. Believed facts that the spec builds on but does not list under "To confirm"

- Cloudflare's "125 seconds" for a request (spec line 233) and Railway's fifteen and five
  minutes (lines 250-251). The design holds at 100 s too, but the figure is unchecked.
- The sign-in cookie inside Onshape's panel. A page embedded in another site gets its
  cookie only as `SameSite=None; Secure`, and browsers that block third-party cookies
  drop it. The confirm list has the browser's storage in the panel (lines 353-355) but
  not the cookie, on which "the panel uses the same sign-in" (line 339) rests.
- The slice service on a private network. `serve` runs Flask's development server and
  binds `127.0.0.1` by default (`slice/__main__.py:68, 82`). "The split adds no code"
  (spec line 83) is true only if that server and a `--host` that Railway's private
  network accepts are good enough for the hosted slice container.

**Smallest fix.** Add the three to the confirm list.

### L6. The whole hosted service slices for three users at a time

**The spec (lines 86-88):** "It runs one Orca at a time and queues two slice jobs, as
today."

**The evidence.** `MAX_RUNNING = 1`, `MAX_QUEUED = 2` (`slice/jobs.py:46-47`); a fourth
submission is refused `slice.busy`. With one live slice job per owner key, three users
across all groups fill it, and the third waits up to two slices of 240 s. The pool's own
rule for raising it is `min(vCPU count, memory / peak resident memory of one slice)`
(`slice/jobs.py:35-36`), which 8 GB would satisfy for two. The plan's question "How many
slice jobs run at once" is answered, but the spec should say what a class sees at the end
of a lesson.

**Smallest fix.** State the capacity in a sentence and that the queue's length is a
setting to revisit once the slice container is measured.

### L7. The printer's display name has two homes

**The spec (lines 160-161, 214):** the configuration "holds ... the printer's display
name"; the paired-printer record "holds the daemon's id ... the printer's display name".

**Smallest fix.** Keep it in one of the two.

## What the plan asks that the spec says it settles and does not

The spec says it "settles the questions the plan lists under phase 3 and the security
questions under phase 5" (lines 9-10).

| The plan's question | What the spec says |
|---|---|
| Phase 3: "How a new Orca version is rolled out to the hosted slice service" (plan line 329) | Nothing. A redeploy of the slice container is mentioned only as a reason for the split; what happens to slice jobs running at that moment, and how the upstream check runs against the new image first, are not stated |
| Phase 5: "What the daemon stores on the daemon's computer (the printer's access code and the token, unprotected by the operating system)" (plan lines 410-411) | Nothing |
| Phase 5: daemon telemetry, "what a message must never hold, its size and rate limits" (plan lines 412-413) | Only who sends it, where it is kept, for how long and who reads it. The relay reads no body over 64 kB (`relay/routes.py:81, 266`), which bounds telemetry that "arrives with the daemon's requests" unless that changes |
| Phase 2: the configuration's content | The spec's list (lines 159-161) omits "a colour for each filament for the layer preview", which the mockup requires of the configuration ([DECISIONS.md](../../mockups/print-wizard/DECISIONS.md), lines 191-193) |

**Smallest fix.** Answer each in a sentence or two, or narrow the claim at the top of the
spec to the questions it does answer and name these as left to phases 3 and 5.

## Checked and found right

These statements were checked against the code and stand: one Orca and a queue of two
(`slice/jobs.py:46-47`); a final record kept one hour today (`slice/jobs.py:48`); 7.5 MB
for one part and 188.5 MB for a whole plate's request (`slice/limits.py:14, 26`,
`slice/web.py:55`); 3.5 GB in the guide; a sync every five seconds, 518,400 a month
(`daemon/run_loop.py:57`); the relay's comment line every 15 s (`relay/routes.py:52,
454`); a late stream gets the latest report at once (both components); the relay taking a
stream and copying it once (`relay/caller.py:55-56`); the pairing exchange needing the
caller to present the code first (`relay/relay.py:437-456`); a daemon offline after two
minutes, which a 50 s hold does not disturb (`relay/relay.py:34-35, 256-265`).
