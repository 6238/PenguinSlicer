# The wizard

Nothing of the wizard is built yet, and this guide is begun, not complete. It holds what
the approved design asks of the code in the browser; the steps a user sees are written
into it later, from the mockup. Every rule and figure is in
[README-details.md](README-details.md).

## What it is, and what it is not

The **wizard** is the code in the browser: the step-by-step user interface, with the
Parts, Settings, Layout, Preview and Send steps and a printer-status icon in its header.
It works from 320 px wide, in Onshape's panel and in a tab of its own.

It talks only to the **front server**, a separate component
([its guide](../front/README.md)): the one process the internet reaches, which serves the
wizard's pages, signs users in with Onshape, passes parts and slice jobs to the slice
service, keeps the sliced files and each group's configuration, and from phase 5 runs the
relay of printer delivery. What passes between the two is to be fixed in
[the contract between them](../contracts/wizard-front-server.md), whose routes are not
written yet. How the whole fits together is in [the architecture](../docs/architecture.md);
the phases are [the plan's](../docs/plans/penguin-slicer-plan.md): 2, one machine; 3,
hosted on Railway; 4, inside Onshape; 5, the real printer.

More: [Terms used below](README-details.md#terms-used-below).

## What the page keeps, and why

The browser is the record of a user's parts and layout: nothing on the server is. The
**page** (the wizard loaded in one tab, or in Onshape's panel) keeps in the browser's
storage the parts, the layout, the chosen settings, the current group, and the id of the
plate's slice job with the time it was submitted. They stay until the page, on opening,
finds the plate's sliced file expired; the current group stays until the user changes it.
No restart of a server touches them. The page never stores or uploads a sliced file, so a
printer only ever receives a file the slice service made.

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
| Unknown, submitted less than two hours ago | Uploads the parts and submits again, unasked |
| Ended in an error | Shows the error on the Preview step |
| Cancelled by a later slice of the same user | Shows the plate and offers to slice it; does not submit by itself |
| Unknown, submitted more than two hours ago | Opens on the Parts step with one line saying the sliced file has expired, and drops the stored parts |

From phase 5, a page whose plate has a delivery job opens on the Send step. Work does not
follow a user to another computer or browser, and Chrome keeps the storage of the page in
Onshape's panel apart from the page in a tab, so work begun in one does not appear in the
other. Safari is not supported.

More: [What a returning page does](README-details.md#what-a-returning-page-does), [Storage in the panel and in a tab](README-details.md#storage-inside-onshapes-panel-and-storage-in-a-tab).

## Across a restart or a deploy

The project is deployed continuously, and a deploy at any moment must interrupt no user.

- **Progress streams reconnect.** The page follows a slice job on server-sent events
  through the front server, which sends a comment line at least every fifteen seconds;
  when the stream closes the page reconnects and gets the latest progress report at once.
- **Every request is retried,** so one that falls in the gap of a deploy is repeated and
  the user sees a pause, not an error. How long before an error shows is awaiting the
  owner's choice (below).
- **The page reloads itself** when an answer carries a newer front server version, at the
  next moment when nothing is in flight; it loses nothing, since its state is in the
  browser's storage.
- **Signing in.** Every user signs in with Onshape; the cookie lasts thirty days. The
  header names the current group, which the user changes there, and has "sign in again"
  beside it, which reads the user's groups afresh for two calls to Onshape.

More: [Following progress](README-details.md#following-progress-and-reconnecting), [Retrying](README-details.md#retrying-every-request), [Reloading](README-details.md#reloading-on-a-newer-version-of-the-front-server), [Signing in](README-details.md#signing-in-and-sign-in-again).

## Where the mockup and the design differ

The mockup's decisions (version 8, approved Thu 2026-11-26) and the approved design
disagree in eleven places, and the mockup shows six things the design gives no means for.
Each has a recommended resolution:

| Item | Recommended | Status |
|---|---|---|
| 1.1 Sending the same plate again after a long print | A sliced file lives until two hours after its slice or two hours after its last print ended, whichever is later | Awaiting the owner's choice |
| 1.9 Retrying, then an error after 20 seconds | Keep the mockup's 20 seconds; a restart that takes longer is a defect to fix once Railway's restart time is measured | Awaiting the owner's choice |
| 2.4 "Not heard from for 7 minutes" | The relay notes the time in the paired-printer record when a daemon goes offline | Awaiting the owner's choice |
| 1.2 What a refresh keeps | Parts, layout and settings restored from the browser's storage | Not yet confirmed |
| 1.3 Finding a slice job after a refresh | The browser kept its id; work does not follow to another browser | Not yet confirmed |
| 1.4 When the two hours start | When the slice ended | Not yet confirmed |
| 1.5 A colour for each filament | Four fixed colours; the configuration holds no colour | Not yet confirmed |
| 1.6 Who pairs the printer, and where | Any user of the group types the code into PenguinSlicer | Not yet confirmed |
| 1.7 Whether the printer is in the configuration | The paired-printer record links the daemon; the configuration names the printer's Orca profile | Not yet confirmed |
| 1.8 A part that cannot be used | A notification; the part is not added | Not yet confirmed |
| 1.10 Where a returning page opens after its print ended | The Parts step, with the last-print note | Not yet confirmed |
| 1.11 How the page outside Onshape finds its configuration | From the signed-in user's group, never from a link | Not yet confirmed |
| 2.5 A profile's name and purpose | The configuration holds the group's own name and purpose for each profile | Not yet confirmed |

The other needs from the server (the plate's size, who sent a print, the user's own
delivery job, the "plate too large" error) and the twelve screens the design needs that
the mockup does not show (signing in, the group choice, waiting and busy, pairing, a
stale print, the reload, and others) are listed in the details.

More: [Where they differ](README-details.md#where-the-mockup-and-the-design-differ), [Needs from the server](README-details.md#what-the-mockup-shows-that-needs-something-from-the-server), [Screens to design](README-details.md#screens-the-design-needs-that-the-mockup-does-not-show).

## What is to be built, by phase

| Phase | What of the wizard |
|---|---|
| 2, one machine | Opened directly, with parts from files: the browser's storage, uploading, submitting by hash, the returning page, progress streams, retrying, the current group, the preview and the download |
| 3, hosted on Railway | Onshape sign-in and "sign in again"; the header that proves a request came from the wizard's page; reloading on a newer version |
| 4, inside Onshape | The wizard in Onshape's panel |
| 5, the real printer | The Send step and the printer-status icon: pairing, sending, "stop following", unpairing |

More: [By phase](README-details.md#by-phase).

## Still to be written

- **The steps,** from [the mockup's decisions](../docs/mockups/print-wizard/DECISIONS.md):
  every screen, message and decision of the five steps and the printer-status icon,
  together with the twelve screens the design needs.
- **The mockup's open questions** ("Please react to these", M-numbered), each answered by
  the owner or carried here as an open choice with its backing.
- **The mockup is thrown away** once this guide is complete.

More: [Still to be written](README-details.md#still-to-be-written).
