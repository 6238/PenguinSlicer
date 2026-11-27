# Review of the front server's guide after the owner's decisions (Fri 2026-11-27)

A review, with repair, of [the front server's guide](../../../front/README.md) against
[the owner's 38 decisions](owner-review-front.md), and the alignment of
[the wizard's guide](../../../wizard/README.md) to them and to
[the owner's 48 decisions on the wizard](owner-review-wizard.md). Line numbers are those
of the files after the repairs.

## Verdict on the front server's guide

The guide states all 38 decisions as the design, each where its subject lives, and no
survivor of a removed mechanism was found in it. It had one contradiction of substance,
a sentence that made the unseen trip inside Onshape's panel the thing relied on, and the
three figures of decision 21 were presented as settled instead of as the guide's
proposal; both are repaired. After the repairs its figures agree everywhere they
appear, its tables match its body, its links and anchors resolve and its two diagrams
are well formed, but it points into the slice service's guide and is pointed at by two
contracts that have not been brought to the same decisions (see "Not resolved").

## The 38 decisions

1. Present and right ("Who may sign in").
2. Present and right ("Sign-ins and the allowance").
3. Corrected: the bullet "After that the sign-in is not felt" said a missing or expired
   cookie is replaced by a trip "without asking the user anything", which relied on the
   unseen trip. It now says the cookie is extended by use, that a lost cookie costs one
   click on Connect, and that the unseen trip removes the click if it proves possible.
4. Present; corrected in one place: "What starts a trip" now says that inside the panel
   the first trip in a browser starts from a button.
5. Present and right.
6. Present and right, with its stated consequence.
7. Present and right.
8. Present and right.
9. Present and right.
10. Present and right.
11. Present and right.
12. Present and right ("What Onshape tells a panel", with both fallbacks).
13. Present and right.
14. Present and right.
15. Present and right.
16. Present; the table under "When things go wrong" now carries the 300 seconds.
17. Present and right.
18. Present and right.
19. Present; the remedy in the table now reads as the wizard's does (fewer instances, or
    a new plate).
20. Present and right, with the corrected ending: nothing compares a configuration with
    the catalog, and who notices is open until Orca is first upgraded.
21. Corrected: the fifty idle daemons, forty pages following and four progress streams
    are now marked "this guide's proposal" in the table of limits, under "Progress" and
    under "How many users at once", with the sum shown (50 + 40 + 3 + 7 = 100), and are
    listed once among what is undecided, as "The figures for users at once".
22. Present and right.
23. Present and right.
24. Present and right.
25. Present and right.
26. Present and right.
27. Present and right.
28. Present and right.
29. Present and right.
30. Present and right.
31. Present and right.
32. Present and right.
33. Present and right.
34. Present and right.
35. Present and right.
36. Present and right: no passage on holding a file whole in memory remains.
37. Present and right.
38. Present; the part on what is undecided now holds the host's, Onshape's and Chrome's
    items and five points left open, the fifth being the three proposed figures.

## Other repairs to the front server's guide

- A sentence of introduction added before the table "What it exchanges", which stood
  with no text before it.
- A line of 110 characters in "Reading it and writing it" rewrapped.
- "Restarts and deploys": "the table" is now "the table below", since the table follows.
- The introduction to "The limits that matter" defines "This guide's proposal" beside
  "The design's choice".
- "What is undecided or unmeasured": the opening count corrected from four points to
  five, and why it matters and what depends on it added to four items that lacked one
  or both (the cost, a daemon through Cloudflare, which allowance the owner's account
  has, an account with no company or classroom).
- "The fifth progress stream" now links to the wizard's item of the same subject.

## Changes to the wizard's guide

- Signing in: inside Onshape's panel the baseline is one click on Connect the first
  time in a browser, with a small window that closes itself; the unseen trip is what
  phase 4 tries for; the aim (not felt as separate from Onshape's sign-in) is kept.
  The same is said in "To be confirmed inside Onshape, in phase 4", the table "Inside
  Onshape's panel and outside it", "What must work inside the panel", "Security", the
  index of "When things go wrong", the table of screens designed here and phase 4's row.
- Outside Onshape a sign-in lasts thirty days from its last use (Signing in, the table
  of the two homes, Security, the table of asks).
- What Onshape asks the user to allow, and the front server's sentence after a refusal,
  now name the user's documents as well, and say that nothing is written.
- While the slice service is stopping: a new paragraph and a new row of the slicing
  card's table under "Slicing" (waiting, the slicer is restarting, 300 seconds); the
  paragraph under "When the server is slow" that showed the slow-server message for
  minutes is replaced; "A restart or a deploy" loses its "one known exception".
- A plate submitted twice: stated under "Slicing" and in the list and table of what the
  wizard asks of the front server.
- A sliced file is at most 50 MB: a row in the table of slice failures, the row "A
  sliced file" of the table of limits, the list and table of asks, and the index.
- The moment a sliced file expires is stated as what the front server does, no longer
  as "to be told" and "undecided".
- Advanced mode's table of settings: stated as supplied by the slice service and passed
  on by the front server; the open item "Where advanced mode's settings come from" is
  removed.
- A configuration that names a lost profile: listed under "Open in the other guides" as
  open until Orca is first upgraded; no check by the front server is stated anywhere.
- "Choices made in designing these screens" removed, with its mentions at the top of
  the guide, in "Where to look first" (now two places) and in the introduction to
  "Designed here and not in the mockup"; one sentence stands where the table stood.
- Removed as settled from "Open items of the other guides that would change the panel":
  a plate submitted while the slice service stops, telling the page when a sliced file
  expires, a plate submitted twice, and who may sign in. "Following a print without a
  progress stream" is replaced by "A user's fifth progress stream", which is still
  open.

## Not resolved

- [contracts/wizard-front-server.md](../../../contracts/wizard-front-server.md) lines
  113 and 300, and [contracts/configuration.md](../../../contracts/configuration.md)
  line 95, link to a section of the front server's guide, "Choices the owner has not
  yet confirmed", that no longer exists. Those files were outside this task.
- [slice/README.md](../../../slice/README.md) still states one unfinished slice job for
  each user (lines 339, 354, 459, 1053), still lists "What a user sees while the slice
  service stops" as open (line 1171) and has no sentence for a sliced file over 50 MB.
  The front server's guide points at it for these subjects (front/README.md lines 523,
  549 and 618), so a reader who follows those links meets the earlier design.
  [docs/architecture.md](../../architecture.md) lines 239 and 499 say the same of one
  unfinished slice job.
- front/README.md line 1177 gives "at most 25 parts in the part store for one user
  key", the slice service's figure (slice/README.md line 201). With a plate for each
  tab and several slices for one user, two tabs with full plates need up to 50. The
  decision files do not settle it; the figure was left as the slice service's.
- front/README.md line 337: that a cookie lost or expired inside the panel costs one
  more click on Connect is this review's reading of decision 3 (one click is the
  baseline, the unseen trip is not relied on) against decision 4 (the page starts the
  trip by itself). The owner may want it said differently.
- front/README.md line 1014: the heading "What the wizard's guide asks of the front
  server" names a document and not its subject, the page's reports about itself. It
  was kept because contracts/wizard-front-server.md line 395 links to it.
- wizard/README.md, "Signing in": the Connect button's screen is described in three
  sentences taken from the front server's guide. Its exact wording and what stands
  around the button have not been drawn or reviewed.
