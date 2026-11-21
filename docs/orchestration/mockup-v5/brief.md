# Brief: wizard mockup version 5

- **Deliverable (REQUIRED):** mockup version 5 in `docs/mockups/print-wizard/`, its
  `DECISIONS.md` updated to version 5, a short algorithm note at
  `docs/research/2026-11-21-lay-on-face-hull-faces.md`, and a result file at
  `docs/orchestration/mockup-v5/result.md`.
- **Stop condition (REQUIRED):** both changes below work in a browser at 320 and 800 px
  panel widths with a clean console; the new Lay on face option was tried on every part
  the mockup offers, including the round ones; screenshots saved to
  `docs/orchestration/mockup-v5/screenshots/`.
- **Budget (REQUIRED):** 120 minutes; no cloud spend.
- **Where this fits:** the owner wants to see this in the mockup soon. Version 4 was just
  merged; change only what this brief asks.

## 1. Lay on face as Orca Slicer does it

The owner wants the Layout step's way of laying an instance on a face to copy Orca
Slicer's "Lay on face" tool. Orca builds a closed convex polyhedron (the convex hull)
around the object, groups the hull's facets into flat faces, keeps the ones worth
offering, and draws each as a translucent rounded patch (the "ovals" in the owner's
screenshot: [orca-lay-on-face.png](../../reference/orca-lay-on-face/orca-lay-on-face.png)).
Clicking a patch lays the object on that face.

**Licence: copy the method, not the code.** Orca Slicer is AGPL; PenguinSlicer is MIT.
Read Orca's implementation (`src/slic3r/GUI/Gizmos/GLGizmoFlatten.cpp` and whatever it
calls, at the tag `v2.4.2` of https://github.com/OrcaSlicer/OrcaSlicer; fetch the files
read-only into your scratch folder). Then write the algorithm note in your own words:
how faces are found, merged, filtered (minimum area, the number kept, any stability test),
and how the patches are drawn and picked. Implement in the mockup from your note, never
by translating Orca's code line by line, and copy no Orca code, comments or constants'
names into the repository. Cite Orca's file and lines in the note. The wizard research
([its section on Orca's tools](../../research/2026-11-19-wizard-layout-and-advanced-mode-research.md))
already records the 5 mm² minimum and the limit of 254 faces; check them.

**Round parts.** The owner: a part such as a pulley is not a box; its hull has many thin
facets round the rim. The student should be offered the faces that make sense (the end
faces of a pulley), not a patch on every sliver of the round side. Orca's filters do part
of this; check what they offer on the mockup's round parts and, if they still offer
slivers, add a simple rule of your own (for example a minimum share of the largest face's
area, or a minimum width) and say which in the note. Do not get carried away: a rule that
behaves sensibly on the mockup's parts is enough, and the note says what the real wizard
would need beyond it.

**In the mockup.** Add it as a new option of the scenario strip's **Lay on face** menu,
named *Faces on the hull (like Orca)*, and make it the default. Keep the four existing
options switchable (question M1 stays open, now with five options). When the student
selects an instance and opens lay on face, the patches show on that instance, in the
light theme's colours, translucent; hover highlights one; a click lays the instance on
it and the patches update. It must work at 320 px. Measure how long finding the faces
takes per part in the browser and put the figures in the result file.

## 2. Parts first, then settings

Swap the first two steps: **Parts** becomes step 1 and **Setup** step 2, so the order is
Parts, Setup, Layout, Preview, Send. Keep the step's name "Setup", as in PenguinCAM. Make
everything that depended on the order still true: the instructions on each step, what
the chips row shows on each step, what Back and Next do, which step the wizard opens on,
resuming after a refresh, the printer-status icon, every sentence in `DECISIONS.md` and
the scenario strip that names a step or its number.

## Also

- Add a "What changed in version 5" section at the top of `DECISIONS.md`, above version
  4's. Update M1 to list the five options. Add no other questions unless the change
  raises one.
- Do not change anything else in the mockup, even things you would improve.

## Walk and rules

Serve the folder on a free port other than 6238 and drive a browser with `playwright-cli`
(session name in `$PLAYWRIGHT_CLI_SESSION`); for WebGL read
`/home/agent/.claude/projects/-repos-popcornpenguins/memory/agent-container-webgl-acceptance.md`.
Stop every server and browser you start and remove any `.playwright-cli/` folder you
leave in the repository.

Read [the standing rules](../review-feedback/briefs/standing-rules.md) and follow them,
with these differences: your folders are `docs/mockups/print-wizard/`,
`docs/orchestration/mockup-v5/` and the one research note; your scratch folder is
`/tmp/claude-1000/-repos-popcornpenguins/866ece9c-6c1b-4561-aa91-d02b79810b96/scratchpad/mockup-v5/`.
