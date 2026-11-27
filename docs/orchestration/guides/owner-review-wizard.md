# The owner's review of the wizard's guide (Fri 2026-11-27)

What the owner decided while reading [the wizard's guide](../../../wizard/README.md). It
adds to [the decisions of the same day](decisions-2026-11-27.md) and wins over them and
over every other document where they differ. The guide states each of these as the design,
without saying who decided or when.

## Signing in and the group

1. Signing in is not something a user manages. Inside Onshape's panel there must be no
   difference between being signed in to Onshape and being signed in to PenguinSlicer: the
   sign-in lasts as long as the user is signed in to Onshape and is never felt as a separate
   thing. Outside Onshape a sign-in lasts thirty days, and the page has a sign-out link.
   Inside the panel there is no sign-out link.
2. When the sign-in is missing or has run out, the page makes the trip to Onshape by itself
   at a quiet moment and returns to the same step. A user signed in to Onshape sees nothing.
   The message with a "Sign in with Onshape" button remains only for when that trip fails
   (for example the user is signed out of Onshape, or refused).
3. If a different person is signed in to Onshape on the same browser, PenguinSlicer follows:
   the sign-in is made again for that user.
4. The browser's stored work is tied to the signed-in user. When a different user signs in
   at the same browser, the previous user's stored work is cleared.
5. A user in one group sees nothing to manage: the header names their configuration in plain
   words, with no group details, no list, no "Signed in as" and nothing to click. A list of
   groups and a way to choose exist only for a user in more than one group.
6. Inside Onshape the group follows Onshape: it is the group of the document the user has
   open, and no choice is offered, even to a user in several groups. Choosing a group is
   only ever seen outside Onshape, by a user in more than one.
7. There is no "Sign in again" for a user to press. The front server reads a user's groups
   again itself: at every sign-in, and when Onshape says the user is working in a company
   that the sign-in does not list.
8. Changing group clears everything: parts, layout, settings and slice. The wizard asks
   first when there is work to lose.
9. To confirm in phase 4, and to state plainly with the fallback: whether Onshape tells a
   panel the user and the company (it gives the document and the element), without which
   point 6 costs a call to Onshape for each document and point 3 has no trigger; and whether
   the trip to Onshape can be invisible inside the panel. PenguinCAM could not manage that:
   it shows a "Connect" button once and signs in through a small window that closes itself.
   The fallback is one click the first time in a browser.

## Plates, tabs and what the browser keeps

10. A plate for each tab. A user may have several tabs open, and each works with its own
    plate without affecting the others. More storage is accepted.
11. A newly opened tab shows the user's most recently used plate, if it was used less than
    12 hours ago and no other open tab holds it; otherwise an empty plate. A plate in the
    browser's storage that has not been used for 12 hours is dropped.
12. A stored plate therefore outlives its sliced file, which lasts two hours. A returning
    page whose sliced file has expired keeps its parts, layout and settings and shows the
    expired message with "Slice again". It does not empty the plate. This departs from the
    mockup's decision 48.
13. There is a "New plate" button. No count of plates is kept or shown. The words are "a new
    plate", never "a second plate".
14. There is no limit on slices for each user. Everyone shares the slice service's places
    (one running and two waiting, as settings). Within one plate, a changed plate's new
    slice replaces that plate's own earlier unfinished slice.

## Slicing

15. A slice cannot be cancelled by hand. The slicing card has no Cancel button and there is
    no "cancelled by the user" state; the front server offers no request to cancel a slice.
    A slice ends without a result for only two reasons a page can meet: the same plate's
    later slice replaced it, or the slice service was asked to stop. This departs from the
    mockup. It is looked at again only if slices on the hosted service turn out to take
    minutes.
16. Orca's own sentence about a failed slice is quoted under Details, marked as Orca's, on
    the two failures about a gap with nothing under it, and nowhere else.
17. A progress stream that cannot be reopened is treated as failed after 20 seconds, and a
    stream that is open but has carried nothing for 45 seconds is also treated as failed.
18. A sliced plate that expires while the page is open: a grey message with "Slice again";
    parts, layout and settings stay; the page does not slice again by itself.
19. No room for a slice to wait: an amber message with "Slice again"; the page does not keep
    trying by itself.
20. A slice that ran out of memory offers no "Slice again".
21. The message that the server is being slow sits on the panel's line, which stays as the
    user moves between steps, with its countdown and a "Retry now" link.

## Parts

22. An upload takes binary STL only.
23. A switch beside the upload area, "Read STL files in: inches / millimetres", starts at the
    configuration's value and is kept in the browser's storage, until the edit screens exist.
24. A part the slice service accepts but the browser cannot draw is not added; the
    notification says that PenguinSlicer could not show the part and that it cannot be
    imported; the failure reaches the server's log.
25. A configuration that cannot be read is never the wizard's to handle. The front server
    never gives the wizard an invalid configuration: it serves the default in its place,
    leaves the saved file untouched, and writes an error to the log. The wizard has no
    screen for this case; its header names the configuration in use.

## The look, the behaviour, and Orca

26. The look follows the mockup. The wizard looks the same as the mockup at version 8: the
    same layout, elements, order, colours, type and wording at each width. Where matching is
    cheap it matches, and taking over the mockup's style sheets is the cheap way. Small
    differences of pixels are acceptable where there is a good reason. The mockup is kept in
    the repository as the reference for the look. It is not thrown away.
27. The behaviour follows the guide. The mockup's scripts were faked, so what the wizard
    does is built from the guide, with real parts and real files.
28. The order of authority for what the wizard does: first the decisions the guide states;
    second the mockup; third Orca's behaviour, for the Layout and Preview steps only, where
    there is complex behaviour that Orca already models (arranging, orienting, laying a part
    on a face through the patches, inspecting a sliced file layer by layer). For the Parts
    step, the Settings step, and the Send step with the printer-status icon, Orca is not a
    reference. Where a stated decision differs from Orca on purpose (the mouse works like
    Onshape; Arrange never turns an instance; the bounding-box patches), say so in a clause.
29. An implementer may read Orca's source to understand its algorithms and methods, and
    never copies its code. The licence covers the code as written, not the idea behind it.
30. Advanced mode shows Orca's own labels, groups and explanations for its settings. The
    table of settings is taken from Orca's source each time an Orca version is integrated.
31. No keyboard support is designed for the Layout step beyond what the mockup has.
    Accessibility beyond what the mockup has is not a goal of this version.

## How well it must do it, and how that is known

32. Nothing the wizard does holds the browser's main thread for more than 250 milliseconds,
    on any step, with any plate up to the limits, judged on the machine of the "without a
    graphics card" target.
33. By design, a separate worker does anything that reads or works with the internals of an
    STL file or of a sliced file's paths: reading a part for drawing, finding the faces it
    can lie on, auto-orient, Arrange, the placement check on a full plate, and preparing a
    sliced file for the Preview step. Hashing a part does not need a worker.
34. The Preview step's targets: 30 frames a second with a graphics card and 10 without, in
    Chrome, with a simpler look allowed while the view is moving. The figure without a
    graphics card is measured in the agents' container; the figure with one is confirmed in
    Chrome on the owner's Mac. Chrome is supported, Edge is tested, Safari is not supported.
35. Test renders are made with Playwright in Chrome's engine, on real sliced files. The
    automated tests pin the behaviour coarsely: the preview draws something and not a blank
    or an error, fills roughly the expected part of the view, shows the four line-type
    colours, changes when the layer slider or the view moves, and draws again after the
    graphics context is lost; any comparison with a kept picture allows a wide tolerance.
    The aim is to catch a badly broken preview. Whether it looks right (no combs, no
    show-through at any angle) is judged by a person looking at the renders one by one, when
    the preview is first built and whenever its drawing code changes. The same holds for the
    Layout view.
36. The wizard measures its own drawing in real use and reports it to the front server,
    which writes it to the log, by the same means as failures in the browser. One summary
    for each use of the Layout view and of the Preview step, never frame by frame: frames a
    second, typical and worst; the time from opening the Preview step to the first layer
    drawn; the longest stretch the main thread was held; how much was drawn (instances; the
    sliced file's size and lines). And of the machine: the browser and its version, the
    operating system, whether drawing is by a graphics card or in software and the card's
    name as the browser gives it, the number of processors and the memory as the browser
    reports them, the panel's width and the screen's pixel density, and whether the wizard
    is inside Onshape's panel. No part names and no geometry.
37. Failures in the browser are reported to the front server, which writes one log line for
    each: what failed, on which step, the page's version, the browser's name and version,
    whether 3D is drawn in software, and the hash of the part concerned. Never a part's
    bytes or geometry, never the contents of the storage. At most a few reports a minute from
    one page, and a report that cannot be sent is dropped, never retried into a loop.
38. The wizard's placement check and the slice service's are kept in agreement by one shared
    set of plates, some just passing and some just failing, run by both components' tests.
39. The guide's other proposed targets for speed and memory stand, and a part the browser's
    storage could not hold gets an amber line. The small screen rules it marked "proposed"
    (the form of a confirmation, which message wins on the panel's line, the reminder after
    an upload refused as too large, and the like) stand.

## Reloading for a new version

40. The goal: the page never refreshes under a person who is looking at it or touching it.
    It reloads only when the user moves between steps of the wizard, or when at least 120
    seconds have passed since the user last interacted with the page, and in either case it
    waits while a request of its own is pending. It says nothing afterwards.

## The printer

41. The pairing form is only in the printer details. When the Send step finds no printer
    paired, its message links to the printer details and has no form of its own.
42. Unpair is only in the printer details. Any user of the group may unpair; Unpair is off
    while a print is being followed.
43. "Stop following" is offered to the sender of the print only. If the sender is away, a
    print that has gone stale holds the printer until the daemon reports again or the relay
    gives the print up by its own rule after a day without word.
44. The printer's name is the one the printer itself reports, sent by the daemon when it is
    paired. Nobody types it.
45. A printer not yet heard from shows a grey dot and "…".
46. The Send step exists from phase 2, named Send, with "Download the sliced file" as its
    one button. Phase 5 adds sending to the printer, the print card and the printer-status
    icon.

## The shape of the guide

47. The items about trials and things unmeasured are too detailed for the guide: the layer
    preview's speed without a graphics card; laying on a face, auto-orient and Arrange on
    real exported parts; and the like. Each is cut to what is to be learned, why it matters
    and what decision depends on it. How the measuring or the building is done belongs in
    `README-details.md`.
48. Every item above that was an open item or a listed choice in the guide leaves its lists
    of open items and of choices, and is stated in the body as the design.
