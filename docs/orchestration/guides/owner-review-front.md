# The owner's review of the front server's guide (Fri 2026-11-27)

What the owner decided while reading [the front server's guide](../../../front/README.md),
together with what the owner's [review of the wizard's guide](owner-review-wizard.md) asks
of the front server. It wins over every other document where they differ. The guide states
each of these as the design, without saying who decided or when.

## Signing in

1. Signing in is open to anyone with an Onshape account. A user who belongs to no company
   or classroom is a group of one.
2. Nothing limits how often a user signs in. The year's total of calls to Onshape is
   watched in the log.
3. Inside Onshape's panel the sign-in must not be felt as separate from Onshape's: it lasts
   as long as the user is signed in to Onshape. The means is what PenguinCAM does, since it
   is known to work: a cookie that the browser sends to a page embedded in another site,
   and a sign-in from the panel by a "Connect" button and a small window that closes
   itself. So one click the first time in a browser is the baseline inside the panel; a
   trip to Onshape that the user never sees is what to try for, not what to rely on.
4. When the sign-in is missing or has run out, the page starts the trip to Onshape by
   itself at a quiet moment and returns to the same step. The front server's answer to a
   request that is not signed in is what tells the page to do so.
5. If Onshape says a different person is signed in on this browser, the sign-in is made
   again for that person.
6. Outside Onshape a sign-in lasts thirty days from its last use: it is extended by use.
   Stated consequence: a user who keeps using PenguinSlicer outside Onshape is never asked
   to sign in again, so their groups are not read again until the Onshape app is public
   and groups are read daily.
7. Outside Onshape the page has a sign-out link, which removes the cookie. Inside the panel
   there is none.
8. There is no "Sign in again" for a user to press. The front server reads a user's groups
   again itself: at every sign-in, and when Onshape says the user is working in a company
   that the sign-in does not list.
9. Inside Onshape the current group is the group of the document the user has open; no
   choice is offered. Outside Onshape a user in more than one group chooses. Every request
   that acts for a group carries the group and is checked against the sign-in, as before.
10. The Onshape app asks, from phase 3, for permission to read who the user is, their
    companies and classrooms, and their documents, so that users are not asked to approve
    more in phase 4. It never asks for permission to write.
11. A user of Safari is shown a plain page saying that PenguinSlicer needs Chrome.
12. To confirm in phase 4, stated with its fallback: whether Onshape tells a panel the user
    and the company. Without it, point 9 costs a call to Onshape for each document and
    point 5 has no trigger.

## Parts and slices

13. There is no limit of one unfinished slice job for each user. A user may have several
    slices under way; everyone shares the slice service's places. Within one plate, a
    changed plate's new slice replaces that plate's own earlier unfinished slice; the page
    makes an id for each plate.
14. A slice cannot be cancelled by hand. The front server offers the page no request to
    cancel a slice job.
15. A plate configuration submitted twice: the page makes a value for each submission, and
    a repeat that carries the same value is answered with the first attempt's slice job.
16. A plate configuration submitted while the slice service is stopping: the front server
    holds nothing. It passes on the slice service's answer, and the wizard shows the slice
    as waiting, says the slicer is restarting, and tries again by itself, for up to 300
    seconds.
17. A slice job is reported as finished only once its sliced file is stored.
18. The front server tells the page the moment a sliced file expires, with the sliced
    file's details.
19. A sliced file is at most 50 MB. The slice service ends a slice whose file would be
    larger, with its own sentence; the front server refuses to store a larger one.
20. The list of settings for the wizard's advanced mode, with Orca's own labels, groups and
    explanations, and the profile catalog's names, come from the slice service; the front
    server passes them to the wizard. The front server checks each group's configuration
    against the catalog's names when it starts and when a configuration is edited.
21. Following slice jobs is counted among the front server's 100 threads. Progress streams
    are kept for slice jobs and for prints; the guide states a target for users at once and
    limits the streams one user may hold.
22. Every answer except the wizard's own page files is marked as not to be kept by any
    proxy or browser, so that no proxy ever holds one user's sliced file or configuration.

## The configuration

23. Until the edit screens exist, every group gets the built-in default, unless the owner
    places a document by hand for that group.
24. The front server never gives the wizard an invalid configuration. When a group's saved
    document is invalid, it serves the default in its place, leaves the saved file
    untouched, and writes an error to the log naming the group and what is wrong. The
    wizard's header names the configuration in use.
25. The configuration holds, for each profile a user can pick, the three Orca profile names
    that go into a plate configuration.

## Reports from the browser

26. The page reports its failures to the front server, which writes one log line for each:
    what failed, on which step, the page's version, the browser's name and version,
    whether 3D is drawn in software, and the hash of the part concerned. Never a part's
    bytes or geometry, never the contents of the browser's storage. At most a few reports a
    minute from one page.
27. The page reports a summary of its drawing for each use of the Layout view and of the
    Preview step, which the front server writes to the log: frames a second, typical and
    worst; the time to the first layer drawn; the longest stretch the main thread was
    held; how much was drawn; and of the machine: browser and version, operating system,
    whether drawing is by a graphics card or in software and the card's name, the number
    of processors and the memory as the browser reports them, the panel's width and the
    screen's pixel density, and whether the wizard is inside Onshape's panel.

## The log

28. One file each minute holds the lines of all components: the front server, the relay,
    the slice service, the daemons' telemetry and the reports from the browser. It is
    written once and never rewritten; the store has no way to append to a file.
29. The files sit in folders by year, then month, then day, so that no folder holds more
    than about 1,440 files. Names use UTC; the command that reads the log shows Pacific
    time.
30. Every line carries the component that wrote it. Filtering by component is the
    reader's job, and the command that reads the log does it.

## The printer, from phase 5

31. "Stop following" is accepted from the sender of the print only.
32. The printer's display name is the one the printer itself reports, sent by the daemon
    when it is paired.

## Deploys

33. The check that runs after each deploy tells the owner when it fails, and the owner puts
    the previous version back by hand. Something outside the host that watches the service
    comes later, once users rely on it.
34. Each container's previous version must work against the other's new one.
35. The log is built in phase 2, into a folder. The defences against requests from other
    sites are built in phase 3.

## The shape of the guide

36. That a part or a sliced file passes through without being held whole in memory is a
    matter for the builder. It leaves the guide and stays in `README-details.md`. Other
    mechanics of the same kind leave the guide the same way.
37. The limits on how fast one user may upload parts and submit plates, and how often
    expired files are swept, are the builder's to settle.
38. Every item above that was an open item or an unconfirmed choice in the guide leaves
    those lists and is stated in the body as the design. What stays in the lists is only
    what the real host or Onshape must show.
