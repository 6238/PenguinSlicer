# The wizard

Nothing of the wizard is built yet, and this guide is begun, not complete. It holds what
the approved design ([the architecture](../docs/architecture.md) holds it now) asks of the
code in the browser; the steps a user sees are written into it later, from the mockup.
Fifteen items await the owner's choice or yes; they are in
[Where the mockup and the design differ](#where-the-mockup-and-the-design-differ). Every
rule and figure is in [README-details.md](README-details.md).

## What it is, and what it is not

The **wizard** is the code in the browser: the step-by-step user interface, with the
Parts, Settings, Layout, Preview and Send steps and a printer-status icon in its header.
It works from 320 px wide, in Onshape's panel and in a tab of its own.

It talks only to the **front server** ([its guide](../front/README.md)), the one process
the internet reaches. What passes between the two is to be fixed in
[the contract between them](../contracts/wizard-front-server.md), whose routes are not
written yet. The phases are [the plan's](../docs/plans/penguin-slicer-plan.md): 2, one
machine; 3, hosted on Railway; 4, inside Onshape; 5, the real printer.

More: [Terms used below](README-details.md#terms-used-below).

## What the page keeps, and why

The browser is the record of a user's parts and layout: nothing on the server is. The
**page** (the wizard loaded in one tab, or in Onshape's panel) keeps in the browser's
storage the parts, the layout, the chosen settings, the current group (the one group, of
those the user belongs to, whose configuration and printer the user is using now), and
the id of the plate's slice job with the time it was submitted. That a refresh keeps all
of this is the design's; the mockup keeps none of it (item 1.2 below).

A sliced file is kept for two hours after its slice ended. This may change: an item awaits
the owner's choice ([1.1](README-details.md#11-sending-the-same-plate-again-after-a-long-print)).
The stored work stays until the page, on opening, finds the plate's
sliced file expired; the current group stays until the user changes it. No restart of a
server touches them. The page never stores or uploads a sliced file, so a printer only
ever receives a file the slice service made.

**Each part is uploaded once, when it is added,** in one request of at most 7.5 MB, and is
checked by the slice service as it arrives, before anything is laid out. The slice service
keeps it for two hours after its last use, as a cache. On the Preview step the page sends
a **plate configuration** that names each part by the SHA-256 hash of its bytes and
carries no files, so slicing again uploads nothing. When the answer lists parts the slice
service no longer has, the page uploads them again from the browser's storage and submits
again; the user sees nothing of it.

**A user has one unfinished slice job at a time.** Submitting a plate cancels the user's
earlier unfinished one, so with the wizard open in two tabs the later slice wins. A slice
job, once submitted, runs to its end whether or not a page follows it.

More: [What the page keeps](README-details.md#what-the-page-keeps-in-the-browsers-storage), [Uploading](README-details.md#uploading-each-part-when-it-is-added), [Submitting](README-details.md#submitting-a-plate-configuration).

## When a user comes back

A page that has lost its state (a refresh, a reopened panel, a reload) reads its plate and
its slice job's id from the browser's storage and asks the front server about that slice
job:

| The front server answers | The page |
|---|---|
| Waiting or running | Shows its progress on the Preview step |
| Finished, sliced file kept | Opens on the Preview step with the result |
| Unknown, submitted less than two hours ago: the slice service restarted | Uploads the parts and submits again, unasked |
| Ended in an error | Shows the error on the Preview step |
| Cancelled by a later slice of the same user | Shows the plate and offers to slice it; does not submit by itself |
| Unknown, submitted more than two hours ago: its sliced file has expired | Opens on the Parts step with one line saying the sliced file has expired, and drops the stored parts |

The page tells the two unknown rows apart by the submission time it kept.

From phase 5, the design opens a page whose plate has a delivery job on the Send step;
the mockup opens it there only while the print is running. Which holds is item 1.10
below, and the recommendation is the design's. Work does not follow a user to another
computer or browser (item 1.3), and Chrome keeps the storage of the page in Onshape's
panel apart from the page in a tab, so work begun in one does not appear in the other.
Safari is not supported.

More: [What a returning page does](README-details.md#what-a-returning-page-does), [Storage in the panel and in a tab](README-details.md#storage-inside-onshapes-panel-and-storage-in-a-tab).

## Signing in and the current group

Every user signs in with Onshape, in the panel and outside it; the sign-in cookie lasts
thirty days. The header names the current group, which the user changes there. Beside it,
"sign in again" serves a user added to an Onshape company after signing in: they see the
new group only after using it. It costs two calls of Onshape's yearly allowance.

Every request that changes something carries a header that only the wizard's own page
can set, because inside Onshape's panel the cookie alone does not prove a request came
from the wizard.

More: [Signing in](README-details.md#signing-in-and-sign-in-again), [The current group](README-details.md#the-current-group).

## Across a restart or a deploy

The project is deployed continuously, and a deploy at any moment must interrupt no user.

- **Progress streams reconnect.** The page follows a slice job on server-sent events
  through the front server; when the stream closes the page reconnects and gets the
  latest progress report at once.
- **Every request that gets no answer is retried,** so one that falls in the gap of a
  deploy is repeated and the user sees a pause, not an error. How long before an error
  shows needs the owner's choice (item 1.9 below).
- **The page reloads itself** when an answer carries a newer front server version, at the
  next moment when nothing is in flight; it loses nothing, since its state is in the
  browser's storage.
- **A restart signs nobody out.**

More: [Following progress](README-details.md#following-progress-and-reconnecting), [Retrying](README-details.md#retrying-every-request), [Reloading](README-details.md#reloading-on-a-newer-version-of-the-front-server).

## Where the mockup and the design differ

The mockup's decisions (version 8, approved Thu 2026-11-26) and the approved design
disagree in eleven places, and the mockup shows six things the design gives no means for.
The numbers are those of
[the comparison of the mockup with the design](../docs/orchestration/hosted-architecture/mockup-against-design.md),
which the items come from. Each is set out in the
details with both sides, what a user would see under each, and the recommendation with
its reason, and is decided there, not from this page.

Three need the owner's **choice**: each answer costs something the owner must weigh.

- **[1.1 Sending the same plate again after a long print](README-details.md#11-sending-the-same-plate-again-after-a-long-print).**
  After a print that ends more than two hours after its slice, can the user send the
  same sliced file again? The mockup: yes, always. The design: no, the file has expired
  and the user slices again. Recommended: keep a sliced file until two hours after its
  slice or after its last print ended, whichever is later, at the cost of one sliced file
  (8.8 to 14.1 MB on the plates measured) stored two hours more per print.
- **[1.9 Retrying, then an error after 20 seconds](README-details.md#19-retrying-then-an-error-after-20-seconds).**
  How long does the page retry before it shows an error? The mockup: 20 seconds, then
  the part is not added. The design: always a pause, never an error, with no limit.
  Recommended: the mockup's 20 seconds, with a restart that takes longer treated as a
  defect once Railway's restart time is measured.
- **[2.4 "Not heard from for 7 minutes"](README-details.md#24-not-heard-from-for-7-minutes).**
  After a front server restart, how long has an offline printer been silent? The mockup
  shows the duration; the design loses it at a restart. Recommended: the relay notes the
  time in the paired-printer record (the one document for each group that names its
  daemon) when a daemon goes offline.

The others need only the owner's **yes** to the recommendation:

| Item | The question | Mockup | Design | Recommended |
|---|---|---|---|---|
| [1.2](README-details.md#12-what-a-refresh-keeps) | Does a refresh keep the work? | No | Yes | The design |
| [1.3](README-details.md#13-finding-a-slice-job-after-a-refresh) | Does work follow to another browser? | Yes, from the server | No | The design |
| [1.4](README-details.md#14-when-the-two-hours-start) | When do the two hours start? | When the user left | When the slice ended | The design, unless the owner answers the mockup's question M18 otherwise |
| [1.5](README-details.md#15-a-colour-for-each-filament) | A preview colour for each filament? | No, four fixed colours | Yes | The mockup |
| [1.6](README-details.md#16-who-pairs-the-printer-and-where) | Who pairs the printer? | An administrator, beside it | Any user, from anywhere | The design |
| [1.7](README-details.md#17-whether-the-printer-is-in-the-configuration) | Is the printer in the configuration? | Yes | No: pairing links it | Pairing links it; the configuration names its Orca profile, for the plate's size |
| [1.8](README-details.md#18-a-part-that-cannot-be-used) | A part that cannot be used | A notification, not added | A row with its error | The mockup |
| [1.10](README-details.md#110-where-a-returning-page-opens-after-its-print-ended) | Where does a page open after its print ended? | The Parts step | The Send step | The design, with the note "Your print finished at 11:25 am." |
| [1.11](README-details.md#111-how-the-page-outside-onshape-finds-its-configuration) | How does the page outside Onshape find its configuration? | A saved link | The user's group | The design |
| [2.1](README-details.md#21-the-plates-size-and-height) | Where do the plate's size and height come from? | The printer | Nowhere | The printer's Orca profile (follows 1.7) |
| [2.5](README-details.md#25-a-profiles-name-and-purpose) | A profile's own name and purpose? | Yes | Orca's names only | The configuration holds them |
| [2.6](README-details.md#26-the-plate-too-large-error) | A "plate too large" error? | Yes, invented | No volume cap | Left out |

The other needs from the server (who sent a print, the user's own delivery job) and the
twelve screens the design needs that the mockup does not show (signing in, the group
choice, waiting and busy, pairing, a print whose daemon has gone silent, the reload, and
others) are listed in the details.

More: [Where they differ](README-details.md#where-the-mockup-and-the-design-differ), [Needs from the server](README-details.md#what-the-mockup-shows-that-needs-something-from-the-server), [Screens to design](README-details.md#screens-the-design-needs-that-the-mockup-does-not-show).

## What is to be built, by phase

| Phase | What of the wizard |
|---|---|
| 2, one machine | Opened directly, with parts from files: the browser's storage, uploading, submitting by hash, the returning page, progress streams, retrying, reloading on a newer version, the current group, the preview and the download |
| 3, hosted on Railway | Onshape sign-in and "sign in again"; the header that proves a request came from the wizard's page |
| 4, inside Onshape | The wizard in Onshape's panel, with parts read from Onshape |
| 5, the real printer | The Send step and the printer-status icon: pairing, sending, cancelling, giving up a print whose daemon has gone silent ("stop following"), unpairing, and the returning page on the Send step |

More: [By phase](README-details.md#by-phase).

## Still to be written

- **The steps,** from [the mockup's decisions](../docs/mockups/print-wizard/DECISIONS.md):
  every screen, message and decision of the five steps and the printer-status icon,
  together with the twelve screens the design needs.
- **The mockup's open questions** ("Please react to these", M-numbered), each answered by
  the owner or carried here as an open choice with its backing.

The mockup is thrown away once this guide is complete and the owner has agreed it.

More: [Still to be written](README-details.md#still-to-be-written).
