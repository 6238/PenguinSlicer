# The wizard

Nothing of the wizard is built yet, and this guide is begun, not complete. It holds what
the approved design ([the architecture](../docs/architecture.md) holds it now) asks of the
code in the browser; the steps a user sees are written into it later, from the mockup.
Every rule and figure is in [README-details.md](README-details.md).

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
the id of the plate's slice job with the time it was submitted. So a refresh, a reopened
panel or a reload keeps the work: the parts, the layout and every changed setting come
back, which matters because the page reloads itself after every deploy.

A sliced file is kept until two hours after its slice ended or two hours after its last
print ended, whichever is later. So after a print of any length, finished or failed, Send
is enabled again for the same sliced plate.
The stored work stays until the page, on opening, finds the plate's
sliced file expired; the current group stays until the user changes it. No restart of a
server touches them. The page never stores or uploads a sliced file, so a printer only
ever receives a file the slice service made.

**Each part is uploaded once, when it is added,** in one request of at most 7.5 MB, and is
checked by the slice service as it arrives, before anything is laid out; a part that
cannot be used is a notification and is not added. The slice service
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

From phase 5, a page whose stored plate has a delivery job, running or ended, opens on
the Send step, with the last-print note ("Your print finished at 11:25 am.") or the
failure; a deploy's reload never moves a user off it. Work does not follow a user to
another computer or browser, and Chrome keeps the storage of the page in Onshape's
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
- **Every request that fails or gets no answer is retried,** quietly at first, so one
  that falls in the gap of a deploy is repeated. After 20 seconds of failed retries the
  page says the server is being slow and the browser is retrying, with a countdown to the
  next attempt; the waits between attempts grow. It keeps retrying for up to 300 seconds
  in all, then says the server could not be reached and offers to try again. Nothing of
  the user's work is dropped: the parts, layout and settings stay in the browser's
  storage. The exact waits and words are proposed.
- **The page reloads itself** when an answer carries a newer front server version, at the
  next moment when nothing is in flight; it loses nothing, since its state is in the
  browser's storage.
- **A restart signs nobody out.**

More: [Following progress](README-details.md#following-progress-and-reconnecting), [Retrying](README-details.md#retrying-every-request), [Reloading](README-details.md#reloading-on-a-newer-version-of-the-front-server).

## The configuration and printers

The page uses the current group's **configuration**, read through the front server after
sign-in, never one opened from a link. It holds the group's filaments, each with its
profiles under the group's own names and purposes, and the printer's Orca profile, from
which the Layout step takes the plate's size and height. Each filament also has a colour,
which the wizard shows where the user chooses a filament, so that a red PLA and a green
PLA can be told apart. The layer preview never uses it: it draws every plate in four
fixed colours, one for each set of line types, whatever the filament.

From phase 5, any signed-in user of the group pairs the printer by typing the code the
daemon shows, from any computer. An offline printer says how long it has been silent
("Not heard from for 7 minutes."), truly even after a restart of the front server,
because the relay notes the time in the group's paired-printer record (the one document
for each group that names its daemon) when a daemon goes offline. The printer details
say who sent a print, what it is, and how the last one ended.

There is no "plate too large" error; a plate too big to slice ends in the out-of-memory
error.

This guide departs from the mockup's decisions (version 8, approved Thu 2026-11-26) in
the places the details list; whoever writes the steps follows this guide there. Twelve
screens the design needs that the mockup does not show (signing in, the group choice,
waiting and busy, pairing, a print whose daemon has gone silent, the reload, and others)
are listed in the details too.

More: [The configuration](README-details.md#the-configuration), [Printers](README-details.md#printers-from-phase-5), [Where it departs from the mockup](README-details.md#where-this-guide-departs-from-the-mockups-decisions), [Screens to design](README-details.md#screens-the-design-needs-that-the-mockup-does-not-show).

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
