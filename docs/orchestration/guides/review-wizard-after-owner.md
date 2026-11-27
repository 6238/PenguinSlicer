# Review of the wizard's guide after the owner's decisions (Fri 2026-11-27)

A full read, first line to last, of [the wizard's guide](../../../wizard/README.md) against
[the owner's 48 decisions](owner-review-wizard.md) and
[the brief for a guide's writer](brief-writer.md), with repairs made in the guide. Line
numbers are those of the guide after the repairs (2,317 lines).

## Verdict

The guide is internally consistent and the owner can rely on it: all 48 decisions are
stated as the design in the place their subject lives, and no removed mechanism survives
as a mechanism. Six decisions needed a correction (5 and 12 in substance; 1, 11, 43 and
47 in one echo each) and nine other repairs were made, all small: a count or rule stated
differently in two places, a term used before its explanation, a paragraph out of order. Five points are left for the owner under
"Not resolved", none of which contradicts a decision.

## The 48 decisions

1. Present and right (Signing in, Sign-out). Corrected one echo: the Security section said
   the sign-in's cookie lasts thirty days without the "outside Onshape"; it now gives both
   durations.
2. Present and right.
3. Present and right.
4. Present and right.
5. Corrected. The body already made the name plain text for a user in one group. The
   table of joined boxes listed "the group details" as if every user had them, and choice
   1 said the header's second line "holds nothing to click", which the reload glyph
   contradicts. Both reworded, and the reload glyph staying for every user is now row 6 of
   the table of choices, with its reason and the alternative (no glyph).
6. Present and right.
7. Present and right. No "Sign in again" control survives (see "Not resolved" for line
   1730).
8. Present and right.
9. Present and right, with the fallback of one click.
10. Present and right.
11. Present and right. What it leaves open is in the table of choices: rows 2 (what New
    plate does to the earlier plate), 3 (a held plate is never dropped) and 4 (a new tab
    takes up only a plate of its current group). Corrected one echo: the gist under
    "Coming back to running work" omitted "of its current group".
12. Corrected. The returning page's table said the expired message stands "on the Preview
    and Send steps", while "A sliced plate that expires" says that entering the Preview
    step from another step slices. The row now says both cases, as the section does.
13. Present and right ("a new plate", no count).
14. Present and right.
15. Present and right; no Cancel button, state or request survives.
16. Present and right.
17. Present and right (20 and 45 seconds, the same in four places).
18. Present and right.
19. Present and right.
20. Present and right.
21. Present and right.
22. Present and right.
23. Present and right.
24. Present and right.
25. Present and right; no screen for the case anywhere.
26. Present and right; the mockup is kept, in both places that say so.
27. Present and right.
28. Present and right; the three deliberate differences from Orca each have their clause.
29. Present and right.
30. Present and right.
31. Present and right.
32. Present and right.
33. Present and right; the six jobs match the decision's list.
34. Present and right.
35. Present and right; no close comparison with kept pictures survives.
36. Present and right.
37. Present and right.
38. Present and right.
39. Present and right; nothing of the wizard's own is still marked "proposed".
40. Present and right; no ten-second wait, and the page says nothing after a reload.
41. Present and right.
42. Present and right.
43. Present and right. Made "a day" and "24 hours" one statement in the open item.
44. Present and right.
45. Present and right.
46. Present and right.
47. Present and right for the two trials and the unmeasured items. Added the missing "why
    it matters" to the item on hosted progress.
48. Present and right: no decided item remains in the open items or the table of choices.

## What was changed under B to F

- B: "Where to look first" said five choices; the table now has six and the text says six.
- B: "Where to look first" did not mention the two unmeasured items on storage and hosted
  progress; added.
- B: the table of choices, row 1, reason reworded to agree with the reload glyph.
- B: the open item on a print no longer followed said "24 hours of silence" where the
  body says "a day without word"; now "a day (24 hours) without word".
- B: the Security section's duration of the sign-in now matches "Signing in".
- C: the terms said a user "starts another" plate with New plate; New plate empties the
  tab's plate, and the sentence now says so.
- C: "quick change" was used in the header's description before it was explained; a
  one-sentence definition added there.
- C: "the slicing card" and "the print card" were used under "When the server is slow"
  before either was explained; each now has a clause saying what it is.
- C: "the 12-hour rule" was named under Sign-out before any such rule was stated; now "12
  hours without use, like any stored plate".
- C: in "Signing in", the closing pointer to what phase 4 must confirm stood before the
  paragraph on unsupported browsers; it is now last.
- C: in "Pairing a printer", the description of the form was split by the Send step's
  message; the form is now described first, the message second, and the table has a
  sentence introducing it.
- C: the item "Whether progress reaches the page unheld when hosted" lacked why it
  matters.
- E: removed "Making the Preview step follow Onshape too would be a change to an accepted
  screen", a rejected option outside the table of choices.
- D: nothing found. The only code spans are the four colour values of the layer preview,
  which are design values.
- F: all 198 relative links and anchors resolve, including anchors in the other guides.
  The one `mermaid` fence is a plain `flowchart TB` with quoted labels and no HTML; it was
  checked by reading and not rendered.

## Not resolved

- Lines 347 and 1740: the words "a second plate" remain twice, as the wording the slice
  service and printer delivery still use and are asked to change. They are not the
  wizard's words, so they were kept; removing them would hide known work in those
  components.
- Lines 1730 and 1733: the table of what the other components do not provide yet names
  two removed mechanisms ("no request to sign in again", "no limit of one unfinished slice
  for each user") as things the contract must stop holding. Kept for the same reason.
- Lines 1110 and 1352: a user who sees the expired message on the Preview step, steps
  back and enters the Preview step again. By the text this slices, since entering the
  step slices any plate not yet sliced; the guide does not say so for this case, and the
  decisions do not either.
- Lines 288 and 1327 against line 1217: "No user of a group has rights another lacks"
  and "there are no permissions inside a group", while Stop following is offered to the
  sender of the print only (decision 43). Left as written, since the sender's link
  concerns their own print; the owner may want the exception said.
- The table "Designed here and not in the mockup" was checked against the body of the
  guide and not against the mockup's own screens.
