# Map of the hosted architecture's decisions

This file maps each decision in
[the hosted architecture design](../../specs/2026-11-25-hosted-architecture-design.md)
(called "the spec" below) to the one document that now holds its full explanation, and to
any other document that must carry a short gist of it with a link. It is used to check
that nothing the spec decided was lost when its content moved into
[the architecture](../../architecture.md), [the plan](../../plans/penguin-slicer-plan.md),
the guides of [the slice service](../../../slice/README.md),
[printer delivery](../../../delivery/README.md), [the front server](../../../front/README.md)
and [the wizard](../../../wizard/README.md), and [the contracts](../../../contracts/README.md).
The spec is a frozen record: it is not changed, so its line numbers below stay valid.
Where the spec says "the wizard's server side", the homes below apply the split decided
after the spec ([D362](#decided-after-the-spec)): that is the front server, in `front/`,
and each table below follows one section of the spec, in the spec's order.

## Opening of the spec

| Id | Decision | Spec lines | Home | Also needed in |
|---|---|---|---|---|
| D1 | The design gives no time estimates. | 6 | `docs/plans/penguin-slicer-plan.md` | `docs/architecture.md` |
| D2 | The design answers the questions the plan lists under phase 3, and of phase 5's security questions those about who may send to a printer, the pairing code, the relay's secret key, what the daemon keeps on its computer and showing who sent a print. | 28-30 | `docs/plans/penguin-slicer-plan.md` | |
| D3 | The wizard's steps and the preview's drawing are left to phase 2's own design spec. | 30-31 | `docs/plans/penguin-slicer-plan.md` | |
| D4 | The configuration's edit screens are left to a design spec of their own, in no named phase; reading parts from Onshape and what that costs in calls to Onshape are left to phase 4's own design spec. | 31-32 | `docs/plans/penguin-slicer-plan.md` | |
| D5 | The messages of the pairing exchange in detail, and what daemon telemetry holds, are left to phase 5's own design spec. | 32-33 | `docs/plans/penguin-slicer-plan.md` | `delivery/README.md` |

## Short answer

Every item here is a summary of a later section; the rows record the summary as the spec
phrased it.

| Id | Decision | Spec lines | Home | Also needed in |
|---|---|---|---|---|
| D6 | PenguinSlicer runs as two containers on Railway, behind Cloudflare, at `https://penguinslicer.popcornpenguins.com/`; the front server (and from phase 5 the relay, in one process) is the only thing the internet reaches, and the slice container runs one slice service process reachable only from the front server. | 37-41 | `docs/architecture.md` | |
| D7 | The browser holds the user's parts and layout in its own storage; the slice container keeps a copy of each part for two hours after its last use, and the state bucket keeps each sliced file for two hours after its slice. | 42-44 | `docs/architecture.md` | |
| D8 | What must last is in two object stores: the state bucket (each group's configuration and paired-printer record, the sliced files, a record of each delivery job) and the log bucket (log lines). | 45-47 | `docs/architecture.md` | |
| D9 | A deploy at any moment interrupts no user: connections drop briefly and come back by themselves, a slice that was cut off starts again, and a print goes on. | 48-50 | `docs/architecture.md` | |
| D10 | Every user signs in with Onshape, in Onshape's panel and outside it alike; a group is an Onshape company or classroom, and every user of a group may edit its configuration. | 51-53 | `docs/architecture.md` | |
| D11 | Development spends almost none of Onshape's yearly allowance: work on one machine and the tests make no calls, and the hosted service makes two at each sign-in and no others until phase 4. | 54-56 | `docs/architecture.md` | `front/README.md` |
| D12 | A pairing code is used once; after pairing the state bucket holds a record linking a group to its daemon, and nothing read from the state bucket lets anyone start a print. | 57-59 | `docs/architecture.md` | |
| D13 | An idle daemon and the relay exchange about one request a minute and a send still reaches the daemon at once, because the relay holds its answer; during a print the daemon syncs every ten seconds. | 60-62 | `docs/architecture.md` | |
| D14 | The log records every error, the figures needed to size the service and who uses it, and goes to Railway's log view and to files in the log bucket that the project owner's coding agents can read. | 63-65 | `docs/architecture.md` | |
| D15 | Every secret can be replaced, and a planned replacement interrupts nobody who uses PenguinSlicer within a week of it. | 66-67 | `docs/architecture.md` | |

## Terms

| Id | Decision | Spec lines | Home | Also needed in |
|---|---|---|---|---|
| D16 | Term **group**: the users who share one configuration and one printer, one Onshape company or classroom named by Onshape's id for it; a user who belongs to none is a group of one, named by the user's Onshape id. | 75 | `docs/architecture.md` | `front/README.md`, `docs/plans/penguin-slicer-plan.md` |
| D17 | Term **current group**: the one group, of those a user belongs to, whose configuration and printer the user is using now. | 76 | `docs/architecture.md` | |
| D18 | Term **front server**: the one process that runs the server side and, from phase 5, the relay with it; hosted, it runs in its own container on Railway, and in phase 2 it is a process on the one machine (redefined by D362). | 77 | `docs/plans/penguin-slicer-plan.md` | |
| D19 | Term **slice container**: the container on Railway that runs one slice service process and nothing else. | 78 | `docs/architecture.md` | |
| D20 | Term **state bucket**: the object store that holds everything that must outlast a restart of the front server (each group's configuration and paired-printer record, the sliced files, a record of each delivery job). | 79 | `docs/architecture.md` | |
| D21 | Term **log bucket**: the object store that holds log lines and daemon telemetry as files. | 80 | `docs/architecture.md` | |
| D22 | Term **paired-printer record**: one small document per group in the state bucket holding the id of the group's daemon, the printer's display name, who paired it and when, which of the relay's secret keys the daemon's token was last issued under, and, until the daemon has its token, a hash of the pairing code. | 81 | `docs/architecture.md` | `delivery/README.md` |
| D23 | Term **daemon id**: a random id a daemon makes for itself when its `pair` command is run, and keeps; it names the daemon in its token, in the paired-printer record and in the relay's memory. | 82 | `docs/architecture.md` | `delivery/README.md` |
| D24 | Term **progress stream**: the connection, of server-sent events, on which a page follows a slice job or a delivery job. | 83 | `docs/architecture.md` | |
| D25 | Term **part store**: the slice service's folder of uploaded parts, each kept for two hours after it was last used; it is a cache, and the browser's storage is the record of a user's parts. | 84 | `docs/architecture.md` | `slice/README.md` |
| D26 | Term **user key**: the signed-in user's Onshape id, which the front server passes to the slice service with every request; the slice service compares user keys and never interprets them. | 85 | `docs/architecture.md` | `slice/README.md` |
| D27 | Term **development identity**: a fixed made-up user and group that the front server signs in when a setting tells it to, for work on one machine. | 86 | `docs/architecture.md` | `front/README.md` |
| D28 | Term **send**: the request by which a user's page asks the relay to print a sliced file; it creates a delivery job. | 87 | `docs/architecture.md` | |
| D29 | Term **sync**: the request a daemon posts to the relay, carrying the printer's status and its delivery job's progress; the answer tells the daemon what to do. | 88 | `docs/architecture.md` | |
| D30 | Term **held wait**: the time, up to 55 seconds, for which the relay holds back its answer to an idle daemon's sync, ending the moment a delivery job arrives for that daemon. | 89 | `docs/architecture.md` | |

## The shape

| Id | Decision | Spec lines | Home | Also needed in |
|---|---|---|---|---|
| D31 | One address, `https://penguinslicer.popcornpenguins.com/`, serves the wizard's pages, the address a daemon is given for the relay and the redirect address of the Onshape OAuth app. | 106-108 | `docs/architecture.md` | `front/README.md` |
| D32 | The domain's DNS is at Cloudflare, whose proxy hides the host's address and turns away floods of requests; Cloudflare holds no logic of PenguinSlicer's. | 108-109 | `docs/architecture.md` | |
| D33 | The browser and the daemons talk only to the front server, and the front server calls the slice service over Railway's private network, so the slice service's HTTP interface is not reachable from the internet and the browser never makes a cross-origin request. | 110-112 | `docs/architecture.md` | `slice/README.md`, `front/README.md` |
| D34 | There are two containers because Orca reads files strangers upload: the slice container holds no credentials, so a flaw in Orca reaches no sign-in secret and no bucket. | 114-115 | `docs/architecture.md` | `slice/README.md` |
| D35 | The split keeps Orca's memory spike and a deploy of the slice container from cutting off every daemon, and lets a change to the wizard be deployed without touching a running slice; two containers cost what one would, since Railway bills by use. | 116-118 | `docs/architecture.md` | |
| D36 | The split makes the front server pass parts and slice jobs through, fetch each sliced file, and fetch the slice service's log lines from a route of the slice service. | 118-120 | `docs/architecture.md` | `front/README.md`, `slice/README.md` |
| D37 | The buckets are at Cloudflare R2, which gives the three things the design needs of its object store: a credential that only reads one bucket, deleting files after a set number of days, and writing a file only if it has not changed; R2 is storage only, so Cloudflare still runs no logic. | 122-125 | `docs/architecture.md` | |
| D38 | The front server holds the one credential that writes to the buckets; beyond it, only the project's owner can write, through Cloudflare's own console. | 125-126 | `docs/architecture.md` | `front/README.md` |
| D39 | The slice container is allowed 8 GB, the most one container gets on Railway's Hobby plan. | 128-129 | `docs/architecture.md` | `slice/README.md` |
| D40 | Both containers stay running and nothing is started on demand, so a slice never waits for a container to start. | 129-130 | `docs/architecture.md` | |
| D41 | Leaving Railway needs of a host only a private network between the two containers and a view of recent log lines; on AWS that is one EC2 machine running both containers with the slice container's port closed to the outside. | 132-134 | `docs/architecture.md` | |
| D42 | A new Orca version is rolled out as a new image of the slice container, built with the pinned version after the upstream check passes, and deployed like any other change. | 136-137 | `slice/README.md` | `docs/architecture.md` |

### Limits on one slice

| Id | Decision | Spec lines | Home | Also needed in |
|---|---|---|---|---|
| D43 | The slice service stops an Orca that passes the memory ceiling or the time limit, and reports each as an error the wizard explains; both are settings of the slice service. | 141-143 | `slice/README.md` | `wizard/README.md` |
| D44 | The hosted memory ceiling is 6,000 MB (proposed), leaving 2 GB of the slice container for the slice service process, its checks on uploaded parts and the operating system, because Railway stops a container that passes its 8 GB and that would take the waiting slice jobs with it. | 145-148, 169 | `slice/README.md` | `docs/architecture.md` |
| D45 | The memory ceiling's figure is the project owner's to change; a high ceiling costs money only while a heavy plate is slicing, since Railway bills the memory a container holds at each moment. | 148-150 | `slice/README.md` | |
| D46 | The heaviest plate ever measured peaked at 2,569 MB (six Stanford bunnies with supports). | 152-153 | `slice/README.md` | |
| D47 | For plates heavier than any measured, the slice service's estimates of memory and time are extended beyond what was measured. | 153-154 | `slice/README.md` | |
| D48 | The time limit must be long enough that every plate which would finish does finish, and no longer, because a slice that hangs holds up everyone waiting behind it. | 156-157 | `slice/README.md` | |
| D49 | The time limit starts at 240 seconds, until measured on Railway; the slowest plate of the Popcorn Penguins' real parts took 22 seconds, measured on aarch64 machines and on plates far lighter than 6,000 MB. | 157-161, 170 | `slice/README.md` | |
| D50 | The memory ceiling and the time limit are both settled by one set of measurements on the slice container (plates of rising weight up to the memory ceiling, each timed), and the time limit is then set at a few times the slowest plate that finishes. | 161-165 | `slice/README.md` | `docs/architecture.md` |
| D51 | Passing the memory ceiling is the error `slice.out_of_memory`; passing the time limit is the error `slice.timeout`. | 167-170 | `slice/README.md` | `wizard/README.md` |

### How many slices at once

| Id | Decision | Spec lines | Home | Also needed in |
|---|---|---|---|---|
| D52 | How many Orcas run at once and how many slice jobs may wait behind them are settings of the slice service; the hosted service starts with one running and two waiting, changed from what is seen in use. | 174-176 | `slice/README.md` | |
| D53 | The slice container never runs more Orcas than fit in its memory with each at the memory ceiling: with 6,000 MB that is one, and two at once would need a ceiling of about 3,000 MB each; a second Orca would share Orca's processors, not use idle ones. | 179-183 | `slice/README.md` | |
| D54 | A slice that cannot start yet waits, and its user is shown that it is waiting and how many slices are ahead of it. | 184-185 | `slice/README.md` | `wizard/README.md`, `contracts/wizard-front-server.md` |
| D55 | When no more slice jobs may wait, the user is told the slice service is busy and to try again shortly. | 186-187 | `slice/README.md` | `wizard/README.md`, `contracts/wizard-front-server.md` |
| D56 | These stay settings because how many processors Railway gives the slice container, how long real plates take there and how often two users slice at the same moment are not yet known. | 189-191 | `slice/README.md` | |
| D57 | Growing beyond one slice container is later work, outside this design. | 191 | `docs/plans/penguin-slicer-plan.md` | |

### Progress streams

| Id | Decision | Spec lines | Home | Also needed in |
|---|---|---|---|---|
| D58 | The browser follows a slice job and a delivery job as server-sent events, through the front server. | 195-196 | `front/README.md` | `wizard/README.md`, `contracts/wizard-front-server.md` |
| D59 | Railway closes a request after fifteen minutes, or after five without data, and Cloudflare after 125 seconds without data. | 196-197 | `docs/architecture.md` | |
| D60 | Every progress stream sends a comment line at least every fifteen seconds while it has nothing to report. | 197-198 | `slice/README.md` | `front/README.md`, `delivery/README.md` |
| D61 | The page reconnects when a progress stream closes. | 198-199 | `wizard/README.md` | `contracts/wizard-front-server.md` |
| D62 | A progress stream that connects late gets the latest progress report at once. | 199 | `front/README.md` | `slice/README.md`, `delivery/README.md`, `contracts/wizard-front-server.md` |

## Where each piece of state lives

| Id | Decision | Spec lines | Home | Also needed in |
|---|---|---|---|---|
| D63 | Neither container keeps a database or a table of sessions. | 203 | `docs/architecture.md` | |

### One plate, from parts to print

| Id | Decision | Spec lines | Home | Also needed in |
|---|---|---|---|---|
| D64 | When the user adds a part, the page keeps it in the browser's storage and uploads it, and the slice service checks it and keeps it in the part store. | 210-211 | `docs/architecture.md` | |
| D65 | The plate's layout and chosen settings exist only in the browser's storage. | 212-213 | `docs/architecture.md` | |
| D66 | On the Preview step the page sends the front server a plate configuration (layout, settings, the hash of each part) carrying no files, and the slice job waits or runs in the slice container. | 214-217 | `docs/architecture.md` | |
| D67 | When the slice ends, the front server fetches the sliced file from the slice container and stores it in the state bucket. | 218-219 | `docs/architecture.md` | |
| D68 | The page draws the preview from the sliced file, which it fetches through the front server. | 220-221 | `docs/architecture.md` | |
| D69 | From phase 5, on Send the relay writes a record of the delivery job to the state bucket, and the daemon fetches the sliced file through the front server and hands it to the printer. | 222-224 | `docs/architecture.md` | |

### Parts

| Id | Decision | Spec lines | Home | Also needed in |
|---|---|---|---|---|
| D70 | The wizard uploads each part by itself at the moment the user adds it, in one request of at most 7.5 MB (the plate configuration's limit for one part), far under the 100 MB Cloudflare allows a request. | 228-231 | `wizard/README.md` | `contracts/wizard-front-server.md` |
| D71 | The front server passes each uploaded part to the slice service with the user key. | 231-232 | `front/README.md` | `slice/README.md` |
| D72 | The slice service keeps a part in the part store under the user key and the SHA-256 hash of its bytes. | 232-233 | `slice/README.md` | |
| D73 | A plate configuration names each part by its SHA-256 hash. | 233 | `contracts/plate-configuration.md` | `slice/README.md`, `wizard/README.md` |
| D74 | The slice service runs its checks on a part as it arrives, so a part that cannot be sliced is refused on the Parts step, on its own row, before the user has laid anything out. | 237-239 | `slice/README.md` | `wizard/README.md`, `contracts/wizard-front-server.md` |
| D75 | Slicing again uploads nothing: each slice after a change sends only a small plate configuration. | 240-241 | `wizard/README.md` | `contracts/wizard-front-server.md` |
| D76 | A part stays in the part store for two hours after it was last used, and each slice that names it counts as a use. | 243-244 | `slice/README.md` | |
| D77 | The part store is a cache; the browser's storage is the record of the user's parts. | 244-245 | `slice/README.md` | `wizard/README.md` |
| D78 | When a plate configuration names a part no longer in the part store, the slice service answers with an error report listing the missing hashes. | 245-247 | `slice/README.md` | `contracts/wizard-front-server.md` |
| D79 | On that error report the page uploads the missing parts again from the browser's storage and submits again, and the user sees nothing of it. | 247-248 | `wizard/README.md` | `contracts/wizard-front-server.md` |
| D80 | The part store holds at most 25 parts for one user key, the most a plate can use; when a further part arrives the least recently used one is removed, and the page uploads it again if a plate ever names it. | 250-252 | `slice/README.md` | |
| D81 | The part store has a limit on the disk it may take in all; past it, the least recently used parts of any user key are removed. | 252-253 | `slice/README.md` | |
| D82 | The slice service empties the part store when it starts. | 253-254 | `slice/README.md` | |
| D83 | A part is found only under its user key, so two users who upload the same file each have their own entry and nobody can learn whether someone else uploaded a given file. | 256-257 | `slice/README.md` | |

### The sliced file

| Id | Decision | Spec lines | Home | Also needed in |
|---|---|---|---|---|
| D84 | When a slice ends, the front server fetches the sliced file from the slice container and stores it in the state bucket under the user key and the slice job's id. | 261-262 | `front/README.md` | |
| D85 | The state bucket's copy is the one everything uses: the browser fetches it through the front server for the Preview step and the download, and on Send the relay hands it to the daemon. | 262-265 | `front/README.md` | `wizard/README.md`, `delivery/README.md`, `contracts/wizard-front-server.md` |
| D86 | The browser does not store the sliced file and never uploads one, so a printer only ever receives a file the slice service made. | 265-266 | `wizard/README.md` | `front/README.md` |
| D87 | The front server learns that a slice has ended by following every unfinished slice job's progress stream itself, whether or not a page is open. | 268-269 | `front/README.md` | |
| D88 | When the front server starts, it asks the slice service for its slice jobs, follows the unfinished ones and collects each finished one it has not yet stored. | 269-271 | `front/README.md` | `slice/README.md` |
| D89 | A sliced file is 8.8 to 14.1 MB on the plates measured so far, small against the 100 MB Cloudflare allows. | 273-274 | `docs/architecture.md` | |
| D90 | Once the front server has stored a sliced file, the slice container deletes its own copy. | 275 | `slice/README.md` | `front/README.md` |
| D91 | A sliced file can be previewed, downloaded, sent, and sent again after a print, for two hours after its slice ended. | 277-278 | `front/README.md` | `wizard/README.md` |
| D92 | The front server refuses a sliced file older than two hours and deletes it. | 278-279 | `front/README.md` | |
| D93 | A sliced file that a delivery job still needs is kept until the daemon has fetched it. | 279-280 | `front/README.md` | `delivery/README.md` |
| D94 | A one-day R2 deletion rule on the sliced files catches any file the front server failed to delete, so such a file can rest at R2 for up to about two days (R2 counts whole days and removes a file typically within 24 hours after it falls due). | 282-285 | `docs/architecture.md` | `front/README.md` |

### Coming back

| Id | Decision | Spec lines | Home | Also needed in |
|---|---|---|---|---|
| D95 | Once submitted, a slice job runs to its end whether or not anything follows it, through a refresh, a dropped connection or a closed lid (the mockup's decision 46). | 289-292 | `slice/README.md` | `docs/plans/penguin-slicer-plan.md` |
| D96 | A slice whose user never returns holds an Orca until it ends, bounded by the time limit (accepted). | 292-293 | `slice/README.md` | |
| D97 | A user has one unfinished slice job at a time: submitting a plate cancels the user's earlier unfinished slice job, which is what the Preview step does when a plate changes. | 295-297 | `slice/README.md` | `contracts/wizard-front-server.md` |
| D98 | With the wizard open in two tabs, the later slice wins. | 297 | `slice/README.md` | `wizard/README.md` |
| D99 | A page that has lost its state reads the parts, the layout, the chosen settings, the id of the plate's slice job and the time it was submitted from the browser's storage, and asks the front server about that slice job. | 299-301 | `wizard/README.md` | `contracts/wizard-front-server.md` |
| D100 | The slice service remembers a slice job for two hours after it ends, and a finished one is also known by its sliced file in the state bucket. | 301-303 | `slice/README.md` | `front/README.md` |
| D101 | Returning page, slice job still waiting or running: the page shows its progress on the Preview step. | 307 | `wizard/README.md` | `contracts/wizard-front-server.md` |
| D102 | Returning page, slice job finished and its sliced file in the state bucket: the page opens on the Preview step with the result. | 308 | `wizard/README.md` | `contracts/wizard-front-server.md` |
| D103 | Returning page, slice job unknown and submitted less than two hours ago (the slice container restarted): the page uploads the parts and submits the plate again. | 309 | `wizard/README.md` | `contracts/wizard-front-server.md` |
| D104 | Returning page, slice job ended in an error: the page shows the error on the Preview step, as when the page was open. | 310 | `wizard/README.md` | `contracts/wizard-front-server.md` |
| D105 | Returning page, slice job cancelled by a later slice of the same user: the page shows the plate on the Preview step and offers to slice it, and does not submit by itself, so two pages cannot cancel each other in turn. | 311 | `wizard/README.md` | `contracts/wizard-front-server.md` |
| D106 | Returning page, slice job unknown and submitted more than two hours ago (its sliced file has expired): the page opens on the Parts step with one line saying the earlier plate's sliced file has expired (the mockup's decision 48), and drops the stored parts. | 312 | `wizard/README.md` | `contracts/wizard-front-server.md` |
| D107 | From phase 5, a returning page whose plate has a delivery job opens on the Send step. | 314 | `wizard/README.md` | `contracts/wizard-front-server.md` |
| D108 | Work does not follow a user to another computer or browser: there the wizard opens empty. | 316-317 | `wizard/README.md` | |
| D109 | Chrome keeps the storage of a page inside Onshape's panel apart from the same page opened directly, so work begun in one does not appear in the other. | 317-319 | `wizard/README.md` | |

### The configuration

| Id | Decision | Spec lines | Home | Also needed in |
|---|---|---|---|---|
| D110 | A group's configuration is one JSON document in the state bucket, read whole and written whole. | 323-324 | `contracts/configuration.md` | `front/README.md`, `docs/architecture.md` |
| D111 | The configuration holds the group's filaments and the units of uploaded files; for each filament the colour for the layer preview and the profiles to slice with, by Orca's names, with any settings that replace a profile's own. | 324-326 | `contracts/configuration.md` | |
| D112 | The configuration holds no secret. | 326 | `contracts/configuration.md` | `docs/architecture.md` |
| D113 | A group with no document gets a built-in default configuration, so a new group can slice without setting anything up. | 326-328 | `front/README.md` | `contracts/configuration.md` |
| D114 | The front server reads the configuration when a user signs in and again when the wizard asks. | 330 | `front/README.md` | `contracts/wizard-front-server.md` |
| D115 | An edit writes the whole document on the condition that it has not changed since it was read, so two users editing at once cannot silently overwrite each other; the second is told to reload. | 330-332 | `front/README.md` | `wizard/README.md`, `contracts/wizard-front-server.md` |
| D116 | Every edit of the configuration writes a log line with the user's name and what changed. | 333 | `front/README.md` | |
| D117 | The edit screens are a feature of their own; until they exist, a group uses the default configuration or a document the project's owner puts into the state bucket through Cloudflare's console, following the annotated example in the document's contract. | 335-337 | `docs/plans/penguin-slicer-plan.md` | `contracts/configuration.md` |
| D118 | The wizard's header names the current group, as the mockup's "Config:" line does, and the user changes it there. | 339-341 | `wizard/README.md` | |
| D119 | The current group is kept in the browser and sent with each request, and the front server accepts it only if the sign-in cookie lists that group among the user's. | 341-343 | `front/README.md` | `wizard/README.md`, `contracts/wizard-front-server.md` |

## Sign-in

| Id | Decision | Spec lines | Home | Also needed in |
|---|---|---|---|---|
| D120 | Every user signs in with Onshape's OAuth, the same way in Onshape's panel and outside it, through one Onshape OAuth app. | 347-348 | `front/README.md` | `docs/architecture.md` |
| D121 | Onshape tells the front server who the user is and which companies and classrooms they belong to; those are the user's groups, or the user alone when there are none. | 348-350 | `front/README.md` | |
| D122 | No other sign-in is offered, so PenguinSlicer keeps no accounts and no passwords. | 350-352 | `front/README.md` | `docs/architecture.md` |
| D123 | Every route of the front server refuses a request without a signed-in user, except the sign-in routes, the daemon's routes (which carry the daemon's token) and the one request by which a daemon without a token offers its pairing code. | 354-357 | `front/README.md` | `delivery/README.md` |
| D124 | The pairing-code offer is limited to sixty a minute for the whole relay and also counted for each address. | 357-358 | `delivery/README.md` | |
| D125 | A sign-in sets one encrypted cookie holding the user's identity, groups and Onshape tokens, lasting thirty days so that signing in, which costs calls to Onshape, is rare. | 360-362 | `front/README.md` | |
| D126 | Nothing about a session is kept on the front server, so a restart signs nobody out. | 362-363 | `front/README.md` | `docs/architecture.md` |
| D127 | Onshape's access token lasts an hour and is renewed with its refresh token only when a call to Onshape needs one (nothing before phase 4 unless the app is public by then, when reading the groups again does), and the renewed tokens are written back to the cookie. | 363-366 | `front/README.md` | |

### Calls to Onshape

| Id | Decision | Spec lines | Home | Also needed in |
|---|---|---|---|---|
| D128 | Until the OAuth app is public in Onshape's App Store, its calls count against the owning account's yearly allowance: 2,500 a year on a free or education account. | 370-372 | `front/README.md` | |
| D129 | The project's owner intends to make the app public; until then, development and testing with users must fit inside that allowance with room to spare. | 372-373 | `docs/plans/penguin-slicer-plan.md` | `front/README.md` |
| D130 | The rule is that nothing calls Onshape that can be done without it. | 373-374 | `front/README.md` | `docs/plans/penguin-slicer-plan.md` |
| D131 | Groups are read at sign-in: a person with no cookie signs in and their groups are read then. | 376-377 | `front/README.md` | |
| D132 | How often a signed-in user's groups are read again is a setting, "never" until the app is public, so the groups in the cookie stand until the cookie ends. | 377-379 | `front/README.md` | |
| D133 | A user removed from an Onshape company keeps its configuration and printer for up to thirty days; once the app is public the setting becomes one day, and such a user loses both within a day (accepted). | 381-383 | `front/README.md` | `docs/architecture.md` |
| D134 | A user added to an Onshape company after signing in does not see the new group until they use the "sign in again" action beside the current group's name in the wizard's header, which reads the groups afresh for two calls. | 384-386 | `wizard/README.md` | `front/README.md`, `contracts/wizard-front-server.md` |
| D135 | Work on one machine with the development identity, and the automated tests with their stand-in for Onshape, make no calls to Onshape. | 392-393 | `front/README.md` | |
| D136 | A sign-in to the hosted service costs 2 calls, once in thirty days for each browser; reading a user's groups again costs none until the app is public. | 394-395 | `front/README.md` | |
| D137 | Reading parts from Onshape in phase 4 costs several calls for each part, counted in phase 4's design before it is built. | 396 | `docs/plans/penguin-slicer-plan.md` | `front/README.md` |
| D138 | Until phase 4, twenty people using the hosted service for two months spend about 80 calls. | 398-399 | `front/README.md` | |
| D139 | The front server writes a log line for each call it makes to Onshape, and the command that reads the log bucket reports the year's total. | 401-403 | `front/README.md` | `docs/architecture.md` |

### Requests from other sites

| Id | Decision | Spec lines | Home | Also needed in |
|---|---|---|---|---|
| D140 | Every route that changes something on the strength of the cookie also requires a header that only the wizard's own page can set, and checks the request's origin. | 407-409 | `front/README.md` | `wizard/README.md`, `contracts/wizard-front-server.md` |
| D141 | No route allows cross-origin requests. | 409 | `front/README.md` | |
| D142 | The sign-in callback checks the value it sent out. | 409-410 | `front/README.md` | |
| D143 | The pages may be embedded by Onshape only. | 410 | `front/README.md` | |

### On one machine

| Id | Decision | Spec lines | Home | Also needed in |
|---|---|---|---|---|
| D144 | With no Onshape app to redirect to, the front server signs in the development identity when a setting tells it to. | 414-415 | `front/README.md` | |
| D145 | The command that launches the hosted front server never sets the development identity's setting, and the front server refuses to start with it when it finds itself on Railway or finds Onshape credentials in its environment. | 415-417 | `front/README.md` | |

### Browsers

| Id | Decision | Spec lines | Home | Also needed in |
|---|---|---|---|---|
| D146 | Safari is not supported, in Onshape's panel or outside it: nothing is designed or tested for it. | 421-422 | `wizard/README.md` | |
| D147 | Inside Onshape's panel, sign-in and the stored parts depend on Chrome allowing cookies and storage to an embedded page. | 422-423 | `wizard/README.md` | `front/README.md` |

## Printers

### Pairing

| Id | Decision | Spec lines | Home | Also needed in |
|---|---|---|---|---|
| D148 | The daemon's `pair` command makes a pairing code and a daemon id, shows the code, and offers both to the relay every thirty seconds. | 431-433 | `delivery/README.md` | |
| D149 | The relay remembers which daemon is offering which code in its memory only. | 433-434 | `delivery/README.md` | |
| D150 | When a signed-in user types a code that a daemon is offering, the relay writes the paired-printer record for the user's current group to the state bucket, naming that daemon and holding a hash of the code. | 435-437 | `delivery/README.md` | `front/README.md`, `contracts/wizard-front-server.md` |
| D151 | When no daemon is offering the typed code, the user is told at once that no daemon is showing that code and to try again in a moment. | 437-438 | `delivery/README.md` | `wizard/README.md`, `contracts/wizard-front-server.md` |
| D152 | The daemon's next offer is answered with its token provided the code matches the hash in the record; the hash is then removed and the code is dead. | 439-441 | `delivery/README.md` | |
| D153 | A pairing code is good for fifteen minutes; a daemon still unpaired then makes a new one. | 443 | `delivery/README.md` | |
| D154 | The daemon's token names the daemon and its group and is signed with the relay's secret key, so nothing read from the state bucket lets anyone start a print or, once the daemon has its token, pose as a daemon. | 445-447 | `delivery/README.md` | `docs/architecture.md` |
| D155 | A wrong pairing code gets the same answer whatever was wrong with it, and attempts are limited for each user. | 448-449 | `delivery/README.md` | |

### Sending and unpairing

| Id | Decision | Spec lines | Home | Also needed in |
|---|---|---|---|---|
| D156 | A send is accepted when the signed-in user's current group has a paired-printer record, and its delivery job goes to the daemon that record names. | 453-454 | `delivery/README.md` | `front/README.md`, `contracts/wizard-front-server.md` |
| D157 | A daemon holds one delivery job at a time. | 454-455 | `delivery/README.md` | |
| D158 | A delivery job's record is kept for a day after the delivery job ends, so the Send step and the printer-status icon can show how the last print ended. | 455-457 | `delivery/README.md` | `wizard/README.md` |
| D159 | Unpairing removes the paired-printer record; the daemon's next request is refused, and the daemon says it has been unpaired and waits for `pair` to be run again. | 459-460 | `delivery/README.md` | |

### A daemon that was off

| Id | Decision | Spec lines | Home | Also needed in |
|---|---|---|---|---|
| D160 | A daemon whose computer was restarted or switched off for any length of time reconnects and works once started again, with no pairing again. | 464-465 | `delivery/README.md` | |
| D161 | Everything the daemon needs to reconnect is in one settings file on its computer (the relay's address, its daemon id and token, the printer's address, serial number and access code), readable only by the daemon's own user. | 467-469 | `delivery/README.md` | `docs/architecture.md` |
| D162 | The daemon's token has no end date: the relay accepts it by its signature and the paired-printer record however long the daemon was silent, except after a replacement of the relay's secret key while the daemon was off for more than a week. | 470-473 | `delivery/README.md` | |
| D163 | While the daemon is silent the printer-status icon shows Offline and Send is disabled; the daemon's first sync puts both back. | 474-475 | `delivery/README.md` | `wizard/README.md` |
| D164 | A print running when the computer went off goes on at the printer; the daemon keeps a note of the print it started in a file beside its settings file, so when started again it follows that print and does not start it a second time. | 476-479 | `delivery/README.md` | |
| D165 | Starting the daemon, at boot or after it stops, is the job of whoever runs that computer and not of PenguinSlicer. | 481-482 | `delivery/README.md` | |
| D166 | A daemon that is a single file installing itself to start at boot is possible later work; this design does not include it and does not depend on it. | 482-483 | `docs/plans/penguin-slicer-plan.md` | `delivery/README.md` |

### How often a daemon talks to the relay

| Id | Decision | Spec lines | Home | Also needed in |
|---|---|---|---|---|
| D167 | The daemon opens no port; everything passes through the sync, which carries the printer's latest status and the progress of the delivery job it holds, and whose answer carries a delivery job to fetch, a cancel, or nothing. | 487-493 | `delivery/README.md` | |
| D168 | While the printer is idle the daemon syncs once for each held wait and again at once when it is answered, so a send reaches it immediately, the idle printer's information is at most about a minute old, and it makes about one request a minute. | 499 | `delivery/README.md` | |
| D169 | While taking a delivery job (fetching the file, uploading it to the printer, starting it) the daemon syncs each second, so the Send step moves smoothly and a cancel reaches it within a second. | 500 | `delivery/README.md` | |
| D170 | While the printer is printing, whoever started the print, the daemon syncs every 10 seconds, so the percentage and time left are at most 10 seconds old (six requests a minute). | 501 | `delivery/README.md` | |
| D171 | When the printer changes state (idle, printing, paused, failed, finished, offline) the daemon syncs at once, whatever else is going on. | 502 | `delivery/README.md` | |
| D172 | While the printer is idle and the daemon has no delivery job, the relay answers a sync the moment a delivery job arrives for that daemon, and otherwise after 55 seconds, inside Cloudflare's 125 seconds and Railway's five minutes without data. | 504-508 | `delivery/README.md` | `docs/architecture.md` |
| D173 | The daemon keeps the held sync on a thread of its own and goes on watching the printer; when the printer's state changes during a held sync it posts a further sync without waiting for the held one. | 510-512 | `delivery/README.md` | |
| D174 | Nothing is held during a print: the relay refuses a send to a printer that is printing, whether PenguinSlicer sent the print or someone started it at the printer's screen. | 514-517 | `delivery/README.md` | `wizard/README.md` |
| D175 | A daemon is online if its last sync was within 2 minutes; past that the printer-status icon shows Offline and Send is disabled. | 523, 526-527 | `delivery/README.md` | |
| D176 | A running delivery job's report is fresh if the daemon's last sync was within 40 seconds; past that it is marked stale, and that is how long a daemon that died during a print goes unnoticed. | 524, 527-529 | `delivery/README.md` | |
| D177 | A stale delivery job whose print was started may be given up by the user ("stop following"), which lets the relay accept the next send once the daemon is back and the printer is idle. | 524 | `delivery/README.md` | `wizard/README.md`, `contracts/wizard-front-server.md` |
| D178 | After a restart of the front server every held sync closes at once, and each daemon waits a short random time before it syncs again so they do not all arrive together. | 531-533 | `delivery/README.md` | |
| D179 | The front server spends one thread on every idle daemon; set to 100 threads, it has room for about fifty idle daemons beside users' requests and progress streams. | 535-537 | `front/README.md` | `delivery/README.md`, `docs/architecture.md` |
| D180 | A small asynchronous server may later take over the held-wait route and hold thousands of daemons, decided when the number of daemons calls for it. | 537-539 | `docs/plans/penguin-slicer-plan.md` | `front/README.md` |

## Reading what happened

| Id | Decision | Spec lines | Home | Also needed in |
|---|---|---|---|---|
| D181 | The log must answer, without seeing a user's screen or computer, what went wrong, whether the service is the right size, and who is using it. | 543-545 | `docs/architecture.md` | |

### What is written

| Id | Decision | Spec lines | Home | Also needed in |
|---|---|---|---|---|
| D182 | Every error a user is shown is logged with its code (such as `slice.out_of_memory`), the user key and name, the group and the job it belongs to, so errors can be counted by kind. | 551-552 | `docs/architecture.md` | `slice/README.md`, `delivery/README.md`, `front/README.md` |
| D183 | Every exception is logged with its stack trace, including one no user saw because the request was tried again. | 553-554 | `docs/architecture.md` | `slice/README.md`, `delivery/README.md`, `front/README.md` |
| D184 | Every refusal is logged: no room for a slice job to wait, a limit on the rate of requests, a failed sign-in, a wrong pairing code, a request for something that belongs to another user. | 555-556 | `docs/architecture.md` | `slice/README.md`, `delivery/README.md`, `front/README.md` |
| D185 | Every start of a container is logged with the version that started. | 557 | `docs/architecture.md` | |
| D186 | A daemon's errors arrive as daemon telemetry with its requests. | 558 | `delivery/README.md` | `docs/architecture.md` |
| D187 | Every component writes one log line for every transition of a job, and the front server writes one for every call it makes to Onshape. | 560-562 | `docs/architecture.md` | |
| D188 | The line that ends a slice job carries the number of parts, the bytes and measurements (triangles, dimensions, volume) of each, the number of instances, how long it waited, how long Orca ran, Orca's peak memory beside the memory ceiling and beside the slice service's estimate, and the bytes of the sliced file. | 566 | `slice/README.md` | |
| D189 | The line that ends a delivery job carries how long the file took to reach the printer, how long the print ran, and how it ended. | 567 | `delivery/README.md` | |
| D190 | A slice that passes 80 percent of the memory ceiling or of the time limit also writes a line marked as a warning. | 569-570 | `slice/README.md` | |
| D191 | Once a minute each container writes one line: the memory it holds, the slices running and waiting, and, for the front server, the connections held open and the threads in use. | 572-575 | `docs/architecture.md` | `slice/README.md`, `front/README.md` |
| D192 | Each sign-in writes a line with the user key, the user's name and their groups. | 577-578 | `front/README.md` | `docs/architecture.md` |
| D193 | Every log line about a slice or a send carries the user key and the current group. | 578-579 | `docs/architecture.md` | `front/README.md`, `delivery/README.md` |

### Where it goes

| Id | Decision | Spec lines | Home | Also needed in |
|---|---|---|---|---|
| D194 | Railway's log view shows each container's lines as they are written and keeps them seven days. | 583-584 | `docs/architecture.md` | |
| D195 | The log bucket keeps log lines ninety days, after which R2 deletes them. | 585-586 | `docs/architecture.md` | |
| D196 | The front server gathers its own lines and the relay's, fetches the slice service's from a route on the private network (the slice container has no credential to write them), and writes them to the log bucket as a new file about once a minute, files named by date and component. | 586-590 | `front/README.md` | `slice/README.md`, `docs/architecture.md` |
| D197 | Each log file is newline-separated JSON, one object per log line, each carrying the time, the component, and whichever of the group, user key, slice job, delivery job and daemon it concerns. | 592-595 | `docs/architecture.md` | |
| D198 | A user's name is written at sign-in and on an error, and found for any other line by its user key. | 595-596 | `docs/architecture.md` | |
| D199 | The front server adds the group to the slice service's log lines as it gathers them, since the slice service knows only the user key. | 596-597 | `front/README.md` | |

### Reading it

| Id | Decision | Spec lines | Home | Also needed in |
|---|---|---|---|---|
| D200 | One command, kept in the repository, reads the log bucket: it pulls everything about one group, user, daemon or job, and reports errors counted by code, users and groups active each day, slices and prints for each group, the busiest hours, slices that came near a limit, and the year's calls to Onshape. | 601-604 | `docs/architecture.md` | |
| D201 | The project owner's coding agents read the log bucket with the read-only credential, which cannot read the state bucket. | 606-607 | `docs/architecture.md` | |
| D202 | No log line holds a secret, a token, a pairing code or a part's geometry; log lines do hold users' names and part names, so the log bucket is private. | 609-610 | `docs/architecture.md` | |

## All the state, in one table

| Id | Decision | Spec lines | Home | Also needed in |
|---|---|---|---|---|
| D203 | Parts, layout, chosen settings, the current group, and the plate's slice job id and submission time live in the browser's storage until the page, on opening, finds the plate's sliced file expired (the current group until the user changes it), unaffected by any restart. | 620 | `docs/architecture.md` | `wizard/README.md` |
| D204 | Who is signed in, their groups and Onshape tokens live in an encrypted cookie in the browser for thirty days, unaffected by any restart. | 621 | `docs/architecture.md` | |
| D205 | Uploaded parts live in the part store for two hours after last use; a slice container restart loses them and the page uploads them again, unasked. | 622 | `docs/architecture.md` | |
| D206 | Slice jobs live in the slice service process's memory until two hours after the slice ends; a restart loses them, the page submits a waiting or running plate again, unasked, and a finished one is known by its sliced file. | 623 | `docs/architecture.md` | |
| D207 | A sliced file not yet collected lives on the slice container's disk for the moments until the front server has stored it; a restart loses it and that slice runs again. | 624 | `docs/architecture.md` | |
| D208 | Sliced files live in the state bucket for two hours after the slice ended, or until the daemon has fetched one a delivery job needs, and are kept across restarts. | 625 | `docs/architecture.md` | |
| D209 | The configuration lives in the state bucket, one document per group, until edited, and is kept across restarts. | 626 | `docs/architecture.md` | |
| D210 | The paired-printer record lives in the state bucket, one per group, until unpaired, and is kept across restarts. | 627 | `docs/architecture.md` | |
| D211 | Delivery jobs live in the state bucket, one record each, until a day after the delivery job ends, and are kept across restarts. | 628 | `docs/architecture.md` | |
| D212 | Printer status and the progress of a print live in the relay's memory until the next sync replaces them; a restart loses them and the daemon's next sync brings them back within seconds. | 629 | `docs/architecture.md` | |
| D213 | Pairing codes that daemons are offering live in the relay's memory for fifteen minutes at most; a restart loses them and they come back within half a minute as each daemon offers again. | 630 | `docs/architecture.md` | |
| D214 | Log lines and daemon telemetry live in the log bucket for ninety days and are kept across restarts, except the last minute before a crash, which stays only in Railway's log view (seven days). | 631 | `docs/architecture.md` | |

## Restarts and deploys

| Id | Decision | Spec lines | Home | Also needed in |
|---|---|---|---|---|
| D215 | The project is deployed continuously, and a deploy at any moment interrupts no user: a user may see a pause while the container comes back and clients reconnect, no work is lost, and a print goes on. | 635-639 | `docs/architecture.md` | `docs/plans/penguin-slicer-plan.md` |
| D216 | Two things can take longer than the pause: a slice that was cut off runs again from its start, and a pairing code typed just after a restart has to be typed again. | 639-641 | `docs/architecture.md` | |

### What a restart does

| Id | Decision | Spec lines | Home | Also needed in |
|---|---|---|---|---|
| D217 | Slice container restart, a slice waiting or running: progress starts again; an open page uploads its parts again from the browser's storage and submits the same plate, unasked, and a closed page does so when next opened. | 649 | `docs/architecture.md` | `wizard/README.md` |
| D218 | Slice container restart, a slice that had finished: the user sees nothing, since the sliced file is in the state bucket. | 650 | `docs/architecture.md` | |
| D219 | Slice container restart, a print being sent or printing: the user sees nothing, since printer delivery does not pass through the slice container. | 651 | `docs/architecture.md` | |
| D220 | Front server restart, any page open: its requests pause and its progress stream reconnects, and nobody is signed out because the cookie's key is a setting of the front server. | 657 | `docs/architecture.md` | |
| D221 | Front server restart, a slice running: it keeps running in the slice container, the page shows its progress again once reconnected, and the front server, having asked for the slice jobs at start, stores the sliced file when the slice ends. | 658 | `docs/architecture.md` | |
| D222 | Front server restart, a delivery job waiting for its daemon: the daemon's next sync is accepted (its token still verifies) and receives the delivery job from its record in the state bucket, then fetches the sliced file through the front server from the state bucket. | 659 | `docs/architecture.md` | |
| D223 | Front server restart, a print running: it goes on, and the printer-status icon and Send step are blank until the daemon's next sync, within ten seconds of the front server answering again. | 660 | `docs/architecture.md` | |
| D224 | Front server restart, a pairing code just typed: the paired-printer record is already in the state bucket, and the daemon gets its token at its next offer, checked against the record. | 661 | `docs/architecture.md` | |
| D225 | Front server restart, a pairing code typed in the half minute after: the user is told, as for any wrong code, that no daemon is showing that code and to try again in a moment. | 662 | `docs/architecture.md` | |
| D226 | The records of delivery jobs are in the state bucket, not the relay's memory, because a daemon told the relay no longer knows its delivery job treats it as finished and drops it. | 664-666 | `delivery/README.md` | `docs/architecture.md` |
| D227 | Before a daemon sends the printer the start command it asks the relay, which allows it once for each delivery job, and the record holds whether that was allowed, which keeps a print from starting twice. | 666-668 | `delivery/README.md` | |
| D228 | A crash (not a deploy) also loses the last minute of log lines, which stays only in Railway's log view, and a slice whose sliced file was not yet stored, which runs again. | 670-672 | `docs/architecture.md` | |

### What makes a deploy cheap

| Id | Decision | Spec lines | Home | Also needed in |
|---|---|---|---|---|
| D229 | Only the container that changed is deployed: each is built from its own folders of the repository, so a change to the wizard does not restart the slice container, nor the reverse. | 678-680 | `docs/architecture.md` | |
| D230 | The slice container, asked to stop, finishes the slice it is running and waits for the front server to fetch the sliced file. | 681-683 | `slice/README.md` | `docs/architecture.md` |
| D231 | The front server, asked to stop, finishes the uploads and downloads in progress, closes its progress streams and answers its held syncs, so pages and daemons reconnect to its replacement. | 683-685 | `front/README.md` | `delivery/README.md`, `docs/architecture.md` |
| D232 | Each container has the time Railway allows a stopping container; a slice still waiting when the slice container stops is submitted again by its page. | 686-687 | `docs/architecture.md` | |
| D233 | The daemon waits and tries again when the relay does not answer. | 688-689 | `delivery/README.md` | |
| D234 | The page retries every request it makes, so a request that falls in the gap of a deploy is repeated and the user sees a pause, not an error. | 689-690 | `wizard/README.md` | `contracts/wizard-front-server.md` |

### Old and new versions together

| Id | Decision | Spec lines | Home | Also needed in |
|---|---|---|---|---|
| D235 | Every change must keep a page loaded before the deploy, an installed daemon and a record written by the old front server working; this is the rule most easily broken by accident. | 694-696 | `docs/architecture.md` | |
| D236 | Every answer of the front server carries the front server's version. | 698-699 | `front/README.md` | `contracts/wizard-front-server.md` |
| D237 | A page that sees a newer front server version reloads itself at the next moment when nothing is in flight, losing nothing because its state is in the browser's storage. | 699-701 | `wizard/README.md` | `contracts/wizard-front-server.md` |
| D238 | An installed daemon, which may be much older than the relay, keeps working: a change to the relay may add to what it sends a daemon, and may not remove or change what an installed daemon relies on. | 702-704 | `docs/architecture.md` | `delivery/README.md` |
| D239 | A record in the state bucket written by the old front server is read by the new one, and each record carries the number of its format. | 705-706 | `docs/architecture.md` | `contracts/README.md` |

### Keeping it true

| Id | Decision | Spec lines | Home | Also needed in |
|---|---|---|---|---|
| D240 | Each row of the two tables under "What a restart does" is a test that runs with the rest of the suite, restarting the container at that moment and checking the result. | 710-711 | `docs/architecture.md` | |
| D241 | Tests of the same kind run the previous version's page and daemon against the new front server. | 711-712 | `docs/architecture.md` | |
| D242 | After each deploy a short scripted check runs against the hosted service. | 712-713 | `docs/architecture.md` | |

## Security

| Id | Decision | Spec lines | Home | Also needed in |
|---|---|---|---|---|
| D243 | Only users signed in with Onshape may use the service. | 717 | `docs/architecture.md` | |
| D244 | One unfinished slice job per user, bounded memory and time, and at most 25 parts per user key together keep one user from taking every place a slice job may wait in or filling the slice container's disk. | 717-720 | `docs/architecture.md` | `slice/README.md` |
| D245 | Limits on the rate of requests are counted for the signed-in user or the daemon. | 720-721 | `delivery/README.md` | `front/README.md`, `docs/architecture.md` |
| D246 | The pairing-code offer, which has neither a user nor a daemon, is counted for the address Cloudflare reports it came from as well as for the whole relay, so one stranger cannot use up everyone's offers. | 721-724 | `delivery/README.md` | `docs/architecture.md` |
| D247 | Outside the browser a part exists only in the slice container, for two hours after its last use, and a sliced file is in the state bucket for two hours after its slice, or up to about two days if the front server fails to delete it. | 726-729 | `docs/architecture.md` | |
| D248 | The state bucket is private: the front server's credential reads it, and otherwise only the project's owner. | 729-730 | `docs/architecture.md` | |
| D249 | A user reaches only their own parts, slice jobs and sliced files, because the front server sets the user key from the cookie and the browser cannot name one. | 730-732 | `front/README.md` | `slice/README.md`, `docs/architecture.md`, `contracts/wizard-front-server.md` |
| D250 | Log lines carry a part's name, size in bytes and measurements, never its geometry. | 732 | `docs/architecture.md` | |
| D251 | Users of one group see each other's names and a one-line description of a plate that is printing, on the printer-status icon. | 733-734 | `docs/architecture.md` | `wizard/README.md` |
| D252 | Orca and the slice service's own checks run in the slice container, which holds no credentials and accepts requests only from the front server. | 736-738 | `docs/architecture.md` | `slice/README.md` |
| D253 | Orca runs as a Unix user of its own that can write only the scratch folder of its slice job, so a flaw in Orca cannot alter the slice service or reach another slice job's files. | 738-740 | `slice/README.md` | `docs/architecture.md` |
| D254 | Accepted risk: a flaw in the slice service itself could, until the slice container restarts, read every part uploaded and hand the front server any file as a sliced file, which would be stored and printed. | 740-743 | `docs/architecture.md` | |
| D255 | The slice container can call the front server over the private network, where it meets the same sign-in as anyone else. | 743-744 | `docs/architecture.md` | |
| D256 | The aim is that nobody outside a group can reach its printer. | 746 | `docs/architecture.md` | |
| D257 | Pairing needs the code on the daemon's screen: forty random bits, good for fifteen minutes, used once, with wrong attempts limited for each signed-in user. | 748-750 | `delivery/README.md` | `docs/architecture.md` |
| D258 | A print is started only by a signed-in user whose current group has a paired-printer record naming the daemon, and the front server accepts a current group only if the cookie lists it. | 751-753 | `docs/architecture.md` | `delivery/README.md`, `front/README.md` |
| D259 | Nothing read from the state bucket can start a print: a paired-printer record holds a hash of the code only until its daemon has its token. | 754-756 | `docs/architecture.md` | |
| D260 | The cookie's key and the relay's secret key are secrets because they could forge a sign-in or a daemon's token. | 756-757 | `docs/architecture.md` | |
| D261 | Someone who could write to the state bucket could plant a record of a delivery job, which is why only the front server's credential and the project's owner can write to it. | 757-759 | `docs/architecture.md` | |
| D262 | The daemon opens no port and only calls out to the relay, so nothing on the internet can call the computer beside the printer. | 760-761 | `docs/architecture.md` | `delivery/README.md` |
| D263 | Accepted: inside a group there is no further limit; any user can send a print from anywhere and it starts by itself with nobody at the printer. | 763-765 | `docs/architecture.md` | |
| D264 | Permissions inside a group are added later if a group needs them. | 765-766 | `docs/plans/penguin-slicer-plan.md` | `docs/architecture.md` |
| D265 | There are six secrets: the Onshape app's client id and secret; the cookie's encryption key; the relay's secret key; the front server's read-write credential for both buckets; the read-only log bucket credential; the project owner's own Cloudflare sign-in. | 768-775 | `docs/architecture.md` | |
| D266 | The first four secrets are environment variables of the front server set in Railway, the fifth is kept with the owner's other secrets and reaches a coding agent as environment variables, the sixth is the owner's alone, and none is in the repository, a bucket, a log line or a page. | 777-779 | `docs/architecture.md` | `front/README.md` |
| D267 | Every secret can be replaced and a planned replacement interrupts nobody; replacing any of the first four changes a setting of the front server, which restarts as at any deploy. | 781-783 | `docs/architecture.md` | |
| D268 | The front server holds two cookie keys, the current one and the previous one for reading only, and a cookie read with the previous key is written back with the current one. | 787 | `front/README.md` | `docs/architecture.md` |
| D269 | The relay accepts a token signed with either of its two secret keys, answers a daemon whose token was signed with the previous key with a new one that the daemon saves, and each paired-printer record notes which key its daemon's token was last issued under. | 788 | `delivery/README.md` | `docs/architecture.md` |
| D270 | A bucket credential is replaced by making a new one at Cloudflare, giving it to the front server (or the read-only one to the owner's secrets), then cancelling the old one. | 789 | `docs/architecture.md` | |
| D271 | The Onshape app's secret is replaced by a new secret for the same app from Onshape's developer portal; no cookie depends on it, so nobody is signed out. | 790 | `docs/architecture.md` | |
| D272 | The project owner's Cloudflare sign-in is changed at Cloudflare; nothing in PenguinSlicer holds it. | 791 | `docs/architecture.md` | |
| D273 | The previous key of either pair is removed after one week, or sooner for the relay's secret key once every paired-printer record shows the current key. | 793-794 | `docs/architecture.md` | `front/README.md`, `delivery/README.md` |
| D274 | The front server writes a log line each time a previous key is used. | 794-795 | `docs/architecture.md` | `front/README.md`, `delivery/README.md` |
| D275 | A command lists the daemons still to be given a new token. | 795-796 | `delivery/README.md` | `docs/architecture.md` |
| D276 | A daemon switched off for the whole week after the relay's secret key is replaced must be paired again, and a user who does not open PenguinSlicer in the week after the cookie's key is replaced signs in again; with no replacement under way neither limit applies. | 796-799 | `docs/architecture.md` | |
| D277 | In an emergency a leaked key is replaced and not kept as the previous key, so every user signs in again or every printer is paired again (accepted). | 801-803 | `docs/architecture.md` | |
| D278 | The replacement steps are written down in the repository as a procedure, and a test covers each replacement: a cookie and a token made with the previous key are accepted and renewed. | 805-806 | `docs/architecture.md` | `front/README.md`, `delivery/README.md` |

## What this changes in the plan

| Id | Decision | Spec lines | Home | Also needed in |
|---|---|---|---|---|
| D279 | Phase 3 is hosted on Railway, not AWS: an 8 GB EC2 machine costs $37 to $55 a month used or not, while Railway bills $10 per gigabyte held for a month and the two containers hold about half a gigabyte between slices, about $7 a month while few people slice; Railway also has no operating system to patch and PenguinCAM already runs there. | 810-815 | `docs/plans/penguin-slicer-plan.md` | `docs/architecture.md` |
| D280 | The buckets are at Cloudflare R2, not Railway, whose buckets promise none of the three things the design needs. | 816-817 | `docs/plans/penguin-slicer-plan.md` | `docs/architecture.md` |
| D281 | A new standing requirement: a deploy at any moment interrupts no user. | 818-819 | `docs/plans/penguin-slicer-plan.md` | `docs/architecture.md` |
| D282 | The standing requirement Cleanup is amended for slice jobs: a slice job goes on when its page goes away, bounded by the time limit, instead of stopping after a stated wait. | 820-822 | `docs/plans/penguin-slicer-plan.md` | `slice/README.md` |
| D283 | Sliced files, the paired-printer records and the records of delivery jobs are kept in the state bucket, not by the slice service and the relay each, which lets a container restart without a user losing work. | 823-826 | `docs/plans/penguin-slicer-plan.md` | `docs/architecture.md` |
| D284 | Phase 2 builds more than the plan lists: the part store, parts named by hash in the plate configuration, the front server and the development identity. | 827-828 | `docs/plans/penguin-slicer-plan.md` | |
| D285 | The configuration is one document per group in the state bucket holding no secret; the plan's phase 4 configuration file in the Onshape account is dropped, since setting it up has been hard for PenguinCAM's users. | 829-831 | `docs/plans/penguin-slicer-plan.md` | `contracts/configuration.md` |
| D286 | The pairing code is typed into PenguinSlicer once and is then dead; it is no longer kept in the configuration. | 832-833 | `docs/plans/penguin-slicer-plan.md` | `delivery/README.md` |
| D287 | The administrator is every user of a group: nothing distinguishes one user of a group from another. | 834-835 | `docs/plans/penguin-slicer-plan.md` | |
| D288 | Onshape sign-in and the registration of the Onshape OAuth app move from phase 4 to phase 3; only the panel itself and reading parts from Onshape stay in phase 4. | 836-837 | `docs/plans/penguin-slicer-plan.md` | |
| D289 | One printer per group for now, where the plan's configuration lists printers; more than one printer per group is later work. | 838 | `docs/plans/penguin-slicer-plan.md` | |
| D290 | How many slices run at once and how many may wait are settings, where the plan states one and two. | 839-840 | `docs/plans/penguin-slicer-plan.md` | `slice/README.md` |

## What changes in each component

### The slice service

| Id | Decision | Spec lines | Home | Also needed in |
|---|---|---|---|---|
| D291 | The slice service gains the part store, with a route to upload one part that is checked on arrival. | 851 | `slice/README.md` | |
| D292 | The route that takes a whole plate's files in one request is removed. | 852 | `slice/README.md` | |
| D293 | A plate configuration names parts by hash and carries no files, and an error report lists parts missing from the part store. | 853-854 | `contracts/plate-configuration.md` | `slice/README.md` |
| D294 | The part store removes a user key's least recently used part when a twenty-sixth arrives, has a limit on the disk it may take, and is emptied at start. | 855-856 | `slice/README.md` | |
| D295 | Every request to the slice service carries the user key, and each user key has one unfinished slice job. | 860 | `slice/README.md` | |
| D296 | A route lists the slice service's slice jobs, by which a restarted front server finds the slices it must still follow or collect. | 861-862 | `slice/README.md` | `front/README.md` |
| D297 | The rule that cancels a slice job nobody has followed for 120 seconds is removed. | 863 | `slice/README.md` | |
| D298 | The slice service remembers an ended slice job for two hours, where it does so for one. | 864 | `slice/README.md` | |
| D299 | The slice service deletes its copy of a sliced file once the front server has stored it, where it keeps that for an hour. | 865-866 | `slice/README.md` | |
| D300 | The slice service's progress stream sends a comment line when it has nothing to report, as the relay's does. | 867-868 | `slice/README.md` | |
| D301 | How many Orcas run at once and how many slice jobs may wait become settings, where they are fixed in the code at one and two. | 872-873 | `slice/README.md` | |
| D302 | A waiting slice job's progress report says how many are ahead of it, where it says only that it is waiting. | 873-874 | `slice/README.md` | `contracts/wizard-front-server.md` |
| D303 | The memory ceiling is set to the hosted figure (the setting exists and defaults to 2,000 MB). | 875-876 | `slice/README.md` | |
| D304 | The time limit, fixed in the code at 240 seconds, becomes a setting. | 876 | `slice/README.md` | |
| D305 | The slice service runs Orca as a Unix user of its own. | 877 | `slice/README.md` | |
| D306 | Asked to stop, the slice service finishes the slice it is running and waits for the sliced file to be fetched. | 881-882 | `slice/README.md` | |
| D307 | A route gives the front server the slice service's log lines, which gain the time and the user key. | 886 | `slice/README.md` | `front/README.md` |
| D308 | The line that ends a slice job, which already carries Orca's peak memory, its estimates, its times and each part's measurements, gains the bytes of each part and of the sliced file, the wait and the memory ceiling. | 887-889 | `slice/README.md` | |
| D309 | The slice service gains the warning line, the line written once a minute, and a line for every exception and refusal. | 890-891 | `slice/README.md` | |

### Printer delivery

| Id | Decision | Spec lines | Home | Also needed in |
|---|---|---|---|---|
| D310 | As built, the daemon syncs every 5 seconds when nothing changes and up to once a second when a delivery job's progress changes, the relay answers every sync at once, and a running delivery job's report is stale after 20 seconds; this is replaced by the syncs of "How often a daemon talks to the relay". | 895-898 | `delivery/README.md` | |
| D311 | The relay gains the held wait. | 898-899 | `delivery/README.md` | |
| D312 | The daemon gains the thread that holds a sync, the 10-second rhythm during a print, and the random wait before it syncs again after losing the relay. | 899-901 | `delivery/README.md` | |
| D313 | The stale limit becomes 40 seconds. | 901 | `delivery/README.md` | |
| D314 | For replacing the relay's secret key, the relay accepts two keys and gives a new token to a daemon holding one signed with the previous key, where as built a token that does not verify makes the daemon blank it and wait to be paired again. | 902-904 | `delivery/README.md` | |
| D315 | As built, the pairing code is a lasting secret the caller presents from the configuration, the token carries the code, and the relay's records are kept by code; this is replaced by the pairing of the "Pairing" section. | 905-907 | `delivery/README.md` | |
| D316 | The daemon gains its daemon id, offers it with its code, and makes a new code after fifteen minutes. | 907-908 | `delivery/README.md` | |
| D317 | The relay keeps what it knows of each daemon by daemon id, writes the paired-printer record, and checks an offered code against the hash in it. | 908-910 | `delivery/README.md` | |
| D318 | The records of delivery jobs are kept in a store the relay's caller supplies (the state bucket hosted, a folder on one machine), where they are kept in the relay's memory. | 911-912 | `delivery/README.md` | `front/README.md` |
| D319 | The relay takes the sliced file from that store when the daemon fetches it, and no longer keeps a copy of its own. | 913-914 | `delivery/README.md` | `front/README.md` |
| D320 | The relay's limit on the age of a sliced file it will send rises from forty minutes to two hours. | 914-915 | `delivery/README.md` | |
| D321 | The daemon fetches again a sliced file whose fetch was cut off. | 916 | `delivery/README.md` | |
| D322 | The daemon says plainly when it has been unpaired. | 916-917 | `delivery/README.md` | |
| D323 | Limits on the rate of requests are counted for each user and each daemon, where they are counted for each pairing code; the limit on offers of a pairing code, sixty a minute for the whole relay, is also counted for each address. | 918-920 | `delivery/README.md` | |
| D324 | Asked to stop, the relay closes its progress streams and answers its held syncs. | 921 | `delivery/README.md` | |
| D325 | The relay's and daemon's log lines become JSON and gain the time, the group and the user key, and the line that ends a delivery job gains the figures of "Reading what happened". | 922-924 | `delivery/README.md` | |
| D326 | These printer delivery changes join what the plan already lists for phase 5. | 926 | `docs/plans/penguin-slicer-plan.md` | |

### The wizard

| Id | Decision | Spec lines | Home | Also needed in |
|---|---|---|---|---|
| D327 | The server side is built with Onshape sign-in and the development identity. | 930-931 | `front/README.md` | |
| D328 | The server side is built with the encrypted cookie and two keys for it. | 931, 934 | `front/README.md` | |
| D329 | The server side sets the user key. | 931 | `front/README.md` | |
| D330 | The server side reads and writes the configuration. | 932 | `front/README.md` | |
| D331 | The server side passes parts and slice jobs through to the slice service. | 932 | `front/README.md` | |
| D332 | The server side stores, serves and deletes sliced files. | 932-933 | `front/README.md` | |
| D333 | The server side gathers log lines. | 933 | `front/README.md` | |
| D334 | The server side writes a log line for each call to Onshape, each sign-in, each exception and each refusal, and the line written once a minute. | 933-934 | `front/README.md` | |
| D335 | The server side checks the current group against the cookie. | 934-935 | `front/README.md` | |
| D336 | The code in the browser keeps the parts, the layout, the chosen settings, the current group, and the slice job's id and time of submission in the browser's storage. | 936-937 | `wizard/README.md` | |
| D337 | The code in the browser submits a plate again when its slice job has become unknown. | 937 | `wizard/README.md` | `contracts/wizard-front-server.md` |
| D338 | The code in the browser retries every request. | 938 | `wizard/README.md` | |
| D339 | The code in the browser reloads itself when the front server's version has changed. | 938-939 | `wizard/README.md` | |
| D340 | The code in the browser offers "sign in again". | 939 | `wizard/README.md` | |

### The contracts

| Id | Decision | Spec lines | Home | Also needed in |
|---|---|---|---|---|
| D341 | The plate configuration's part names a hash, not a file sent with it. | 943 | `contracts/plate-configuration.md` | |
| D342 | A contract for the configuration document is written, with an annotated example. | 944 | `contracts/configuration.md` | |
| D343 | Each record kept in the state bucket carries the number of its format. | 945 | `contracts/README.md` | `docs/architecture.md` |

## By phase

| Id | Decision | Spec lines | Home | Also needed in |
|---|---|---|---|---|
| D344 | Phase 2 runs the front server, without the relay, and one slice service process on the one machine, with the development identity, and a folder stands in for each bucket behind the same interface. | 949-951 | `docs/plans/penguin-slicer-plan.md` | `front/README.md` |
| D345 | Phase 2 builds everything under "Where each piece of state lives" except what it says of Send and delivery jobs (which waits for phase 5), and the slice container's half of "Restarts and deploys" with its tests. | 951-954 | `docs/plans/penguin-slicer-plan.md` | |
| D346 | Phase 3 first tries what Railway does at a deploy, since the rest of "Restarts and deploys" rests on it; then it builds the two containers at `https://penguinslicer.popcornpenguins.com/`, the state and log buckets, Onshape sign-in, two keys for the cookie, the rules of "Old and new versions together", the command that reads the log bucket, the check after each deploy, and the measurements that set the memory ceiling and the time limit. | 955-961 | `docs/plans/penguin-slicer-plan.md` | |
| D347 | Phase 4's panel uses the same sign-in and the same routes. | 962 | `docs/plans/penguin-slicer-plan.md` | |
| D348 | Phase 5 brings the relay into the front server, with pairing, the syncs and the held wait, the records of delivery jobs in the state bucket, replacing the relay's secret key, and daemon telemetry. | 963-965 | `docs/plans/penguin-slicer-plan.md` | `front/README.md`, `delivery/README.md` |

## To confirm before building on it

| Id | Decision | Spec lines | Home | Also needed in |
|---|---|---|---|---|
| D349 | To confirm: whether Railway deploys one of two services alone when only its folders changed, whether it starts the new container before stopping the old, and how long it lets a stopping container finish; until tried, the design assumes a plain stop and start. | 971-975 | `docs/architecture.md` | |
| D350 | To confirm: Orca on Railway's machines up to the memory ceiling; all measurements so far are from aarch64 Linux and plates under 2,600 MB, so plates of rising weight up to the proposed 6,000 MB are sliced and measured on the slice container before users rely on it, setting the memory ceiling, time limit and estimates and showing the processors and Orca's use of them. | 976-981 | `docs/architecture.md` | `slice/README.md` |
| D351 | To confirm: Railway's limit on a request body, which its documents do not state; a 7.5 MB part should pass and one real upload settles it. | 982-983 | `docs/architecture.md` | |
| D352 | To confirm: Railway's 8 GB for one container on its Hobby plan, and x86_64 machines, both inferred from Railway's pages and staff posts. | 984-985 | `docs/architecture.md` | |
| D353 | To confirm: the owner's account's Onshape allowance, whether the development and hosted OAuth apps draw on the same allowance, and whether renewing a token counts as a call (which matters from phase 4). | 986-988 | `docs/architecture.md` | `front/README.md` |
| D354 | To confirm: whether Cloudflare and Railway pass server-sent events on without holding them; if one holds them, the page asks for the latest progress report every second or two instead, by a route both interfaces have. | 989-992 | `docs/architecture.md` | `front/README.md`, `wizard/README.md`, `contracts/wizard-front-server.md` |
| D355 | To confirm: whether the old Onshape app secret stops working at once when replaced (failing sign-ins until the front server has the new one) and whether, from phase 4, tokens issued under the old secret can still be renewed. | 993-996 | `docs/architecture.md` | |
| D356 | To confirm: whether Cloudflare's protection against automated clients ever challenges a daemon's requests. | 997-998 | `docs/architecture.md` | `delivery/README.md` |
| D357 | To confirm: the cookie fits in about 4 KB carrying identity, groups and both Onshape tokens encrypted, and two requests renewing the tokens at once must not leave a spent refresh token in the cookie. | 999-1001 | `docs/architecture.md` | `front/README.md` |
| D358 | To confirm: what Onshape answers for an account with no company or classroom. | 1002-1003 | `docs/architecture.md` | `front/README.md` |
| D359 | To confirm: whether the daemon as built fetches a sliced file again when the connection drops mid-way. | 1004-1005 | `docs/architecture.md` | `delivery/README.md` |
| D360 | To confirm: the front server's memory with fifty held syncs, the part store's disk use, and what the slice service needs beside Orca (the 2 GB left above the memory ceiling) were never measured. | 1006-1008 | `docs/architecture.md` | |
| D361 | To confirm: cost; by Railway's rates the two containers cost about $7 a month with a few slices a day, about $40 a month for 5,000 slices and 1,000 daemons (which also needs the asynchronous server), the buckets cost cents, and the first month's bill settles it. | 1009-1014 | `docs/architecture.md` | `docs/plans/penguin-slicer-plan.md` |

## Decided after the spec

| Id | Decision | Spec lines | Home | Also needed in |
|---|---|---|---|---|
| D362 | What the spec calls "the wizard's server side" is a component of its own, the front server, in `front/`; the wizard is the code in the browser only, in `wizard/`; and a contract between the two, `contracts/wizard-front-server.md`, is to be written. | 14-17 (note added after approval) | `docs/plans/penguin-slicer-plan.md` | `docs/architecture.md`, `front/README.md`, `wizard/README.md`, `contracts/wizard-front-server.md`, `contracts/README.md` |

| D363 | A component's guide is two files: `README.md` for a person and `README-details.md` for a builder (the owner, Thu 2026-11-26). | none | `docs/plans/penguin-slicer-plan.md` | every guide |
| D364 | Correction by measurement: the slowest plate of the Popcorn Penguins' real parts took 34.3 seconds (twelve Elevator Block Bottom Inners with supports on), where the spec says 22. | 150 | `slice/README.md` | |
| D365 | Correction by the code: the line that ends a slice job already carries the memory ceiling, which the spec lists as something to add. | 892 | `slice/README.md` | |
| D366 | Answered by the code: the daemon as built fetches a sliced file again after a cut-off connection, up to three attempts; this leaves the list of things to confirm (D359). | 1004-1005 | `delivery/README.md` | `docs/architecture.md` |
| D367 | Added: the front server stores a sliced file's summary beside it in the state bucket and serves both, because the Preview step needs the summary after the slice container has deleted its copy. | none | `front/README.md` | `contracts/wizard-front-server.md` |
| D368 | Added, as a proposal: a send repeated with the same sliced file by the same user while its delivery job is live answers with that delivery job, since the page retries every request. | none | `delivery/README.md` | `front/README.md`, `contracts/wizard-front-server.md` |
| D369 | Added: a slice service that is stopping refuses a new slice job with an answer that is tried again without telling the user, never `slice.busy`. | none | `slice/README.md` | `contracts/wizard-front-server.md`, `wizard/README.md` |

### Awaiting the owner

Where the wizard's approved mockup (version 8) and the spec differ. Each is set out in
full, with both sides and a recommendation, in
[the wizard's detailed guide](../../../wizard/README-details.md). For the three items
awaiting the owner's choice, the living documents state the approved design as it stands
and add "This may change: an item awaits the owner's choice", with a link to the item. For
every other item, they state the recommendation, marked "not yet confirmed by the owner",
with a link to the item.

| Item | Recommendation | Status |
|---|---|---|
| Sending the same plate again after a long print | A sliced file lives until two hours after its slice or two hours after its last print ended, whichever is later | Awaiting the owner's choice |
| How long the page retries before telling the user | Keep the mockup's 20 seconds; a longer restart is a defect to fix once measured | Awaiting the owner's choice |
| "Not heard from for 7 minutes" | The relay notes the time in the paired-printer record when a daemon goes offline | Awaiting the owner's choice |
| What a refresh keeps; finding a slice job after one; when the two hours start; who pairs the printer and where; how the page outside Onshape finds its configuration; where a returning page opens after its print ended | The spec | Not yet confirmed |
| A colour for each filament; a part that cannot be used | The mockup (four fixed colours; a notification, and the part is not added) | Not yet confirmed |
| Whether the printer is in the configuration | The paired-printer record links the group to its daemon; the configuration names the printer's Orca profile | Not yet confirmed |
| What a delivery job's record carries; a returning page finding its delivery job and last print; a profile's own name and purpose; the plate's size on the Layout step | Added to the living documents as the mockup requires | Not yet confirmed |

## Possible disagreements in the spec

- D11 against D127, D132 and D133: the short answer says the hosted service makes no calls besides sign-in until phase 4, but if the app becomes public before phase 4, reading groups again (once a day) and renewing tokens make calls before phase 4.
- D217 against D106 and D203: a closed page whose slice was cut off by a restart "submits again when next opened", but a page opened more than two hours after submitting treats an unknown slice job as expired and drops the stored parts.
- D15 against D267 and D276: the short answer limits "interrupts nobody" to users who return within a week; the Security section states it unqualified, then adds the one-week limit.
- D223 against D178 and D312: a running print's status is back "within ten seconds of the front server answering again", while a daemon that lost the relay waits a random time before it syncs again, which could add to the ten seconds.
